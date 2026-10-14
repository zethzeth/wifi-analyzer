import sqlite3
import threading

from kestrel.models import Link
from kestrel.settings import DB_PATH, Settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY,
    name TEXT,
    location TEXT,
    domain TEXT DEFAULT "google.com",
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER,
    event_type TEXT,
    result REAL,
    succeeded INTEGER,
    target TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);
CREATE TABLE IF NOT EXISTS link_samples (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER,
    bssid TEXT,
    signal INTEGER,
    noise INTEGER,
    channel INTEGER,
    band TEXT,
    tx_rate REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);
"""


class AnalysisLog:
    """One analysis row plus its log rows, written from several threads."""

    def __init__(self, settings: Settings, path=DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.conn.executescript(SCHEMA)
        self.analysis_id = self.conn.execute(
            'INSERT INTO analyses (name, location) VALUES (?, ?)', (settings.test_name, settings.location),
        ).lastrowid
        self.conn.commit()

    def log(self, event_type: str, target: str | None, result: float | None):
        self._write(
            'INSERT INTO logs (analysis_id, event_type, result, target, succeeded) VALUES (?, ?, ?, ?, ?)',
            (self.analysis_id, event_type, result, target, int(result is not None)),
        )

    def log_link(self, link: Link):
        self._write(
            'INSERT INTO link_samples (analysis_id, bssid, signal, noise, channel, band, tx_rate) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (self.analysis_id, link.bssid, link.signal, link.noise, link.channel, link.band, link.tx_rate),
        )

    def _write(self, sql: str, params: tuple):
        with self.lock:
            self.conn.execute(sql, params)
            self.conn.commit()

    def close(self):
        self.conn.close()
