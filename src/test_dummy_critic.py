
import sqlite3
def get_conn():
    conn = sqlite3.connect('/tmp/test.db')  # FM-002: module-level, no lock
    return conn

def run_query(sql):
    conn = get_conn()
    return conn.execute(sql).fetchall()
