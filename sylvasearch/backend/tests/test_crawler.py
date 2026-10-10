from app.crawler.crawler import Crawler
from app.url_utils import is_safe_url, canonicalize_url


def test_is_safe_url_blocks_dangerous_destinations():
    assert is_safe_url("http://127.0.0.1") is False
    assert is_safe_url("http://localhost:8000") is False
    assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False
    assert is_safe_url("http://10.0.0.1/admin") is False
    assert is_safe_url("http://192.168.1.100") is False
    assert is_safe_url("ftp://example.com/file") is False
    assert is_safe_url("file:///etc/passwd") is False


def test_is_safe_url_allows_public_https_domains():
    assert is_safe_url("https://www.python.org") is True
    assert is_safe_url("https://en.wikipedia.org/wiki/Search_engine") is True
    assert is_safe_url("https://example.com/docs") is True


def test_canonicalize_url():
    # Fragment removal and lowercasing
    assert canonicalize_url("https://Example.COM/Path#section") == "https://example.com/Path"
    # Default port removal
    assert canonicalize_url("http://example.com:80/index") == "http://example.com/index"
    assert canonicalize_url("https://example.com:443/index") == "https://example.com/index"


def test_crawler_url_normalization_and_domain_check():
    crawler = Crawler(allowed_domain="example.com")
    normalized = crawler.normalize_url("https://Example.COM/page#anchor")
    assert normalized == "https://example.com/page"
    assert crawler.is_allowed_domain("https://example.com/allowed") is True
    assert crawler.is_allowed_domain("https://otherdomain.org/denied") is False
