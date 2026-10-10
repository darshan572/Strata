from unittest.mock import patch

from app.crawler.web_retriever import WebRetriever
from app.indexer.index import InvertedIndex
from app.search.engine import SearchEngine


def test_tokenize():
    index = InvertedIndex()
    tokens = index.tokenize("Python Machine Learning!")
    assert "python" in tokens
    assert "machine" in tokens
    assert "learning" in tokens
    assert index.tokenize("") == []


def test_inverted_index_add_and_remove():
    index = InvertedIndex()
    doc_id = 999
    doc = {
        "title": "Natural Language Processing",
        "url": "https://example.com/nlp",
        "text": "NLP involves linguistics and machine learning.",
    }
    index.add_document(doc_id, doc)

    assert doc_id in index.index.get("linguistics", set())
    found = index.search("linguistics")
    assert len(found) == 1
    assert found[0]["url"] == "https://example.com/nlp"

    # Test clean removal
    index.remove_document(doc_id)
    assert doc_id not in index.index.get("linguistics", set())
    assert index.search("linguistics") == []


def test_search_engine_bm25_ranking():
    index = InvertedIndex()
    index.add_document(
        1,
        {
            "title": "Machine Learning in Python",
            "url": "https://example.com/ml-python",
            "text": "A comprehensive machine learning guide.",
        },
    )
    index.add_document(
        2,
        {
            "title": "Gardening Essentials",
            "url": "https://example.com/gardening",
            "text": "Cultivating flowers and organic vegetables.",
        },
    )

    engine = SearchEngine(index)
    results = engine.search("machine learning")
    assert len(results) >= 1
    assert results[0]["id"] == 1
    assert "ml-python" in results[0]["url"]


def test_search_engine_prefix_expansion():
    index = InvertedIndex()
    index.add_document(
        10,
        {
            "title": "Darshan Filmography",
            "url": "https://example.com/darshan",
            "text": "Darshan Thoogudeepa is a prominent cinema actor.",
        },
    )

    engine = SearchEngine(index)
    # Prefix query "darsha" expands to match "darshan"
    results = engine.search("darsha")
    assert len(results) > 0
    assert results[0]["id"] == 10
    assert "darshan" in results[0]["url"]


def test_web_retriever_safety_and_fallback():
    retriever = WebRetriever(timeout=1.0)
    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []

    # Verify graceful degradation on simulated network failure
    with patch("urllib.request.urlopen") as mock_fetch:
        mock_fetch.side_effect = Exception("Network offline")
        assert retriever.retrieve("test query") == []
