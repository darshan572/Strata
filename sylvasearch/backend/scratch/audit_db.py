import sqlite3
import shutil
import datetime
import os

src = "data/sylvasearch.db"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
dst = f"data/sylvasearch_audit_backup_{ts}.db"
shutil.copy2(src, dst)
print(f"Created backup: {dst} ({os.path.getsize(dst)} bytes)")

conn = sqlite3.connect(src)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

tables = [row["name"] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"Tables in database: {tables}")

for t in tables:
    count = cursor.execute(f"SELECT count(*) as c FROM {t}").fetchone()["c"]
    print(f"  Table '{t}': {count} records")

# Inspect documents table: highest IDs and any recent inserts
print("\n--- Recent / High-ID Documents ---")
high_docs = cursor.execute("SELECT id, url, title, length(content) as content_len FROM documents ORDER BY id DESC LIMIT 10").fetchall()
for d in high_docs:
    print(f"  Doc ID {d['id']}: {d['url']} | Title: {d['title']} | Len: {d['content_len']}")

# Inspect images schema & table
print("\n--- Images Table Schema & Content ---")
img_cols = cursor.execute("PRAGMA table_info(images)").fetchall()
print("Images cols:", [c["name"] for c in img_cols])
imgs = cursor.execute("SELECT * FROM images").fetchall()
for im in imgs:
    print(f"  Image: {dict(im)}")

# Inspect videos schema & table
print("\n--- Videos Table Schema & Content ---")
vid_cols = cursor.execute("PRAGMA table_info(videos)").fetchall()
print("Videos cols:", [c["name"] for c in vid_cols])
vids = cursor.execute("SELECT * FROM videos LIMIT 10").fetchall()
for v in vids:
    print(f"  Video: {dict(v)}")

conn.close()
