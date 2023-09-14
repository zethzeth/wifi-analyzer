import sqlite3

DATABASE_NAME = "wifi_analysis.db"

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Creating table for user inputs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_inputs (
        id INTEGER PRIMARY KEY,
        location TEXT,
        domain TEXT DEFAULT "google.com",
        test_name TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # Creating table for connection logs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY,
        user_input_id INTEGER,
        ping_response_time TEXT,
        dns_resolution_time TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_input_id) REFERENCES user_inputs(id)
    )''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
