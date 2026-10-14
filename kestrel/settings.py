from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / 'kestrel.db'

PING_TARGETS = {'google': '8.8.8.8', 'cloudflare': '1.1.1.1', 'dr': 'dr.dk'}  # Router and ISP hop are added at runtime
DNS_TARGETS = {'google': 'google.com', 'dr': 'dr.dk'}
LINK_POLL_SECONDS = 2
SPEEDTEST_FIRST_AFTER = 20  # Seconds of idle baseline before loading the link
SPEEDTEST_EVERY = 60


@dataclass
class Settings:
    test_name: str = 'Unknown'
    location: str = ''
    duration: int = 300  # Seconds
    run_speedtests: bool = True
    pause_between_rounds: float = 1  # Seconds
