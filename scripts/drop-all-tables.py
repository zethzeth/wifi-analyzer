import os
from dotenv import load_dotenv
import sqlite3

load_dotenv()

DATABASE_NAME = os.getenv("DATABASE_NAME")


def drop_all_tables():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS analyses")
    cursor.execute("DROP TABLE IF EXISTS routers")
    cursor.execute("DROP TABLE IF EXISTS logs")

    conn.commit()
    conn.close()


drop_all_tables()
