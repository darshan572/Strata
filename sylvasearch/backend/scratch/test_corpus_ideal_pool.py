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
    {
        "query": "LinkedIn",
        "intent": "navigational",
        "eval_fn": lambda url: 2.0 if any(url.rstrip("/").endswith(d) or "login" in url for d in ["linkedin.com", "linkedin.com/login", "fr.linkedin.com", "nl.linkedin.com", "br.linkedin.com"]) else (1.0 if any(k in url for k in ["company/linkedin", "wiki/LinkedIn", "LinkedIn_Learning", "Timeline_of_LinkedIn"]) else 0.0),
        "forbidden_top": "wikipedia.org",
    },
    {
        "query": "LinkedIn login",
        "intent": "navigational",
        "eval_fn": lambda url: 2.0 if "linkedin.com/login" in url else (1.0 if (url.rstrip("/").endswith("linkedin.com") or any(k in url for k in ["fr.linkedin.com", "nl.linkedin.com", "br.linkedin.com"])) else 0.0),
        "forbidden_top": "wikipedia.org",
    },
    {
        "query": "what is LinkedIn",
        "intent": "informational",
        "eval_fn": lambda url: 2.0 if ("whatis" in url or "wiki/LinkedIn" in url) else (1.0 if any(k in url for k in ["Timeline_of_LinkedIn", "LinkedIn_Learning"]) else 0.0),
        "forbidden_top": "linkedin.com/login",
    },
    {
        "query": "LinkedIn history",
        "intent": "informational",
        "eval_fn": lambda url: 2.0 if "Timeline_of_LinkedIn" in url else (1.0 if "wiki/LinkedIn" in url else 0.0),
        "forbidden_top": "linkedin.com/login",
    },
    {
        "query": "Python",
        "intent": "navigational",
        "eval_fn": lambda url: 2.0 if (url.rstrip("/").endswith("python.org") or "downloads" in url) else (1.0 if "python.org" in url else 0.0),
        "forbidden_top": "wikipedia.org",
    },
    {
        "query": "Python beginner tutorial",
        "intent": "informational",
        "eval_fn": lambda url: 2.0 if "tutorial" in url else (1.0 if any(k in url for k in ["about/help", "doc", "getting-started"]) else 0.0),
        "forbidden_top": "linkedin.com",
    },
    {
        "query": "latest AI news",
        "intent": "news",
        "eval_fn": lambda url: 2.0 if ("news.mit.edu" in url and "artificial-intelligence" in url) else (1.0 if "scikit-learn" in url else 0.0),
        "forbidden_top": "linkedin.com",
    },
]

rrs, p10s, ndcgs = [], [], []
for b in benchmarks:
    results = engine.search(b["query"])[:10]
    grades = [b["eval_fn"](r["url"]) for r in results]
    first_rank = next((idx for idx, g in enumerate(grades, 1) if g >= 1.0), None)
    mrr = (1.0 / first_rank) if first_rank else 0.0
    p10 = sum(1 for g in grades if g >= 1.0) / max(1, len(results))
    
    # Standard IR nDCG: Ideal ranking is the top 10 grades across the entire corpus
    all_corpus_grades = sorted([b["eval_fn"](r["url"]) for r in rows], reverse=True)[:10]
    idcg = sum((2**g - 1) / math.log2(idx + 1) for idx, g in enumerate(all_corpus_grades, 1))
    dcg = sum((2**g - 1) / math.log2(idx + 1) for idx, g in enumerate(grades, 1))
    ndcg = (dcg / idcg) if idcg > 0 else 0.0
    
    rrs.append(mrr)
    p10s.append(p10)
    ndcgs.append(ndcg)
    assert 0.0 <= ndcg <= 1.0, f"nDCG {ndcg} must be in [0, 1] for {b['query']}"
    print(f"{b['query']:<25}: MRR={mrr:.4f}, P@10={p10:.4f}, nDCG@10={ndcg:.4f} (DCG={dcg:.2f}, IDCG={idcg:.2f})")

print(f"\nMean MRR:          {sum(rrs)/len(rrs):.4f}")
print(f"Mean Precision@10: {sum(p10s)/len(p10s):.4f}")
print(f"Mean nDCG@10:      {sum(ndcgs)/len(ndcgs):.4f}")
