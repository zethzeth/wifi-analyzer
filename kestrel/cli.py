# Terminal front end: prompts, a live table while the test runs, then the report.
import select
import shutil
import sys
import threading
from datetime import datetime

from tabulate import tabulate

from kestrel import channels, platforms
from kestrel.runner import Analysis
from kestrel.settings import Settings
from kestrel.term import LiveTable, block_title, color

TABLE = LiveTable([('Time', 10), ('Type', 28), ('Target', 18), ('Result', 10), ('Signal', 12), ('Channel', 14)])
LEVEL_STYLE = {'bad': ('✖', 'red'), 'warn': ('▲', 'yellow'), 'ok': ('✔', None)}


def run():
    block_title('Kestrel', 'magenta')
    for tool in ['ping', 'dig']:
        if not shutil.which(tool):
            print(color(f'Missing "{tool}" on PATH - those probes will all fail.', 'red'))

    connection = platforms.connection()
    print_connection(connection)
    settings = prompt_for_settings()
    print(f'\nRunning for {settings.duration}s. Press Enter to stop early.\n')

    analysis = Analysis(settings, connection, TerminalEvents().emit)
    threading.Thread(target=_stop_on_enter, args=(analysis,), daemon=True).start()
    analysis.run()


def channels_view():
    connection = platforms.connection()
    if not connection.link.wireless:
        print('Not on Wi-Fi.')
        return
    print('Scanning...')
    print_channels(channels.analyse(platforms.networks(rescan=True), connection.link))


def prompt_for_settings() -> Settings:
    block_title('Test settings', 'blue')
    name = input('Test name (default: Unknown): ').strip() or 'Unknown'
    location = input('Location, e.g. "2nd floor, desk 14" (optional): ').strip()
    run_speedtests = input('Run speedtests? (Y/n): ').strip().lower() != 'n'
    duration = input('Duration in seconds (default: 300): ').strip()
    return Settings(
        test_name=f'{name} - {datetime.now():%Y-%m-%d--%H-%M-%S}',
        location=location,
        run_speedtests=run_speedtests,
        duration=int(duration) if duration.isdigit() else 300,
    )


def print_connection(connection):
    link = connection.link
    block_title('Connection', 'blue')
    print(f'Router IP: {connection.router_ip or "not found"}')
    print(f'DNS:       {connection.dns_server or "system resolver"}')
    print(f'Interface: {link.interface or "not found"} ({"wireless" if link.wireless else "cabled"})')
    if link.wireless:
        print(f'SSID:      {link.ssid or "hidden"} (AP {link.bssid or "unknown"})')
        print(f'Signal:    {link.describe_snr()}')
        print(f'Channel:   {link.describe_channel()} on {link.band}')
        print(f'Link rate: {link.tx_rate or "N/A"} Mbit/s')


def print_channels(report: dict):
    current = report['current'] or {}
    for band, loads in report['bands'].items():
        block_title(f'Channel load - {band}', 'blue')
        peak = max([l['load'] for l in loads] + [1])
        for l in loads:
            bar = '█' * round(l['load'] / peak * 40)
            tags = ' ← you' * l['current'] + ' ★ quietest' * l['recommended']
            line = f'{l["channel"]:>4}  {bar:<40} {l["load"]:>5.1f}  {l["radios"]:>2} radios{tags}'
            print(color(line, 'magenta' if l['current'] else None))
    block_title('Nearby access points', 'blue')
    rows = [[n['ssid'] or '(hidden)', n['bssid'] or '-', n['band'], n['channel'], f'{n["width"]} MHz',
             f'{n["signal"]} dBm', '*' if n['in_use'] else ''] for n in report['networks']]
    print(tabulate(rows, ['SSID', 'BSSID', 'Band', 'Ch', 'Width', 'Signal', 'Use']))
    if current:
        print(f'\nYou are on channel {current["channel"]} ({current["band"]}). Load = signal-weighted count of overlapping radios.')


def print_report(report: dict):
    summary = report['summary']
    settings = report['settings']
    block_title('Report', 'magenta')
    print(f'Test:     {settings["test_name"]}' + (f' @ {settings["location"]}' if settings['location'] else ''))
    print(f'Period:   {_clock(report["started_at"])} - {_clock(report["ended_at"])}')

    block_title('Findings', 'magenta')
    for finding in report['findings']:
        icon, name = LEVEL_STYLE[finding['level']]
        print(color(f'{icon} {finding["title"]}', name))
        print(f'  {finding["detail"]}')

    block_title('Network', 'magenta')
    headers = ['', '#', 'Avg', 'Median', 'Min', 'Max', 'Jitter', 'Loss']
    rows = [[name, s['attempts'], *(_num(s[k], s['unit']) for k in ('avg', 'median', 'min', 'max', 'jitter')),
             f'{s["loss"]:.0%}'] for name, s in summary['network'].items()]
    print(tabulate(rows, headers, colalign=('left',) + ('right',) * 7))

    if summary['link']:
        block_title('Wi-Fi', 'magenta')
        rows = [[name, s['attempts'], *(_num(s[k], s['unit']) for k in ('avg', 'median', 'min', 'max'))]
                for name, s in summary['link'].items()]
        print(tabulate(rows, headers[:6], colalign=('left',) + ('right',) * 5))
        print(f'\nAccess points: {", ".join(summary["access_points"]) or "unknown"}  '
              f'Roams: {summary["roams"]}  Drops: {summary["drops"]}  Bands: {", ".join(summary["bands"])}')


class TerminalEvents:
    def __init__(self):
        self.link = None
        self.header_printed = False

    def emit(self, event: str, data: dict):
        if event == 'started':
            targets = ', '.join(f'{name} {host}' for name, host in data['targets'].items())
            print(f'Pinging: {targets}')
        elif event == 'channels':
            print_channels(data)
        elif event == 'link':
            self.link = data
        elif event == 'probe':
            self._print_probe(data)
        elif event == 'roam':
            print(color(f'Roamed {data["from"]} → {data["to"]} (ch {data["channel"]}, {data["signal"]} dBm)', 'yellow'))
        elif event == 'speedtest':
            print(color(f'Speedtest: {_num(data["download"], "Mbps")} down / {_num(data["upload"], "Mbps")} up', 'magenta'))
        elif event == 'notice':
            print(data['message'])
        elif event == 'report':
            print_report(data)

    def _print_probe(self, probe: dict):
        if not self.header_printed:
            print()
            TABLE.print_header()
            self.header_printed = True
        link = self.link or {}
        ms = probe['ms']
        TABLE.print_row(
            probe['clock'],
            probe['series'],
            probe['target'] or '-',
            (_num(ms, 'ms') if ms is not None else 'FAILED', 'red' if ms is None or ms > 300 else 'yellow' if ms > 150 else None),
            f'{link["signal"]} dBm' if link.get('signal') is not None else '-',
            f'{link["channel"]} ({link["width"]} MHz)' if link.get('channel') else '-',
        )


def _stop_on_enter(analysis: Analysis):
    while True:
        if select.select([sys.stdin], [], [], 0.5)[0]:
            sys.stdin.readline()
            analysis.stop()
            return


def _num(value: float | None, unit: str) -> str:
    return f'{value:.0f} {unit}' if value is not None else '-'


def _clock(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
