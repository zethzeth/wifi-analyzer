import statistics
from dataclasses import dataclass, field

from kestrel.models import Link

LINK_FIELDS = {'signal': 'dBm', 'noise': 'dBm', 'snr': 'dB', 'tx_rate': 'Mbit/s'}


@dataclass
class Series:
    unit: str
    values: list[float] = field(default_factory=list)
    failures: int = 0

    def add(self, value: float | None):
        if value is None:
            self.failures += 1
        else:
            self.values.append(value)

    @property
    def attempts(self) -> int:
        return len(self.values) + self.failures

    @property
    def jitter(self) -> float | None:
        """Mean change between consecutive samples, as in RFC 3550."""
        if len(self.values) < 2:
            return None
        return statistics.mean(abs(b - a) for a, b in zip(self.values, self.values[1:]))

    def summary(self) -> dict:
        values = self.values
        return {
            'unit': self.unit,
            'attempts': self.attempts,
            'avg': statistics.mean(values) if values else None,
            'median': statistics.median(values) if values else None,
            'min': min(values, default=None),
            'max': max(values, default=None),
            'jitter': self.jitter,
            'loss': self.failures / self.attempts if self.attempts else None,
        }


class Results:
    def __init__(self):
        self.network: dict[str, Series] = {}  # e.g. "ping router", "dns google", "download"
        self.link = {name: Series(unit) for name, unit in LINK_FIELDS.items()}
        self.bssids: list[str] = []  # Every access point we were associated with, in order
        self.roams = 0
        self.drops = 0  # Link readings where we weren't associated at all
        self.bands: set[str] = set()

    def add(self, name: str, value: float | None, unit: str):
        self.network.setdefault(name, Series(unit)).add(value)

    def add_link(self, link: Link) -> str | None:
        """Records a link reading; returns the previous BSSID when this reading is a roam."""
        if not link.wireless or link.signal is None:
            self.drops += 1
            return None
        # Missing readings are skipped rather than counted as failures, since drivers often never report them
        for name in self.link:
            value = getattr(link, name)
            if value is not None:
                self.link[name].add(value)
        if link.band:
            self.bands.add(link.band)
        if not link.bssid or (self.bssids and self.bssids[-1] == link.bssid):
            return None
        previous = self.bssids[-1] if self.bssids else None
        self.bssids.append(link.bssid)
        if previous:
            self.roams += 1
        return previous

    def summary(self) -> dict:
        return {
            'network': {name: series.summary() for name, series in self.network.items()},
            'link': {name: series.summary() for name, series in self.link.items() if series.values},
            'access_points': list(dict.fromkeys(self.bssids)),
            'roams': self.roams,
            'drops': self.drops,
            'bands': sorted(self.bands),
        }
