import math
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urldefrag
from typing import Optional

from pathlib import Path
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.crawler.crawler import Crawler

from app.database import (
    get_all_documents,
    get_connection,
    initialize_database,
    enqueue_url,
    claim_next_url,
    mark_url_crawled,
    mark_url_failed,
    mark_url_permanently_failed,
    get_frontier_stats,
)

from app.indexer.index import InvertedIndex
from app.search.engine import SearchEngine
from app.search.pagerank import PageRank
from app.database import get_documents_by_urls

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="SylvaSearch",
    description="My own search engine",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

initialize_database()

index = InvertedIndex()
pagerank = PageRank()
search_engine = SearchEngine(index, {})


def load_page_ranks():
    """Calculate PageRank from links persisted in SQLite."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT source_url, target_url FROM links")
        rows = cursor.fetchall()
    finally:
        connection.close()

    links = [(row["source_url"], row["target_url"]) for row in rows]
    return pagerank.calculate(links)


def load_index():
    """Rebuild the in-memory index from persisted documents."""
    index.documents.clear()
    index.index.clear()

    for document in get_all_documents():
        index.add_document(
            document["id"],
            {
                "url": document["url"],
                "title": document["title"] or "",
                "text": document["content"] or "",
            },
        )


def refresh_index_documents(documents):
    """Refresh only persisted documents belonging to this crawl batch."""
    urls = {
        item.get("url")
        for item in documents
        if isinstance(item, dict) and item.get("url")
    }
    if not urls:
        return

    rows = get_documents_by_urls(urls)
    for document in rows:
        index.add_document(
            document["id"],
            {
                "url": document["url"],
                "title": document["title"] or "",
                "text": document["content"] or "",
            },
        )



def rebuild_search_state(documents=None):
    """Refresh search state incrementally, or fully rebuild when requested."""
    if documents is None:
        load_index()
    else:
        refresh_index_documents(documents)
    search_engine.page_ranks = load_page_ranks()


def validate_http_url(url: str) -> str:
    """Validate a seed URL and return its netloc, preventing SSRF to restricted networks."""
    from app.url_utils import is_safe_url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid URL: {url}. Use an http:// or https:// URL.",
        )
    if not is_safe_url(url):
        raise HTTPException(
            status_code=400,
            detail=f"Blocked unsafe destination: {url}. Crawling private or loopback networks is prohibited.",
        )
    return parsed.netloc


def save_crawled_documents(documents):
    """Insert new documents, refresh existing content, and replace outgoing links."""
    from app.url_utils import canonicalize_url

    # Normalize page URLs and outgoing links before persistence.
    normalized_documents = []
    for document in documents:
        try:
            document["url"] = canonicalize_url(document["url"])
        except (ValueError, KeyError, TypeError):
            continue

        normalized_links = []
        seen_links = set()
        for raw_link in document.get("links", []) or []:
            if not isinstance(raw_link, str):
                continue
            try:
                target = canonicalize_url(raw_link)
            except (ValueError, TypeError):
                continue
            if target not in seen_links:
                seen_links.add(target)
                normalized_links.append(target)

        document["links"] = normalized_links
        normalized_documents.append(document)

    documents[:] = normalized_documents
    connection = get_connection()
    new_documents = 0
    new_links = 0

    try:
        cursor = connection.cursor()

        for document in documents:
            url = document["url"]
            title = document.get("title", "")
            content = document.get("text", "")
            thumbnail = document.get("thumbnail")
            media_type = document.get("media_type", "web")
            published_at = document.get("published_at")
            publisher = document.get("publisher")

            # Insert new URLs; update content and metadata when the URL already exists.
            cursor.execute(
                """
                INSERT OR IGNORE INTO documents
                    (url, title, content, thumbnail, media_type, published_at, publisher)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (url, title, content, thumbnail, media_type, published_at, publisher),
            )

            if cursor.rowcount > 0:
                new_documents += 1
            else:
                cursor.execute(
                    """
                    UPDATE documents
                    SET title = ?, content = ?,
                        thumbnail = COALESCE(?, thumbnail),
                        media_type = COALESCE(?, media_type),
                        published_at = COALESCE(?, published_at),
                        publisher = COALESCE(?, publisher)
                    WHERE url = ?
                    """,
                    (title, content, thumbnail, media_type, published_at, publisher, url),
                )

            # Insert associated images into images table
            for img in document.get("images", []):
                img_url = img.get("image_url")
                if img_url:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO images
                            (source_page_url, image_url, alt_text, title, width, height)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            url,
                            img_url,
                            img.get("alt_text"),
                            img.get("title"),
                            img.get("width"),
                            img.get("height"),
                        ),
                    )

            # Insert associated videos into videos table
            for vid in document.get("videos", []):
                vid_url = vid.get("video_url")
                if vid_url:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO videos
                            (source_page_url, video_url, title, thumbnail_url, duration, publisher)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            url,
                            vid_url,
                            vid.get("title"),
                            vid.get("thumbnail_url"),
                            vid.get("duration"),
                            vid.get("publisher"),
                        ),
                    )

            # Replace this page's old outgoing links with its current links.
            cursor.execute(
                "SELECT target_url FROM links WHERE source_url = ?",
                (url,),
            )
            previous_links = {row[0] for row in cursor.fetchall()}

            current_links = list(dict.fromkeys(document.get("links", [])))

            cursor.execute(
                "DELETE FROM links WHERE source_url = ?",
                (url,),
            )

            if current_links:
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO links (source_url, target_url)
                    VALUES (?, ?)
                    """,
                    [(url, target) for target in current_links],
                )

            new_links += sum(
                1 for target in current_links
                if target not in previous_links
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return new_documents, new_links


# Restore the persistent corpus whenever the application starts.
rebuild_search_state()


@app.get("/")
def home():
    return {
        "message": "SylvaSearch is running!",
        "status": "online",
        "indexed_documents": len(index.documents),
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "message": "SylvaSearch is running!",
        "status": "online",
        "indexed_documents": len(index.documents),
        "docs": "/docs",
    }



@app.get("/crawl")
def crawl(url: str):
    """Crawl one domain, save its pages, and refresh the search index."""
    domain = validate_http_url(url)
    crawler = Crawler(
        max_pages=50,
        allowed_domain=domain,
        max_depth=2,
        delay=1.0,
    )

    try:
        crawl_result = crawler.crawl(url)
    finally:
        crawler.close()

    documents = crawl_result.get("documents", [])
    new_documents, new_links = save_crawled_documents(documents)
    rebuild_search_state(documents)

    return {
        "seed": url,
        "pages_crawled": len(documents),
        "new_documents": new_documents,
        "new_links": new_links,
        "links_found": sum(len(doc.get("links", [])) for doc in documents),
        "blocked_by_robots": crawl_result.get("blocked_by_robots", 0),
        "request_errors": crawl_result.get("request_errors", 0),
        "total_indexed_documents": len(index.documents),
    }


@app.get("/crawl-seeds")
def crawl_seeds(
    seeds: str,
    max_pages: int = Query(default=100, ge=1, le=500),
):
    """
    Crawl multiple domains and persist the collected pages.
    max_pages applies per seed/domain, not to the combined crawl.
    """
    seed_urls = [seed.strip() for seed in seeds.split(",") if seed.strip()]
    if not seed_urls:
        raise HTTPException(
            status_code=400,
            detail="At least one seed URL is required.",
        )

    validated_seeds = [
        (seed_url, validate_http_url(seed_url))
        for seed_url in seed_urls
    ]

    all_documents = []
    seen_urls = set()
    blocked_by_robots = 0
    request_errors = 0

    for seed_url, domain in validated_seeds:
        print(f"Starting seed: {seed_url}")
        crawler = Crawler(
            max_pages=max_pages,
            allowed_domain=domain,
            max_depth=2,
            delay=1.0,
        )

        try:
            crawl_result = crawler.crawl(seed_url)
        finally:
            crawler.close()

        blocked_by_robots += crawl_result.get("blocked_by_robots", 0)
        request_errors += crawl_result.get("request_errors", 0)

        for document in crawl_result.get("documents", []):
            document_url = document.get("url")
            if not document_url or document_url in seen_urls:
                continue
            seen_urls.add(document_url)
            all_documents.append(document)

    # This work must happen before returning the response.
    new_documents, new_links = save_crawled_documents(all_documents)
    rebuild_search_state(all_documents)

    return {
        "seeds": [seed_url for seed_url, _ in validated_seeds],
        "pages_crawled": len(all_documents),
        "new_documents": new_documents,
        "new_links": new_links,
        "links_found": sum(
            len(document.get("links", [])) for document in all_documents
        ),
        "blocked_by_robots": blocked_by_robots,
        "request_errors": request_errors,
        "total_indexed_documents": len(index.documents),
    }


@app.get("/frontier/stats")
def frontier_stats():
    """Return persistent crawl queue statistics."""
    return get_frontier_stats()


@app.post("/crawl-queue")
def crawl_queue(
    seeds: str,
    max_pages: int = Query(default=10, ge=1, le=100),
    max_depth: int = Query(default=2, ge=0, le=5),
    delay: float = Query(default=1.0, ge=0, le=5),
):
    """Enqueue seed URLs and process a bounded batch of pages."""
    seed_urls = list(dict.fromkeys(
        item.strip() for item in seeds.split(",") if item.strip()
    ))

    if not seed_urls:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one seed URL.",
        )

    validated_seeds = []

    for seed in seed_urls:
        domain = validate_http_url(seed)

        crawler = Crawler(
            max_pages=1,
            allowed_domain=domain,
            max_depth=0,
            delay=0,
        )
        try:
            normalized = crawler.normalize_url(seed)
        finally:
            crawler.close()

        if not normalized:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid seed URL: {seed}",
            )

        validated_seeds.append((normalized, domain))

    seeds_added = 0

    for seed_url, _domain in validated_seeds:
        if enqueue_url(seed_url, depth=0, priority=100):
            seeds_added += 1

    pages_processed = 0
    new_documents = 0
    new_links = 0
    blocked_by_robots = 0
    request_errors = 0

    while pages_processed < max_pages:
        job = claim_next_url(max_attempts=3)

        if job is None:
            break

        url = job["url"]
        depth = job["depth"]
        domain = validate_http_url(url)

        crawler = Crawler(
            max_pages=1,
            allowed_domain=domain,
            max_depth=0,
            delay=0,
        )

        try:
            result = crawler.crawl(url)
        except Exception as exc:
            mark_url_failed(
                url,
                str(exc),
                max_attempts=3,
                retry_delay_seconds=60,
            )
            pages_processed += 1
            continue
        finally:
            crawler.close()

        blocked_by_robots += result.get("blocked_by_robots", 0)
        request_errors += result.get("request_errors", 0)
        documents = result.get("documents", [])

        if not documents:
            errors = result.get("errors", [])
            crawl_error = next(
                (item for item in errors if item.get("url") == url),
                None,
            )

            if crawl_error and not crawl_error.get("retryable", True):
                error_message = crawl_error.get("error") or (
                    f"Permanent HTTP error: {crawl_error.get('status_code')}"
                )
                mark_url_permanently_failed(url, error_message)
            else:
                error_message = (
                    crawl_error.get("error")
                    if crawl_error
                    else "No indexable page returned by crawler"
                )
                mark_url_failed(
                    url,
                    error_message,
                    max_attempts=3,
                    retry_delay_seconds=60,
                )

            pages_processed += 1
            continue

        try:
            added_docs, added_links = save_crawled_documents(documents)
            refresh_index_documents(documents)
            
            new_documents += added_docs
            new_links += added_links

            if depth < max_depth:
                for document in documents:
                    for link in document.get("links", []):
                        enqueue_url(
                            link,
                            source_url=document["url"],
                            depth=depth + 1,
                            priority=10,
                        )

            mark_url_crawled(url)

        except Exception as exc:
            mark_url_failed(
                url,
                str(exc),
                max_attempts=3,
                retry_delay_seconds=60,
            )
            pages_processed += 1
            continue

        pages_processed += 1

        if delay and pages_processed < max_pages:
            time.sleep(delay)

    rebuild_search_state()

    return {
        "seeds_added": seeds_added,
        "pages_processed": pages_processed,
        "new_documents": new_documents,
        "new_links": new_links,
        "blocked_by_robots": blocked_by_robots,
        "request_errors": request_errors,
        "indexed_documents": len(index.documents),
        "frontier": get_frontier_stats(),
    }


@app.get("/search")
def search(
    q: str = Query(min_length=1, max_length=300),
    category: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=15, ge=1),
    offset: Optional[int] = Query(default=None, ge=0),
):
    query_text = q.default if hasattr(q, "default") else q
    query_text = str(query_text or "").strip()
    if not query_text:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    cat = category.default if hasattr(category, "default") else category
    cat = str(cat or "all").lower().strip()
    if cat not in ("all", "images", "videos", "news"):
        cat = "all"

    # Strictly enforce 15-result limit per page as required
    lim = limit.default if hasattr(limit, "default") else limit
    try:
        lim = min(max(1, int(lim)), 15)
    except (TypeError, ValueError):
        lim = 15

    # Determine stable page and offset
    off = offset.default if hasattr(offset, "default") else offset
    pg = page.default if hasattr(page, "default") else page
    try:
        pg = max(1, int(pg))
    except (TypeError, ValueError):
        pg = 1

    if off is not None:
        try:
            off_int = max(0, int(off))
            pg = (off_int // lim) + 1
        except (TypeError, ValueError):
            off_int = (pg - 1) * lim
    else:
        off_int = (pg - 1) * lim

    all_results = []

    # 1. CATEGORY: IMAGES
    if cat == "images":
        from app.crawler.web_retriever import WebRetriever
        from app.search.image_scorer import ImageRelevanceScorer

        raw_candidates = []
        conn = get_connection()
        try:
            # Query local images with token match
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
            rows = conn.execute(query_sql, params).fetchall()
            for r in rows:
                raw_candidates.append({
                    "id": r["id"],
                    "title": r["title"] or r["alt_text"] or "Image",
                    "url": r["url"],
                    "image_url": r["image_url"],
                    "thumbnail": r["image_url"],
                    "alt_text": r["alt_text"] or "",
                    "source_page_title": r["title"] or "",
                    "width": r["width"],
                    "height": r["height"],
                    "media_type": "image",
                    "source": "Local Index",
                    "publisher": "Local Index",
                    "snippet": r["alt_text"] or r["title"] or "",
                })
        except Exception:
            pass
        finally:
            conn.close()

        try:
            retriever = WebRetriever(timeout=3.5)
            live_images = retriever.retrieve(query_text, max_results=30, category="images")
            for img in live_images:
                iurl = img.get("image_url")
                if iurl:
                    raw_candidates.append({
                        "id": hash(iurl) % 10000000,
                        "title": img.get("title", "Image"),
                        "url": img.get("url", iurl),
                        "image_url": iurl,
                        "thumbnail": img.get("thumbnail") or iurl,
                        "alt_text": img.get("alt_text") or img.get("title") or "",
                        "source_page_title": img.get("source_page_title") or "",
                        "width": img.get("width"),
                        "height": img.get("height"),
                        "media_type": "image",
                        "source": img.get("source", "Web"),
                        "publisher": img.get("publisher", "Web"),
                        "snippet": img.get("snippet") or img.get("title") or "",
                    })
        except Exception:
            pass

        # Apply principled image relevance scoring, safety filtering, and deduplication
        all_results = ImageRelevanceScorer.rank_and_filter_images(
            query=query_text,
            candidates=raw_candidates,
            min_threshold=0.20,
            limit=45,
        )

    # 2. CATEGORY: VIDEOS
    elif cat == "videos":
        from app.crawler.web_retriever import WebRetriever
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, source_page_url, video_url, title, thumbnail_url, duration, publisher
                FROM videos
                WHERE title LIKE ?
                LIMIT 30
                """,
                (f"%{query_text}%",),
            ).fetchall()
            for r in rows:
                all_results.append({
                    "id": r["id"],
                    "title": r["title"],
                    "url": r["video_url"],
                    "thumbnail": r["thumbnail_url"],
                    "duration": r["duration"],
                    "publisher": r["publisher"] or "Video",
                    "media_type": "video",
                    "source": "Local Index",
                    "snippet": f"Video: {r['title']}",
                    "score": 1.0,
                })
        except Exception:
            pass
        finally:
            conn.close()

        try:
            retriever = WebRetriever(timeout=3.5)
            live_videos = retriever.retrieve(query_text, max_results=30, category="videos")
            seen_urls = {r["url"] for r in all_results if r.get("url")}
            for vid in live_videos:
                vurl = vid.get("url")
                if vurl and vurl not in seen_urls:
                    seen_urls.add(vurl)
                    all_results.append({
                        "id": hash(vurl) % 10000000,
                        "title": vid.get("title", "Video"),
                        "url": vurl,
                        "thumbnail": vid.get("thumbnail"),
                        "duration": vid.get("duration"),
                        "publisher": vid.get("publisher", "YouTube"),
                        "published_at": vid.get("published_at"),
                        "media_type": "video",
                        "source": "YouTube",
                        "snippet": vid.get("snippet", ""),
                        "score": 0.85,
                    })
        except Exception:
            pass

    # 3. CATEGORY: NEWS
    elif cat == "news":
        from app.crawler.web_retriever import WebRetriever
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, url, title, content, thumbnail, published_at, publisher
                FROM documents
                WHERE media_type = 'news' AND (title LIKE ? OR content LIKE ?)
                LIMIT 30
                """,
                (f"%{query_text}%", f"%{query_text}%"),
            ).fetchall()
            for r in rows:
                all_results.append({
                    "id": r["id"],
                    "title": r["title"],
                    "url": r["url"],
                    "thumbnail": r["thumbnail"],
                    "published_at": r["published_at"],
                    "publisher": r["publisher"] or "News",
                    "media_type": "news",
                    "source": r["publisher"] or "News",
                    "snippet": (r["content"] or "")[:250],
                    "text": (r["content"] or "")[:250],
                    "score": 1.0,
                })
        except Exception:
            pass
        finally:
            conn.close()

        try:
            retriever = WebRetriever(timeout=3.5)
            live_news = retriever.retrieve(query_text, max_results=30, category="news")
            seen_urls = {r["url"] for r in all_results if r.get("url")}
            for n in live_news:
                nurl = n.get("url")
                if nurl and nurl not in seen_urls:
                    seen_urls.add(nurl)
                    all_results.append({
                        "id": hash(nurl) % 10000000,
                        "title": n.get("title", "News Article"),
                        "url": nurl,
                        "thumbnail": n.get("thumbnail"),
                        "published_at": n.get("published_at"),
                        "publisher": n.get("publisher", "News"),
                        "media_type": "news",
                        "source": n.get("publisher", "News"),
                        "snippet": n.get("snippet", ""),
                        "text": n.get("text", ""),
                        "score": 0.85,
                    })
        except Exception:
            pass

    # 4. CATEGORY: ALL (Web Pages)
    else:
        all_results = search_engine.search(query_text)

        # Supplement with live web results if fewer than 15 results
        if len(all_results) < 15:
            try:
                from app.crawler.web_retriever import WebRetriever

                retriever = WebRetriever(timeout=3.5)
                web_docs = retriever.retrieve(query_text, max_results=30, category="all")
                if web_docs:
                    save_crawled_documents(web_docs)
                    refresh_index_documents(web_docs)
                    all_results = search_engine.search(query_text)

                    existing_urls = {r["url"] for r in all_results}
                    for doc in web_docs:
                        url = doc.get("url")
                        if url and url not in existing_urls:
                            nav_boost = search_engine.calculate_navigational_boost(
                                url, doc.get("title", ""), query_text
                            )
                            all_results.append({
                                "id": hash(url) % 10000000,
                                "title": doc.get("title", ""),
                                "url": url,
                                "score": round(0.75 + nav_boost, 4),
                                "bm25": 1.25,
                                "bm25_normalized": 0.38,
                                "title_score": 0.8,
                                "phrase_score": 0.5,
                                "pagerank": 0.0001,
                                "pagerank_normalized": 0.5,
                                "text": doc.get("text", "")[:300],
                                "snippet": doc.get("snippet") or doc.get("text", "")[:300],
                                "thumbnail": doc.get("thumbnail"),
                                "media_type": "web",
                            })
                            existing_urls.add(url)

                    # Ensure final priority ordering puts the official, most accessed domain first
                    all_results.sort(key=lambda r: (-r.get("score", 0.0), -r.get("pagerank", 0.0)))
            except Exception:
                pass

        # Enrich results with thumbnail and metadata from database if missing
        conn = get_connection()
        try:
            urls_to_check = [r["url"] for r in all_results if not r.get("thumbnail")]
            if urls_to_check:
                for chunk_start in range(0, len(urls_to_check), 100):
                    batch = urls_to_check[chunk_start : chunk_start + 100]
                    placeholders = ",".join("?" for _ in batch)
                    meta_rows = conn.execute(
                        f"SELECT url, thumbnail, published_at, publisher, media_type FROM documents WHERE url IN ({placeholders})",
                        batch,
                    ).fetchall()
                    meta_dict = {m["url"]: m for m in meta_rows}
                    for r in all_results:
                        if r["url"] in meta_dict:
                            m = meta_dict[r["url"]]
                            if not r.get("thumbnail") and m["thumbnail"]:
                                r["thumbnail"] = m["thumbnail"]
                            if not r.get("published_at") and m["published_at"]:
                                r["published_at"] = m["published_at"]
                            if not r.get("publisher") and m["publisher"]:
                                r["publisher"] = m["publisher"]
        except Exception:
            pass
        finally:
            conn.close()

    total_results = len(all_results)
    total_pages = max(1, math.ceil(total_results / lim))
    has_next = pg < total_pages
    has_prev = pg > 1

    paged = all_results[off_int : off_int + lim]

    return {
        "query": query_text,
        "category": cat,
        "page": pg,
        "limit": lim,
        "offset": off_int,
        "total_results": total_results,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev,
        "results": paged,
    }


@app.get("/suggest")
def suggest(q: str = Query(default="", max_length=100)):
    """Return live query suggestions for autocomplete dropdown."""
    query_text = q.default if hasattr(q, "default") else q
    query_text = str(query_text or "").strip()
    if not query_text:
        return {"query": "", "suggestions": []}

    from app.crawler.web_retriever import WebRetriever

    live_suggestions = WebRetriever.get_suggestions(query_text, limit=8)

    local_matches = [
        term for term in index.index.keys()
        if term.startswith(query_text.lower()) and len(term) > len(query_text)
    ]
    local_matches.sort(key=lambda t: len(index.index[t]), reverse=True)

    combined = []
    seen = set()
    # Prioritize real query search suggestions first
    for s in live_suggestions + local_matches:
        cleaned = s.strip()
        if cleaned and cleaned.lower() not in seen and len(cleaned) <= 40:
            seen.add(cleaned.lower())
            combined.append(cleaned)

    return {
        "query": query_text,
        "suggestions": combined[:8],
    }


@app.get("/pagerank")
def calculate_pagerank():
    ranks = load_page_ranks()
    sorted_ranks = sorted(ranks.items(), key=lambda item: item[1], reverse=True)
    return {
        "total_pages": len(ranks),
        "pages": [
            {"url": url, "pagerank": round(score, 8)}
            for url, score in sorted_ranks[:20]
        ],
    }


@app.get("/graph")
def graph():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT source_url, target_url FROM links LIMIT 100"
        )
        rows = cursor.fetchall()
    finally:
        connection.close()

    return {
        "total_links": len(rows),
        "links": [
            {"source": row["source_url"], "target": row["target_url"]}
            for row in rows
        ],
    }


@app.get("/reload-index")
def reload_index():
    rebuild_search_state(None)
    return {"status": "ok", "documents_indexed": len(index.documents)}


