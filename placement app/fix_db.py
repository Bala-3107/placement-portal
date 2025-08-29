import sqlite3

conn = sqlite3.connect('database.db')
try:
    conn.execute("ALTER TABLE jobs ADD COLUMN location TEXT")
    print("Column 'location' added successfully.")
except sqlite3.OperationalError as e:
    print("Error:", e)  # Likely means column already exists
finally:
    conn.commit()
    conn.close()
