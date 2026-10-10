import sys
sys.path.insert(0, ".")
import math
from app.search.engine import SearchEngine
from app.indexer.index import InvertedIndex
from app.database import get_connection
from app.main import load_page_ranks

index = InvertedIndex()
conn = get_connection()
rows = conn.execute("SELECT id, title, content, url FROM documents").fetchall()
for r in rows:
    index.add_document(
        r["id"],
        {"title": r["title"] or "", "text": r["content"] or "", "url": r["url"]}
    )
conn.close()

engine = SearchEngine(index, load_page_ranks())

benchmarks = [
    {"query": "LinkedIn", "ideal": "linkedin.com", "type": "nav"},
    {"query": "LinkedIn login", "ideal": "linkedin.com/login", "type": "nav"},
    {"query": "what is LinkedIn", "ideal": "techtarget.com", "type": "info"},
    {"query": "LinkedIn history", "ideal": "Timeline_of_LinkedIn", "type": "info"},
    {"query": "Python", "ideal": "python.org", "type": "nav"},
    {"query": "Python beginner tutorial", "ideal": "python.org/3/tutorial", "type": "info"},
    {"query": "latest AI news", "ideal": "news.mit.edu", "type": "news"},
]

mrr_list = []
p10_list = []
ndcg_list = []

for b in benchmarks:
    res = engine.search(b["query"])[:10]
    # Standard multi-level relevance judgments:
    # 2.0 = exact ideal target result (e.g. official homepage/login or target definition/tutorial)
    # 1.0 = relevant topical match (subpage or authoritative guide)
    # 0.0 = non-matching / irrelevant
    rel_scores = []
    for r in res:
        url_lower = r["url"].lower()
        if b["ideal"].lower() in url_lower:
            rel_scores.append(2.0)
        elif b["type"] == "nav" and b["ideal"].split(".")[0].lower() in url_lower:
            rel_scores.append(1.0)
        elif b["type"] == "info" and ("wiki" in url_lower or "doc" in url_lower or "tutorial" in url_lower or "definition" in url_lower):
            rel_scores.append(1.0)
        elif b["type"] == "news" and "news" in url_lower:
            rel_scores.append(1.0)
        else:
            rel_scores.append(0.0)

    # 1. MRR
    first_rank = next((idx for idx, s in enumerate(rel_scores, 1) if s >= 2.0), None)
    if first_rank is None:
        first_rank = next((idx for idx, s in enumerate(rel_scores, 1) if s >= 1.0), None)
    mrr = (1.0 / first_rank) if first_rank else 0.0
    mrr_list.append(mrr)

    # 2. Precision@10
    p10 = sum(1 for s in rel_scores if s >= 1.0) / max(1, len(res))
    p10_list.append(p10)

    # 3. Standard nDCG@10 (mathematically guaranteed to be in [0.0, 1.0])
    dcg = sum((2**s - 1) / math.log2(idx + 1) for idx, s in enumerate(rel_scores, 1))
    ideal_scores = sorted(rel_scores, reverse=True)
    idcg = sum((2**s - 1) / math.log2(idx + 1) for idx, s in enumerate(ideal_scores, 1))
    ndcg = (dcg / idcg) if idcg > 0 else 0.0
    ndcg_list.append(ndcg)

    print(f"{b['query']:<28}: MRR={mrr:.4f}, P@10={p10:.4f}, nDCG@10={ndcg:.4f}")

print(f"\n--- EVALUATION SUMMARY ---")
print(f"Mean MRR:          {sum(mrr_list)/len(mrr_list):.4f}")
print(f"Mean Precision@10: {sum(p10_list)/len(p10_list):.4f}")
print(f"Mean nDCG@10:      {sum(ndcg_list)/len(ndcg_list):.4f}")
