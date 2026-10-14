# Estimates how crowded each Wi-Fi channel is from a scan of nearby access points.
# "Load" is a signal-weighted count of overlapping radios: a loud neighbour counts ~1, a faint one ~0.
# It's a proxy for contention, not measured airtime.
from dataclasses import asdict, dataclass

from kestrel.models import Link, Network

CHANNELS = {
    '2.4 GHz': list(range(1, 14)),
    '5 GHz': [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144,
              149, 153, 157, 161, 165],
    '6 GHz': list(range(1, 234, 4)),
}
RECOMMENDABLE_24 = [1, 6, 11]  # The only non-overlapping 2.4 GHz channels
DFS_5 = range(52, 145)  # Radar channels: allowed, but an AP may be forced off them


@dataclass
class ChannelLoad:
    channel: int
    load: float
    radios: int  # Overlapping radios with any weight
    strongest: int | None  # dBm of the loudest overlapping radio
    current: bool = False
    recommended: bool = False


def weight(signal: int) -> float:
    return min(1.0, max(0.0, (signal + 95) / 50))  # -45 dBm and up → 1, -70 → 0.5, -95 → 0


def overlap(network: Network, channel: int) -> float:
    """Fraction of a 20 MHz channel that the network's transmission covers."""
    if network.band == '2.4 GHz':
        # 2.4 GHz channels are 5 MHz apart, so a 20 MHz signal spills ±2 channels; secondary side of 40 MHz is unknown
        half = network.width / 10
        covered = min(channel + 2, network.channel + half) - max(channel - 2, network.channel - half)
        return max(0.0, covered / 4)
    return 1.0 if channel in occupied_channels(network) else 0.0


def occupied_channels(network: Network) -> list[int]:
    """5/6 GHz networks wider than 20 MHz occupy an aligned block of 20 MHz channels."""
    count = max(1, network.width // 20)
    span = 4 * count
    if network.band == '6 GHz':
        base = 1
    else:
        base = 36 if network.channel < 100 else 100 if network.channel < 149 else 149
    start = base + (network.channel - base) // span * span
    return [start + 4 * i for i in range(count)]


def radios(networks: list[Network]) -> list[Network]:
    """One entry per physical radio: APs broadcast several SSIDs with BSSIDs differing only in the last octet."""
    loudest = {}
    for n in networks:
        key = (n.bssid[:14] if n.bssid else id(n), n.band, n.channel)
        if key not in loudest or n.signal > loudest[key].signal or n.in_use:
            loudest[key] = n
    return list(loudest.values())


def analyse(networks: list[Network], link: Link | None = None) -> dict:
    # The radio we're connected to isn't competition, so it's left out of the load
    ours = {(n.bssid[:14], n.band) for n in networks if n.bssid and (n.in_use or (link and n.bssid == link.bssid))}
    others = [n for n in radios(networks) if not (n.in_use or (n.bssid and (n.bssid[:14], n.band) in ours))]
    bands = {}
    for band, channels in CHANNELS.items():
        in_band = [n for n in others if n.band == band]
        if band == '6 GHz' and not in_band:
            continue
        loads = [_load(channel, in_band) for channel in channels]
        if band == '6 GHz':
            loads = [load for load in loads if load.radios]
        _mark(loads, band, link)
        bands[band] = [asdict(load) for load in loads]

    return {
        'bands': bands,
        'networks': [n.to_dict() for n in sorted(networks, key=lambda n: -n.signal)],
        'current': {'channel': link.channel, 'band': link.band} if link and link.wireless else None,
    }


def _load(channel: int, networks: list[Network]) -> ChannelLoad:
    hits = [(n, overlap(n, channel)) for n in networks]
    hits = [(n, share) for n, share in hits if share > 0 and weight(n.signal) > 0]
    return ChannelLoad(
        channel=channel,
        load=round(sum(weight(n.signal) * share for n, share in hits), 2),
        radios=len(hits),
        strongest=max((n.signal for n, _ in hits), default=None),
    )


def _mark(loads: list[ChannelLoad], band: str, link: Link | None):
    for load in loads:
        load.current = bool(link and link.band == band and link.channel == load.channel)
    candidates = [l for l in loads if band != '2.4 GHz' or l.channel in RECOMMENDABLE_24]
    if band == '5 GHz':
        candidates = [l for l in candidates if l.channel not in DFS_5] or candidates
    if candidates:
        min(candidates, key=lambda l: (l.load, l.channel)).recommended = True
