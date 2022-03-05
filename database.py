import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

class DB:
    def save(username, user_id, wallet, tx_hash):
        with conn:
                rows = [(username, user_id, wallet, tx_hash)]
                cursor.executemany('insert into users values (?,?,?,?)', rows)
                conn.commit()