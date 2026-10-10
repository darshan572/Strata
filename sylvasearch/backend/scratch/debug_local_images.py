import sys
sys.path.insert(0, ".")
from app.database import get_connection
import re

query_text = "LinkedIn"
q_words = [w for w in re.findall(r"\b[a-zA-Z0-9]+\b", query_text.lower()) if len(w) > 1]
where_clauses = ["title LIKE ? OR alt_text LIKE ? OR source_page_url LIKE ?"]
params = [f"%{query_text}%", f"%{query_text}%", f"%{query_text}%"]
for w in q_words[:3]:
    where_clauses.append("title LIKE ? OR alt_text LIKE ?")
    params.extend([f"%{w}%", f"%{w}%"])

query_sql = f"""
    SELECT id, source_page_url as url, image_url, title, alt_text, width, height
    FROM images
    WHERE {' OR '.join(where_clauses)}
    LIMIT 40
"""
conn = get_connection()
rows = conn.execute(query_sql, params).fetchall()
conn.close()
print("Returned rows from DB query:", [dict(r) for r in rows])
