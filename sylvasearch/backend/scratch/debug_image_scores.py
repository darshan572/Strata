import sys
sys.path.insert(0, ".")
from app.search.image_scorer import ImageRelevanceScorer
from app.database import get_connection

conn = get_connection()
row = conn.execute("SELECT * FROM images WHERE id = 1").fetchone()
conn.close()

local_cand = {
    "id": row["id"],
    "title": row["title"],
    "url": row["source_page_url"],
    "image_url": row["image_url"],
    "alt_text": row["alt_text"],
    "source_page_title": row["title"],
    "source": "Local Index",
    "width": row["width"],
    "height": row["height"],
}

hiq_court_seal = {
    "title": "Seal of the United States Courts, Ninth Judicial Circuit",
    "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/cf/Seal_of_the_United_States_Courts%2C_Ninth_Judicial_Circuit.svg/960px-Seal_of_the_United_States_Courts%2C_Ninth_Judicial_Circuit.svg.png",
    "alt_text": "Seal of the United States Courts, Ninth Judicial Circuit",
    "source_page_title": "HiQ Labs v. LinkedIn",
    "source": "Wikipedia",
    "width": 600,
    "height": 600
}

score_local = ImageRelevanceScorer.score_candidate("LinkedIn", local_cand)
score_seal = ImageRelevanceScorer.score_candidate("LinkedIn", hiq_court_seal)

print(f"Local brand logo score: {score_local}")
print(f"HiQ Court Seal score:   {score_seal}")
