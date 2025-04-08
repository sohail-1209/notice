import sqlite3
import os

DB_PATH = os.path.join('database', 'notices.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Add 'image' column if it doesn't already exist
try:
    cursor.execute("ALTER TABLE notices ADD COLUMN image TEXT")
    print("✅ 'image' column added successfully.")
except sqlite3.OperationalError as e:
    print("⚠️", e)

conn.commit()
conn.close()
