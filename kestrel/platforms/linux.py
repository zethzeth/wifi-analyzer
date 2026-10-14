# Linux backend: iproute2 for the gateway, iw for the link and signal levels, nmcli for scans.
import re
import subprocess
from pathlib import Path

from kestrel.models import Link, Network, band_for


def gateway() -> tuple[str | None, str | None]:
    """Router IP and the interface that reaches it."""
    # Matches the default route's gateway and device.
    # ✔ default via 192.168.1.1 dev wlan0 proto dhcp  ✔ default via 10.0.0.1 dev eth0  ✘ default dev wg0 scope link
    match = re.search(r'default via (\S+) dev (\S+)', _run(['ip', 'route', 'show', 'default']))
    return (match.group(1), match.group(2)) if match else (None, None)


def dns_server(interface: str | None) -> str | None:
    """First upstream resolver, so DNS timings skip systemd-resolved's local cache."""
    output = _run(['resolvectl', 'dns', interface]) if interface else ''
    # Matches the first IPv4 resolver after the link label.
    # ✔ Link 2 (wlan0): 9.9.9.9 1.1.1.1  ✔ Link 3 (eth0): 192.168.1.1  ✘ Link 2 (wlan0):
    return _find(r'\): (\d+\.\d+\.\d+\.\d+)', output)


def link(interface: str | None) -> Link:
    if not _is_wireless(interface):
        return Link(interface, wireless=False)
    return parse_link(interface, _run(['iw', 'dev', interface, 'link']), _run(['iw', 'dev', interface, 'info']))


def parse_link(interface: str, link_output: str, info_output: str) -> Link:
    # Matches the channel number and width of the current association.
    # ✔ channel 128 (5640 MHz), width: 20 MHz,  ✔ channel 6 (2437 MHz), width: 40 MHz  ✘ channel 6 (2437 MHz)
    channel = re.search(r'channel (\d+) \((\d+) MHz\), width: (\d+) MHz', info_output)
    return Link(
        interface,
        wireless=True,
        ssid=_find(r'SSID: (.+)', link_output),  # ✔ SSID: Home  ✘ ssid Home
        bssid=_find(r'Connected to ([0-9a-f:]{17})', link_output),  # ✔ Connected to a8:53:7d:20:47:82  ✘ Not connected.
        signal=_int(_find(r'signal: (-?\d+) dBm', link_output)),  # ✔ signal: -39 dBm  ✘ signal avg: -39
        channel=int(channel.group(1)) if channel else None,
        width=int(channel.group(3)) if channel else None,
        band=band_for(int(channel.group(2))) if channel else None,
        tx_rate=_float(_find(r'tx bitrate: ([\d.]+) MBit/s', link_output)),  # ✔ tx bitrate: 286.7 MBit/s  ✘ tx bitrate: n/a
    )


def networks(rescan: bool = False) -> list[Network]:
    """Nearby access points. A rescan takes a few seconds and briefly disturbs traffic."""
    _, interface = gateway()
    listing = _run(['nmcli', '-t', '-f', 'IN-USE,SSID,BSSID,CHAN,FREQ,BANDWIDTH,SIGNAL', 'dev', 'wifi', 'list',
                    '--rescan', 'yes' if rescan else 'auto'], timeout=20)
    signals = parse_scan_signals(_run(['iw', 'dev', interface, 'scan', 'dump'])) if _is_wireless(interface) else {}
    return parse_nmcli_networks(listing, signals)


def parse_nmcli_networks(listing: str, signals: dict[str, int]) -> list[Network]:
    """nmcli knows channel widths; iw knows real dBm (nmcli only has a 0-100 score)."""
    found = []
    for line in listing.splitlines():
        # Matches the field separators in terse nmcli output: colons not escaped with a backslash.
        # ✔ the ":" in "*:Home"  ✔ the ":" in "Home:A8"  ✘ the ":" in "A8\:53"
        fields = [field.replace('\\:', ':') for field in re.split(r'(?<!\\):', line)]
        if len(fields) != 7 or not fields[3].isdigit():
            continue
        in_use, ssid, bssid, channel, freq, width, score = fields
        bssid = bssid.lower()
        found.append(Network(
            ssid=ssid or None,
            bssid=bssid,
            channel=int(channel),
            band=band_for(_float(freq.split()[0])),
            width=_int(width.split()[0]) or 20,
            signal=signals.get(bssid, round(int(score) / 2 - 100)),  # Rough score→dBm fallback
            in_use=in_use == '*',
        ))
    return found


def parse_scan_signals(scan_dump: str) -> dict[str, int]:
    signals = {}
    for block in scan_dump.split('\nBSS '):
        bssid = _find(r'^(?:BSS )?([0-9a-f:]{17})', block)  # ✔ BSS a8:53:7d:20:47:82(on wlan0)  ✘ BSSID: a8:53:...
        signal = _float(_find(r'\tsignal: (-?[\d.]+) dBm', block))  # ✔ signal: -39.00 dBm  ✘ signal: n/a
        if bssid and signal is not None:
            signals[bssid] = round(signal)
    return signals


def _is_wireless(interface: str | None) -> bool:
    return bool(interface) and Path(f'/sys/class/net/{interface}/wireless').exists()


def _find(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def _int(value: str | None) -> int | None:
    return int(value) if value and value.lstrip('-').isdigit() else None


def _float(value: str | None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _run(command: list[str], timeout: float = 5) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ''
