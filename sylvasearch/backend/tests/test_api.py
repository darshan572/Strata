from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "SylvaSearch is running!"
    assert data["status"] == "online"
    assert "indexed_documents" in data


def test_search_valid_query():
    response = client.get("/search", params={"q": "python"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "results" in data
    assert "total_results" in data
    assert data["query"] == "python"
    assert data["limit"] <= 15
    assert len(data["results"]) <= 15


def test_search_empty_query():
    response = client.get("/search", params={"q": ""})
    assert response.status_code == 422


def test_search_oversized_query():
    response = client.get("/search", params={"q": "a" * 301})
    assert response.status_code == 422


def test_search_pagination_caps_at_15():
    # Client requests limit=50, but backend MUST strictly cap to 15
    response = client.get("/search", params={"q": "python", "limit": 50})
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 15
    assert len(data["results"]) <= 15
    assert "page" in data
    assert "total_pages" in data
    assert "has_next" in data
    assert "has_prev" in data
    assert data["page"] == 1
    assert data["has_prev"] is False


def test_search_pagination_next_page():
    response_p1 = client.get("/search", params={"q": "python", "page": 1, "limit": 15})
    assert response_p1.status_code == 200
    data1 = response_p1.json()

    if data1["total_pages"] > 1:
        response_p2 = client.get("/search", params={"q": "python", "page": 2, "limit": 15})
        assert response_p2.status_code == 200
        data2 = response_p2.json()
        assert data2["page"] == 2
        assert data2["has_prev"] is True

        # Results across pages must not collide
        p1_urls = {r["url"] for r in data1["results"]}
        p2_urls = {r["url"] for r in data2["results"]}
        assert len(p1_urls.intersection(p2_urls)) == 0


def test_search_pagination_out_of_range():
    response = client.get("/search", params={"q": "python", "page": 9999})
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 9999
    assert data["results"] == []
    assert data["has_next"] is False


def test_search_categories():
    # Images category
    res_img = client.get("/search", params={"q": "python", "category": "images"})
    assert res_img.status_code == 200
    data_img = res_img.json()
    assert data_img["category"] == "images"
    assert len(data_img["results"]) <= 15
    if data_img["results"]:
        assert data_img["results"][0]["media_type"] == "image"
        assert "thumbnail" in data_img["results"][0]

    # Videos category
    res_vid = client.get("/search", params={"q": "python", "category": "videos"})
    assert res_vid.status_code == 200
    data_vid = res_vid.json()
    assert data_vid["category"] == "videos"
    assert len(data_vid["results"]) <= 15
    if data_vid["results"]:
        assert data_vid["results"][0]["media_type"] == "video"
        assert "duration" in data_vid["results"][0]

    # News category
    res_news = client.get("/search", params={"q": "python", "category": "news"})
    assert res_news.status_code == 200
    data_news = res_news.json()
    assert data_news["category"] == "news"
    assert len(data_news["results"]) <= 15
    if data_news["results"]:
        assert data_news["results"][0]["media_type"] == "news"
        assert "publisher" in data_news["results"][0]


def test_suggest_endpoint():
    response = client.get("/suggest", params={"q": "darsh"})
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)


