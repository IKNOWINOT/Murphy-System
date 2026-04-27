import sqlite3

def get_conn():
    conn = sqlite3.connect('/tmp/test.db')
    return conn

def run_query(sql):
    return get_conn().execute(sql).fetchall()
