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
        # Exact official portals (2.0), corporate/wiki subpages (1.0), user posts/court cases (0.0)
        "eval_fn": lambda url: 2.0 if any(url.rstrip("/").endswith(d) or "login" in url for d in ["linkedin.com", "linkedin.com/login"]) else (1.0 if any(k in url for k in ["company/linkedin", "wiki/LinkedIn", "LinkedIn_Learning", "Timeline_of_LinkedIn"]) else 0.0),
        "ideal_pool": [2.0, 2.0, 1.0, 1.0, 1.0, 1.0]
    },
    {
        "query": "LinkedIn login",
        "intent": "navigational",
        # Exact login page (2.0), homepage/auth portal (1.0), other pages (0.0)
        "eval_fn": lambda url: 2.0 if "linkedin.com/login" in url else (1.0 if (url.rstrip("/").endswith("linkedin.com") or "s'identifier" in url or "meld" in url) else 0.0),
        "ideal_pool": [2.0, 1.0, 1.0, 1.0, 1.0]
    },
    {
        "query": "what is LinkedIn",
        "intent": "informational",
        # TechTarget definition (2.0), Wikipedia overview (2.0), timeline/learning (1.0), login/posts (0.0)
        "eval_fn": lambda url: 2.0 if ("whatis" in url or "wiki/LinkedIn" in url) else (1.0 if any(k in url for k in ["Timeline_of_LinkedIn", "LinkedIn_Learning"]) else 0.0),
        "ideal_pool": [2.0, 2.0, 1.0, 1.0]
    },
    {
        "query": "LinkedIn history",
        "intent": "informational",
        # Timeline article (2.0), Wikipedia general article with history section (1.0), login/posts (0.0)
        "eval_fn": lambda url: 2.0 if "Timeline_of_LinkedIn" in url else (1.0 if "wiki/LinkedIn" in url else 0.0),
        "ideal_pool": [2.0, 1.0]
    },
    {
        "query": "Python",
        "intent": "navigational",
        # python.org home/downloads (2.0), official python docs/events (1.0), third-party/unrelated (0.0)
        "eval_fn": lambda url: 2.0 if (url.rstrip("/").endswith("python.org") or "python.org/downloads" in url) else (1.0 if "python.org" in url else 0.0),
        "ideal_pool": [2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    },
    {
        "query": "Python beginner tutorial",
        "intent": "informational",
        # Official tutorial (2.0), help/beginner docs (1.0), bare homepage (0.0)
        "eval_fn": lambda url: 2.0 if "tutorial" in url else (1.0 if any(k in url for k in ["about/help", "doc", "getting-started"]) else 0.0),
        "ideal_pool": [2.0, 1.0, 1.0, 1.0]
    },
    {
        "query": "latest AI news",
        "intent": "news",
        # MIT AI news (2.0), AI research articles (1.0), python homepage/unrelated (0.0)
        "eval_fn": lambda url: 2.0 if ("news.mit.edu" in url and "artificial-intelligence" in url) else (1.0 if "scikit-learn" in url else 0.0),
        "ideal_pool": [2.0, 1.0]
    }
]

for b in benchmarks:
    results = engine.search(b["query"])[:10]
    grades = [b["eval_fn"](r["url"].lower()) for r in results]
    
    first_rank = next((idx for idx, g in enumerate(grades, 1) if g >= 1.0), None)
    mrr = (1.0 / first_rank) if first_rank else 0.0
    p10 = sum(1 for g in grades if g >= 1.0) / max(1, len(results))
    
    dcg = sum((2**g - 1) / math.log2(idx + 1) for idx, g in enumerate(grades, 1))
    idcg = sum((2**g - 1) / math.log2(idx + 1) for idx, g in enumerate(sorted(b["ideal_pool"], reverse=True)[:10], 1))
    ndcg = (dcg / idcg) if idcg > 0 else 0.0
    
    assert 0.0 <= ndcg <= 1.0, f"nDCG {ndcg} not in [0, 1] for {b['query']}"
    print(f"{b['query']:<25}: MRR={mrr:.4f}, P@10={p10:.4f}, nDCG@10={ndcg:.4f} (DCG={dcg:.2f}, IDCG={idcg:.2f})")
