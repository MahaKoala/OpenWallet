import sqlite3
import os

SQLITE_DB_FILE = os.path.dirname(
    os.path.realpath(__file__)) + "/data/wallets.db"

if __name__ == '__main__':
    if not os.path.exists(SQLITE_DB_FILE):
        with sqlite3.connect(SQLITE_DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE Wallets (id INTEGER PRIMARY KEY, network TEXT NOT NULL, mnemonic TEXT NOT NULL, label TEXT)")
            conn.commit()
