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
        "doc_grades": {
            471: 2.0, 472: 2.0, 476: 2.0, 477: 2.0, 478: 2.0, # Official portals
            474: 1.0, 479: 1.0, 483: 1.0, 484: 1.0, 485: 1.0, 487: 1.0 # Topical subpages
        }
    },
    {
        "query": "LinkedIn login",
        "doc_grades": {
            472: 2.0, # exact login
            471: 1.0, 476: 1.0, 477: 1.0, 478: 1.0 # homepage/international login
        }
    },
    {
        "query": "what is LinkedIn",
        "doc_grades": {
            475: 2.0, 479: 2.0, # TechTarget definition + Wikipedia article
            487: 1.0, 483: 1.0
        }
    },
    {
        "query": "LinkedIn history",
        "doc_grades": {
            487: 2.0, # Timeline of LinkedIn
            479: 1.0  # Wikipedia overview
        }
    }
]

for b in benchmarks:
    results = engine.search(b["query"])[:10]
    grades = [b["doc_grades"].get(r["id"], 0.0) for r in results]
    
    # 1. Standard MRR: first rank where grade >= 1.0
    first_rank = next((idx for idx, g in enumerate(grades, 1) if g >= 1.0), None)
    mrr = (1.0 / first_rank) if first_rank else 0.0
    
    # 2. Precision@10
    p10 = sum(1 for g in grades if g >= 1.0) / max(1, len(results))
    
    # 3. Standard nDCG@10 using ground-truth ideal pool
    dcg = sum((2**g - 1) / math.log2(idx + 1) for idx, g in enumerate(grades, 1))
    all_corpus_grades = sorted(b["doc_grades"].values(), reverse=True)[:10]
    idcg = sum((2**g - 1) / math.log2(idx + 1) for idx, g in enumerate(all_corpus_grades, 1))
    ndcg = (dcg / idcg) if idcg > 0 else 0.0
    
    print(f"{b['query']:<20}: MRR={mrr:.4f}, P@10={p10:.4f}, nDCG@10={ndcg:.4f} (DCG={dcg:.2f}, IDCG={idcg:.2f})")
