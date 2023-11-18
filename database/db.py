import os
import sqlite3

from dotenv import load_dotenv

from core.analysis_state import AnalysisState

load_dotenv()
DATABASE_NAME = os.getenv("DATABASE_NAME")


def add_log_to_db(event_type, result, target, succeeded=1):
    state = AnalysisState()
    analysis_id = state.analysis_id

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (analysis_id, event_type, result, target, succeeded) VALUES (?, ?, ?, ?, ?)",
        (analysis_id, event_type, result, target, succeeded),
    )
    conn.commit()
    conn.close()


def get_connection():
    return sqlite3.connect(DATABASE_NAME)


def setup_db():
    conn = sqlite3.connect(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()

    # Creating table for user inputs
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY,
            name TEXT,
            location TEXT,
            domain TEXT DEFAULT "google.com",
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS routers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            ip TEXT,
            mac_address TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    # Creating table for connection logs
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY,
            analysis_id INTEGER,
            event_type TEXT,
            result REAL,
            succeeded INTEGER,
            target TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        )"""
    )

    conn.commit()
    conn.close()
