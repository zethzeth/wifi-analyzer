# Each probe returns its measurement, or None when it failed.
import ipaddress
import os
import re
import subprocess
import sys

import speedtest

TIMEOUT_SECONDS = 3


def ping(host: str) -> float | None:
    if not host:
        return None
    output = _run(['ping', '-c', '1', host])
    # Matches the round-trip time in a ping reply.
    # ✔ time=15.2 ms  ✔ time=7 ms  ✘ time<1ms
    match = re.search(r'time=([\d.]+) ms', output or '')
    return float(match.group(1)) if match else None


def resolve(domain: str, server: str | None = None) -> float | None:
    output = _run(['dig', *([f'@{server}'] if server else []), '+tries=1', f'+time={TIMEOUT_SECONDS - 1}', domain])
    if not output or 'status: NOERROR' not in output or 'ANSWER SECTION' not in output:
        return None
    # Matches dig's own query timing, which excludes process startup.
    # ✔ ;; Query time: 12 msec  ✔ ;; Query time: 0 msec  ✘ ;; Query time: n/a
    match = re.search(r'Query time: (\d+) msec', output)
    return float(match.group(1)) if match else None


def isp_hop(target: str = '8.8.8.8') -> str | None:
    """First public hop that answers ping: usually the ISP's edge router, just past the office router/firewall."""
    for command in (['tracepath', '-n', '-m', '10', target], ['traceroute', '-n', '-q', '1', '-w', '1', '-m', '10', target]):
        output = _run(command, timeout=20)
        if output:
            break
    public = [ip for ip in parse_hops(output or '') if ipaddress.ip_address(ip).is_global and ip != target]
    return next((ip for ip in public[:3] if ping(ip) is not None), None)


def parse_hops(output: str) -> list[str]:
    """Hop IPs in order, deduplicated; works for both tracepath and traceroute output."""
    # Matches a hop number followed by the hop's IPv4 address.
    # ✔ " 3:  194.50.40.3   2.902ms"  ✔ " 3  194.50.40.3  2.9 ms"  ✘ " 1?: [LOCALHOST]  pmtu 1500"
    hops = re.findall(r'^\s*\d+\??:?\s+(\d+\.\d+\.\d+\.\d+)', output, re.M)
    return list(dict.fromkeys(hops))


def speeds() -> tuple[float | None, float | None]:
    """Download and upload speed in Mbps."""
    try:
        test = speedtest.Speedtest(secure=True)
        test.get_best_server()
        test.download()
        test.upload()
    except Exception as e:
        if os.getenv('DEBUG'):
            print(f'Speedtest failed: {e}', file=sys.stderr)
        return None, None
    return round(test.results.download / 1e6, 2), round(test.results.upload / 1e6, 2)


def _run(command: list[str], timeout: float = TIMEOUT_SECONDS) -> str | None:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
