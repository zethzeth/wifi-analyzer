# Runs one analysis: a link poller, a ping/DNS loop and a speedtest loop side by side.
# Everything it observes goes out through `emit(event, data)`, so the terminal and the Electron app share it.
import threading
import time
from datetime import datetime
from typing import Callable

from kestrel import channels, platforms, probes
from kestrel.db import AnalysisLog
from kestrel.diagnosis import diagnose
from kestrel.models import Connection, Link
from kestrel.results import Results
from kestrel.settings import DNS_TARGETS, LINK_POLL_SECONDS, PING_TARGETS, SPEEDTEST_EVERY, SPEEDTEST_FIRST_AFTER, Settings

Emit = Callable[[str, dict], None]


class Analysis:
    def __init__(self, settings: Settings, connection: Connection, emit: Emit):
        self.settings = settings
        self.connection = connection
        self.emit = emit
        self.ping_targets: dict[str, str | None] = {}  # Filled in by run(), once the ISP hop is known
        self.results = Results()
        self.link: Link = connection.link
        self.speedtest_running = False
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self) -> dict:
        self.emit('notice', {'message': 'Finding the ISP hop...'})
        isp = probes.isp_hop()
        self.ping_targets = {'router': self.connection.router_ip, **({'isp': isp} if isp else {}), **PING_TARGETS}

        started_at = time.time()
        self.emit('started', {'settings': vars(self.settings), 'connection': self.connection.to_dict(),
                              'targets': self.ping_targets, 'dns_targets': DNS_TARGETS,
                              'started_at': started_at})

        # Scan before probing starts: a scan takes the radio off-channel and would show up as latency spikes
        channel_report = None
        if self.connection.link.wireless:
            channel_report = channels.analyse(platforms.networks(), self.connection.link)
            self.emit('channels', channel_report)

        log = AnalysisLog(self.settings)
        loops = [self._link_loop, self._probe_loop] + ([self._speedtest_loop] if self.settings.run_speedtests else [])
        threads = [threading.Thread(target=loop, args=(log,), daemon=True) for loop in loops]
        for thread in threads:
            thread.start()

        try:
            self._stop.wait(self.settings.duration)
        except KeyboardInterrupt:
            pass
        self._stop.set()
        if self.speedtest_running:
            self.emit('notice', {'message': 'Waiting for the running speedtest to finish...'})
        for thread in threads:
            thread.join()
        log.close()

        summary = self.results.summary()
        report = {
            'settings': vars(self.settings),
            'started_at': started_at,
            'ended_at': time.time(),
            'connection': self.connection.to_dict(),
            'summary': summary,
            'findings': diagnose(summary, channel_report, self.connection.to_dict()),
        }
        self.emit('report', report)
        return report

    def _link_loop(self, log: AnalysisLog):
        while not self._stop.is_set():
            self.link = platforms.link(self.connection.interface)
            previous = self.results.add_link(self.link)
            log.log_link(self.link)
            self.emit('link', {'time': time.time(), **self.link.to_dict()})
            if previous:
                self.emit('roam', {'time': time.time(), 'from': previous, 'to': self.link.bssid,
                                   'signal': self.link.signal, 'channel': self.link.channel})
            self._stop.wait(LINK_POLL_SECONDS)

    def _probe_loop(self, log: AnalysisLog):
        while not self._stop.is_set():
            for name, host in self.ping_targets.items():
                self._record(log, 'ping', name, host, probes.ping(host))
            for name, domain in DNS_TARGETS.items():
                self._record(log, 'dns', name, domain, probes.resolve(domain, self.connection.dns_server))
            self._stop.wait(self.settings.pause_between_rounds)

    # Spaced out so most probes measure the idle link, and the rest show how it copes under load
    def _speedtest_loop(self, log: AnalysisLog):
        self._stop.wait(SPEEDTEST_FIRST_AFTER)
        while not self._stop.is_set():
            self.speedtest_running = True
            self.emit('speedtest_started', {'time': time.time()})
            download, upload = probes.speeds()
            self.speedtest_running = False
            for name, value in (('download', download), ('upload', upload)):
                self.results.add(name, value, 'Mbps')
                log.log(name, 'speedtest.net', value)
            self.emit('speedtest', {'time': time.time(), 'download': download, 'upload': upload})
            self._stop.wait(SPEEDTEST_EVERY)

    def _record(self, log: AnalysisLog, kind: str, name: str, target: str | None, ms: float | None):
        # Probes during a speedtest go in their own series: latency under load (bufferbloat) vs. idle
        series = f'{kind} {name}' + (' under load' if self.speedtest_running else '')
        self.results.add(series, ms, 'ms')
        log.log(kind, target, ms)
        self.emit('probe', {
            'time': time.time(), 'clock': datetime.now().strftime('%H:%M:%S'), 'kind': kind, 'name': name,
            'series': series, 'target': target, 'ms': ms, 'loaded': self.speedtest_running,
        })
