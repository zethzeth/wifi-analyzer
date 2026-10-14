# macOS backend: route/scutil for gateway and DNS, CoreWLAN for the live link, system_profiler for scans.
# SSIDs and BSSIDs are hidden unless the terminal (or Kestrel.app) has Location Services access.
import json
import re
import subprocess

from kestrel.models import Link, Network, band_for

try:
    import CoreWLAN
except ImportError:
    CoreWLAN = None

CW_WIDTHS = {1: 20, 2: 40, 3: 80, 4: 160}  # CWChannelWidth enum
CW_BANDS = {1: '2.4 GHz', 2: '5 GHz', 3: '6 GHz'}  # CWChannelBand enum


def gateway() -> tuple[str | None, str | None]:
    """Router IP and the interface that reaches it."""
    output = _run(['route', '-n', 'get', 'default'])
    return _find(r'gateway: (\S+)', output), _find(r'interface: (\S+)', output)  # ✔ gateway: 192.168.1.1  ✘ gateway:


def dns_server(interface: str | None) -> str | None:
    # ✔ nameserver[0] : 192.168.1.1  ✔ nameserver[0] : 9.9.9.9  ✘ nameserver[1] : 1.1.1.1
    return _find(r'nameserver\[0\] : (\d+\.\d+\.\d+\.\d+)', _run(['scutil', '--dns']))


def link(interface: str | None) -> Link:
    if CoreWLAN is None:
        return _link_from_profiler(interface)

    wifi = CoreWLAN.CWWiFiClient.sharedWiFiClient().interface()
    if wifi is None or wifi.interfaceName() != interface or not wifi.rssiValue():
        return Link(interface, wireless=False)

    channel = wifi.wlanChannel()
    return Link(
        interface,
        wireless=True,
        ssid=wifi.ssid(),
        bssid=wifi.bssid(),
        signal=wifi.rssiValue(),
        noise=wifi.noiseMeasurement() or None,
        channel=channel.channelNumber() if channel else None,
        width=CW_WIDTHS.get(channel.channelWidth()) if channel else None,
        band=CW_BANDS.get(channel.channelBand()) if channel else None,
        tx_rate=wifi.transmitRate() or None,
    )


def networks(rescan: bool = False) -> list[Network]:
    """Nearby access points; system_profiler always scans, so `rescan` is implied."""
    data = _profiler_interface(None)
    current = data.get('spairport_current_network_information')
    found = [parse_profiler_network(current, in_use=True)] if current else []
    for key, entries in data.items():
        if key.startswith('spairport_airport_') and key.endswith('wireless_networks'):
            found += [parse_profiler_network(entry) for entry in entries]
    return [network for network in found if network]


def parse_profiler_network(entry: dict, in_use: bool = False) -> Network | None:
    """Entries look like {"_name": "Home", "spairport_network_channel": "36 (5GHz, 80MHz)",
    "spairport_signal_noise": "-55 dBm / -92 dBm"}; older macOS gives a bare channel number."""
    raw_channel = str(entry.get('spairport_network_channel', ''))
    channel = _int(_find(r'^(\d+)', raw_channel))  # ✔ 36 (5GHz, 80MHz)  ✔ 6  ✘ (5GHz)
    signal = _int(_find(r'^(-?\d+) dBm', str(entry.get('spairport_signal_noise', ''))))  # ✔ -55 dBm / -92 dBm  ✘ n/a
    if channel is None or signal is None:
        return None
    ghz = _find(r'\((\d)GHz', raw_channel)  # ✔ 36 (5GHz, 80MHz)  ✔ 1 (2GHz, 20MHz)  ✘ 36
    return Network(
        ssid=entry.get('_name'),
        bssid=entry.get('spairport_network_bssid'),
        channel=channel,
        band={'2': '2.4 GHz', '5': '5 GHz', '6': '6 GHz'}.get(ghz) or band_for(channel=channel),
        width=_int(_find(r'(\d+)MHz', raw_channel)) or 20,  # ✔ 36 (5GHz, 80MHz)  ✘ 36
        signal=signal,
        in_use=in_use,
    )


def _link_from_profiler(interface: str | None) -> Link:
    current = _profiler_interface(interface).get('spairport_current_network_information')
    network = parse_profiler_network(current) if current else None
    if not network:
        return Link(interface, wireless=False)
    noise = _int(_find(r'/ (-?\d+) dBm', current.get('spairport_signal_noise', '')))  # ✔ -55 dBm / -92 dBm  ✘ -55 dBm
    return Link(interface, True, network.ssid, network.bssid, network.signal, noise, network.channel,
                network.width, network.band, _float(current.get('spairport_network_rate')))


def _profiler_interface(interface: str | None) -> dict:
    """The Wi-Fi interface block of `system_profiler SPAirPortDataType -json` (slow: it scans)."""
    try:
        data = json.loads(_run(['system_profiler', 'SPAirPortDataType', '-json'], timeout=30) or '{}')
        interfaces = data['SPAirPortDataType'][0]['spairport_airport_interfaces']
    except (ValueError, KeyError, IndexError):
        return {}
    return next((i for i in interfaces if i.get('_name') == interface), interfaces[0] if interfaces else {})


def _find(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.M)
    return match.group(1) if match else None


def _int(value: str | None) -> int | None:
    return int(value) if value and value.lstrip('-').isdigit() else None


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _run(command: list[str], timeout: float = 10) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ''
