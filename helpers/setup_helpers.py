import os
from dotenv import load_dotenv
import sqlite3

load_dotenv()


def setup_db():
    conn = sqlite3.connect(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()

    # Creating table for user inputs
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS user_inputs (
        id INTEGER PRIMARY KEY,
        location TEXT,
        domain TEXT DEFAULT "google.com",
        test_name TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )"""
    )

    # Creating table for connection logs
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY,
        user_input_id INTEGER,
        ping_response_time TEXT,
        dns_resolution_time TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_input_id) REFERENCES user_inputs(id)
    )"""
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    setup_db()
    print("Database initialized successfully!")
