import threading, sqlite3
from pathlib import Path
_lock = threading.Lock()
_conn = None
def get_conn():
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(str(Path('/tmp/test.db')), check_same_thread=False)
        return _conn
def run_query(sql):
    with _lock:
        return get_conn().execute(sql).fetchall()
