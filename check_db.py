
import sqlite3

conn = sqlite3.connect("instance/app.db")
cursor = conn.cursor()

tables = cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

print("CÁC BẢNG TRONG DATABASE:")
for table in tables:
    print("-", table[0])

conn.close()
