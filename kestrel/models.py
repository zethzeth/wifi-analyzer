from dataclasses import asdict, dataclass


def band_for(freq_mhz: float | None = None, channel: int | None = None) -> str | None:
    if freq_mhz:
        return '2.4 GHz' if freq_mhz < 3000 else '5 GHz' if freq_mhz < 5925 else '6 GHz'
    if channel:
        return '2.4 GHz' if channel <= 14 else '5 GHz'  # Without a frequency, 6 GHz can't be told apart
    return None


@dataclass(frozen=True)
class Link:
    """The current association, as seen by this machine's adapter."""
    interface: str | None
    wireless: bool
    ssid: str | None = None
    bssid: str | None = None  # Which access point; changes when roaming
    signal: int | None = None  # dBm
    noise: int | None = None  # dBm; most Linux drivers don't expose it
    channel: int | None = None
    width: int | None = None  # MHz
    band: str | None = None
    tx_rate: float | None = None  # Mbit/s the adapter currently negotiates

    @property
    def snr(self) -> int | None:
        if self.signal is None or self.noise is None:
            return None
        return self.signal - self.noise

    def describe_snr(self) -> str:
        if self.snr is not None:
            return f'{self.snr} ({self.signal}, {self.noise})'
        return f'signal {self.signal}' if self.signal is not None else 'N/A'

    def describe_channel(self) -> str:
        if self.channel is None:
            return 'N/A'
        return f'{self.channel} ({self.width} MHz)' if self.width else str(self.channel)

    def to_dict(self) -> dict:
        return {**asdict(self), 'snr': self.snr}


@dataclass(frozen=True)
class Network:
    """One access point found in a scan."""
    ssid: str | None
    bssid: str | None
    channel: int
    band: str
    width: int  # MHz
    signal: int  # dBm
    in_use: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Connection:
    router_ip: str | None
    interface: str | None
    dns_server: str | None
    link: Link

    def to_dict(self) -> dict:
        return {**asdict(self), 'link': self.link.to_dict()}
