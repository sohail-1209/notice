import sqlite3

conn = sqlite3.connect('database/notices.db')
cursor = conn.cursor()

cursor.execute("ALTER TABLE notices ADD COLUMN category TEXT DEFAULT 'General'")
conn.commit()
conn.close()

print("✅ Category column added.")
