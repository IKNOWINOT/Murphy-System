import sqlite3

db = sqlite3.connect('crm.db')
c = db.cursor()

def get_inbound_replies():
    c.execute("SELECT * FROM activities WHERE date > DATE('now', '-999 days')")
    return c.fetchall()