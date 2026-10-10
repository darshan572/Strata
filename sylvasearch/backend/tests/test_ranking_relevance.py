import pytest
import math
from app.search.engine import SearchEngine
from app.indexer.index import InvertedIndex
from app.database import get_connection
from app.main import load_page_ranks


@pytest.fixture(scope="module")
def populated_engine():
    index = InvertedIndex()
    conn = get_connection()
    rows = conn.execute("SELECT id, title, content, url FROM documents").fetchall()
    for r in rows:
        index.add_document(
            r["id"],
            {"title": r["title"] or "", "text": r["content"] or "", "url": r["url"]}
        )
    conn.close()
    page_ranks = load_page_ranks()
    return SearchEngine(index, page_ranks)


class TestPrincipledSearchRanking:
    """Deterministic regression test suite for navigational vs informational ranking."""

    def test_linkedin_navigational_ranks_official_domain(self, populated_engine):
        results = populated_engine.search("LinkedIn")
        assert len(results) > 0, "Expected search results for 'LinkedIn'"
        top = results[0]
        # Official domain must be #1, ahead of Wikipedia or third party profiles
        assert "linkedin.com" in top["url"].lower(), f"Expected linkedin.com #1, got {top['url']}"
        assert "wikipedia.org" not in top["url"].lower(), "Wikipedia should not rank above official LinkedIn for navigational search"

    def test_linkedin_login_ranks_login_page_first(self, populated_engine):
        results = populated_engine.search("LinkedIn login")
        assert len(results) > 0
        top = results[0]
        assert "linkedin.com/login" in top["url"].lower(), f"Expected login page #1, got {top['url']}"

    def test_what_is_linkedin_informational_outranks_bare_login(self, populated_engine):
        results = populated_engine.search("what is LinkedIn")
        assert len(results) > 0
        top = results[0]
        # An explanatory / definition article must rank #1
        assert "whatis" in top["url"].lower() or "techtarget" in top["url"].lower() or "definition" in top["title"].lower(), (
            f"Expected explanatory article for informational query, got: {top['title']} ({top['url']})"
        )
        # Bare login page must NOT rank #1 for informational search
        assert "linkedin.com/login" not in top["url"].lower(), "Bare login page should not outrank explanatory article for 'what is LinkedIn'"



class TestRankingEvaluationMetrics:
    """Evaluation suite calculating Precision@10, MRR, and nDCG@10 across benchmarks."""

    GOLDEN_EVAL_SET = [
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

    def test_precision_mrr_and_ndcg(self, populated_engine):
        reciprocal_ranks = []
        precision_at_10_list = []
        ndcg_list = []

        conn = get_connection()
        corpus_rows = conn.execute("SELECT id, url, title FROM documents").fetchall()
        conn.close()

        for item in self.GOLDEN_EVAL_SET:
            results = populated_engine.search(item["query"])
            top_10 = results[:10]

            # Relevance grades of retrieved documents
            grades = [item["eval_fn"](r["url"]) for r in top_10]

            # 1. Standard MRR: Reciprocal rank of the FIRST relevant document (grade >= 1.0)
            # Standard IR definition: does NOT skip earlier relevant documents to prefer later ones
            first_rank = next((idx for idx, g in enumerate(grades, 1) if g >= 1.0), None)
            reciprocal_ranks.append(1.0 / first_rank if first_rank else 0.0)

            # 2. Precision@10: Fraction of retrieved top-10 that are relevant
            relevant_count = sum(1 for g in grades if g >= 1.0)
            precision_at_10_list.append(relevant_count / max(1, len(top_10)))

            # 3. Standard nDCG@10:
            # Ideal DCG is computed from the top-10 grades across the ENTIRE corpus of documents,
            # correctly penalizing the search engine for unretrieved relevant documents.
            all_corpus_grades = sorted([item["eval_fn"](r["url"]) for r in corpus_rows], reverse=True)[:10]
            idcg = sum((2**g - 1) / math.log2(idx + 1) for idx, g in enumerate(all_corpus_grades, 1))
            dcg = sum((2**g - 1) / math.log2(idx + 1) for idx, g in enumerate(grades, 1))
            ndcg = (dcg / idcg) if idcg > 0 else 0.0

            # Mathematical invariant: nDCG must strictly reside in [0.0, 1.0]
            assert 0.0 <= ndcg <= 1.0, f"nDCG {ndcg} must be bounded in [0.0, 1.0] for query {item['query']}"
            ndcg_list.append(ndcg)

            # Ensure forbidden top result did NOT win
            if top_10:
                assert item["forbidden_top"] not in top_10[0]["url"], (
                    f"Forbidden result {item['forbidden_top']} was #1 for {item['query']}"
                )

        mean_reciprocal_rank = sum(reciprocal_ranks) / len(reciprocal_ranks)
        mean_precision_at_10 = sum(precision_at_10_list) / len(precision_at_10_list)
        mean_ndcg = sum(ndcg_list) / len(ndcg_list)

        print(f"\n--- INTENT BENCHMARK EVALUATION REPORT ---")
        print(f"Mean Reciprocal Rank (MRR): {mean_reciprocal_rank:.4f}")
        print(f"Mean Precision@10: {mean_precision_at_10:.4f}")
        print(f"Mean nDCG@10: {mean_ndcg:.4f}")

        # Strict quality assertions
        assert mean_reciprocal_rank >= 0.85, f"MRR {mean_reciprocal_rank} is below benchmark 0.85"
        assert 0.0 <= mean_ndcg <= 1.0, f"Mean nDCG {mean_ndcg} must be bounded in [0.0, 1.0]"
        assert mean_ndcg >= 0.65, f"nDCG {mean_ndcg} is below benchmark 0.65"

    def test_persistent_corpus_labeled_benchmarks(self, populated_engine):
        """Evaluate naturally crawled corpus using data/ranking_eval.json ground-truth doc IDs."""
        import json
        from pathlib import Path

        labels_path = Path(__file__).resolve().parents[1] / "data" / "ranking_eval.json"
        if not labels_path.exists():
            pytest.skip("ranking_eval.json not found")

        cases = json.loads(labels_path.read_text(encoding="utf-8-sig"))
        precisions, reciprocal_ranks, ndcgs = [], [], []

        for case in cases:
            results = populated_engine.search(case["query"])
            top_10 = results[:10]
            relevant_ids = set(case["relevant_ids"])

            # Precision@10
            p10 = sum(1 for r in top_10 if r["id"] in relevant_ids) / max(1, len(top_10))
            precisions.append(p10)

            # Standard MRR: first retrieved document in ground-truth set
            first_rank = next((idx for idx, r in enumerate(top_10, 1) if r["id"] in relevant_ids), None)
            rr = (1.0 / first_rank) if first_rank else 0.0
            reciprocal_ranks.append(rr)

            # Standard nDCG@10: IDCG from ground-truth relevant count
            dcg = sum(1.0 / math.log2(idx + 1) for idx, r in enumerate(top_10, 1) if r["id"] in relevant_ids)
            num_ideal = min(10, len(relevant_ids))
            idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, num_ideal + 1)) if num_ideal > 0 else 0.0
            ndcg = (dcg / idcg) if idcg > 0 else 0.0
            assert 0.0 <= ndcg <= 1.0
            ndcgs.append(ndcg)

        mean_p10 = sum(precisions) / len(precisions)
        mean_rr = sum(reciprocal_ranks) / len(reciprocal_ranks)
        mean_ndcg = sum(ndcgs) / len(ndcgs)

        print(f"\n--- NATURALLY CRAWLED CORPUS BENCHMARK REPORT ---")
        print(f"Mean P@10:    {mean_p10:.4f}")
        print(f"Mean MRR:     {mean_rr:.4f}")
        print(f"Mean nDCG@10: {mean_ndcg:.4f}")

        assert mean_rr >= 0.70, f"Corpus MRR {mean_rr} below 0.70"
        assert mean_ndcg >= 0.50, f"Corpus nDCG {mean_ndcg} below 0.50"
