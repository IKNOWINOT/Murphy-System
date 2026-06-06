import sqlite3

def trigger_refresh():
    conn = sqlite3.connect('src/db/crm.db')
    c = conn.cursor()
    c.execute('UPDATE crm_activities SET needs_copy_refresh = 1 WHERE activity_type = "APC outreach"')
    conn.commit()
    conn.close()
