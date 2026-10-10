import concurrent.futures
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

import bs4

from app.url_utils import is_safe_url, canonicalize_url

logger = logging.getLogger("sylvasearch.web_retriever")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 SylvaSearch/1.0"
)

# In-memory query cache keyed by (category, clean_query.lower())
_QUERY_CACHE: Dict[str, List[Dict]] = {}
_SUGGEST_CACHE: Dict[str, List[str]] = {}


class WebRetriever:
    """
    High-performance multi-category web retriever.
    Supports 'all', 'images', 'videos', and 'news' with authentic data.
    Protects against SSRF by validating all target URLs before ingestion.
    """

    def __init__(self, timeout: float = 3.5):
        self.timeout = timeout

    def retrieve(
        self, query: str, max_results: int = 15, category: str = "all"
    ) -> List[Dict]:
        """
        Retrieve search results for a query across web sources in parallel.
        Caches results per (category, query) to eliminate result fluctuation.
        """
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        cat = category.lower().strip()
        cache_key = f"{cat}:{clean_query.lower()}"

        if cache_key in _QUERY_CACHE and len(_QUERY_CACHE[cache_key]) >= 3:
            return _QUERY_CACHE[cache_key][:max_results]

        results: List[Dict] = []

        if cat == "images":
            results = self._fetch_images(clean_query, max_results)
        elif cat == "videos":
            results = self._fetch_videos(clean_query, max_results)
        elif cat == "news":
            results = self._fetch_news(clean_query, max_results)
        else:
            # Category 'all' / general web
            results = self._fetch_all_web(clean_query, max_results)

        if results:
            _QUERY_CACHE[cache_key] = results

        return results[:max_results]

    # -------------------------------------------------------------------------
    # CATEGORY: ALL (Web pages + enriched thumbnails)
    # -------------------------------------------------------------------------

    def _fetch_all_web(self, query: str, max_results: int) -> List[Dict]:
        results: List[Dict] = []
        seen_urls = set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_ddg = executor.submit(self._fetch_duckduckgo_lite, query, max_results)
            future_wiki = executor.submit(self._fetch_wikipedia_with_images, query, 10)
            future_ddg_ia = executor.submit(self._fetch_duckduckgo_instant, query)

            # 1. DDG Lite results (broad web)
            try:
                for item in future_ddg.result(timeout=self.timeout + 0.5):
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        results.append(item)
            except Exception as exc:
                logger.warning("DDG Lite retrieval error: %s", exc)

            # 2. Wikipedia results (high accuracy with thumbnails)
            try:
                for item in future_wiki.result(timeout=self.timeout + 0.5):
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        results.append(item)
            except Exception as exc:
                logger.warning("Wikipedia retrieval error: %s", exc)

            # 3. DDG Instant Answer (if scarce results)
            if len(results) < 5:
                try:
                    for item in future_ddg_ia.result(timeout=self.timeout + 0.5):
                        if item["url"] not in seen_urls:
                            seen_urls.add(item["url"])
                            results.append(item)
                except Exception as exc:
                    logger.warning("DDG Instant answer error: %s", exc)

        return results[:max_results]

    def _fetch_duckduckgo_lite(self, query: str, limit: int = 15) -> List[Dict]:
        """Fetch general web results from DuckDuckGo Lite."""
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            html = response.read()

        soup = bs4.BeautifulSoup(html, "html.parser")
        items = []

        for tr in soup.select("table tr"):
            a_elem = tr.select_one("a.result-link")
            if not a_elem:
                continue

            raw_href = a_elem.get("href", "")
            if "uddg=" in raw_href:
                qs = urllib.parse.parse_qs(urllib.parse.urlsplit(raw_href).query)
                target_url = qs.get("uddg", [raw_href])[0]
            else:
                target_url = raw_href

            if not target_url.startswith(("http://", "https://")):
                continue

            if not is_safe_url(target_url):
                continue

            try:
                canon_url = canonicalize_url(target_url)
            except Exception:
                canon_url = target_url

            title = a_elem.get_text(strip=True)
            if not title:
                continue

            next_tr = tr.find_next_sibling("tr")
            snippet_elem = next_tr.select_one(".result-snippet") if next_tr else None
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            combined_text = f"{title}. {snippet}".strip()

            items.append({
                "url": canon_url,
                "title": title,
                "text": combined_text,
                "snippet": snippet or combined_text[:200],
                "links": [],
                "media_type": "web",
            })

            if len(items) >= limit:
                break

        return items

    def _fetch_wikipedia_with_images(self, query: str, limit: int = 10) -> List[Dict]:
        """Fetch Wikipedia articles enriched with thumbnail images."""
        encoded_query = urllib.parse.quote(query)
        api_url = (
            f"https://en.wikipedia.org/w/api.php?"
            f"action=query&generator=search&gsrsearch={encoded_query}&gsrlimit={limit}"
            f"&prop=pageimages|extracts&exintro=1&explaintext=1&exchars=280&pithumbsize=400&format=json"
        )
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "SylvaSearchBot/1.0 (https://sylvasearch.local; bot@sylvasearch.local)",
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))

        pages = payload.get("query", {}).get("pages", {})
        items = []

        for _, page in pages.items():
            title = page.get("title", "").strip()
            if not title:
                continue

            article_slug = urllib.parse.quote(title.replace(" ", "_"))
            target_url = f"https://en.wikipedia.org/wiki/{article_slug}"

            if not is_safe_url(target_url):
                continue

            try:
                canon_url = canonicalize_url(target_url)
            except Exception:
                canon_url = target_url

            snippet = page.get("extract", "").strip()
            combined_text = f"{title}. {snippet}".strip()

            thumb_info = page.get("thumbnail", {})
            thumb_url = thumb_info.get("source") if isinstance(thumb_info, dict) else None

            items.append({
                "url": canon_url,
                "title": f"{title} - Wikipedia",
                "text": combined_text,
                "snippet": snippet or combined_text[:200],
                "thumbnail": thumb_url,
                "links": [],
                "media_type": "web",
            })

        return items

    def _fetch_duckduckgo_instant(self, query: str) -> List[Dict]:
        """Fetch answers and related topics from DuckDuckGo Instant Answer API."""
        encoded_query = urllib.parse.quote(query)
        api_url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json"
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": USER_AGENT},
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        items = []
        abstract_text = data.get("AbstractText", "")
        abstract_url = data.get("AbstractURL", "")
        heading = data.get("Heading", query)
        image_url = data.get("Image", "")
        if image_url and not image_url.startswith("http"):
            image_url = f"https://duckduckgo.com{image_url}"

        if abstract_url and is_safe_url(abstract_url):
            try:
                canon_url = canonicalize_url(abstract_url)
            except Exception:
                canon_url = abstract_url

            items.append({
                "url": canon_url,
                "title": heading,
                "text": f"{heading}. {abstract_text}".strip(),
                "snippet": abstract_text or heading,
                "thumbnail": image_url if image_url else None,
                "links": [],
                "media_type": "web",
            })

        for topic in data.get("RelatedTopics", []):
            if not isinstance(topic, dict):
                continue
            first_url = topic.get("FirstURL")
            text = topic.get("Text", "")
            topic_icon = topic.get("Icon", {}).get("URL", "")
            if topic_icon and not topic_icon.startswith("http"):
                topic_icon = f"https://duckduckgo.com{topic_icon}"

            if not first_url or not is_safe_url(first_url):
                continue

            try:
                canon_url = canonicalize_url(first_url)
            except Exception:
                canon_url = first_url

            parts = text.split(" - ", 1)
            title = parts[0] if parts else text[:60]

            items.append({
                "url": canon_url,
                "title": title,
                "text": text,
                "snippet": text,
                "thumbnail": topic_icon if topic_icon else None,
                "links": [],
                "media_type": "web",
            })

        return items

    # -------------------------------------------------------------------------
    # CATEGORY: IMAGES (Wikimedia Commons + Wikipedia Media API)
    # -------------------------------------------------------------------------

    def _fetch_images(self, query: str, limit: int = 15) -> List[Dict]:
        """Fetch authentic image results with genuine URLs, thumbnails, and dimensions."""
        encoded = urllib.parse.quote(query)
        items: List[Dict] = []
        seen = set()

        # Source 1: Wikimedia Commons generator search
        commons_url = (
            f"https://commons.wikimedia.org/w/api.php?"
            f"action=query&generator=search&gsrsearch={encoded}&gsrnamespace=6"
            f"&prop=imageinfo&iiprop=url|size|extmetadata&format=json&gsrlimit={limit}"
        )
        try:
            req = urllib.request.Request(
                commons_url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                data = json.loads(res.read().decode("utf-8"))
            pages = data.get("query", {}).get("pages", {})
            for _, page in pages.items():
                title = page.get("title", "").replace("File:", "").strip()
                imageinfo = page.get("imageinfo", [{}])[0]
                img_url = imageinfo.get("url")
                if not img_url or img_url in seen or not is_safe_url(img_url):
                    continue
                seen.add(img_url)

                thumb_url = imageinfo.get("thumburl") or img_url
                width = imageinfo.get("width")
                height = imageinfo.get("height")
                source_url = f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(page.get('title', ''))}"

                items.append({
                    "title": title,
                    "url": source_url,
                    "image_url": img_url,
                    "thumbnail": thumb_url,
                    "width": width,
                    "height": height,
                    "source": "Wikimedia Commons",
                    "publisher": "Wikimedia Commons",
                    "media_type": "image",
                    "text": f"Image: {title}",
                    "snippet": f"{title} ({width}x{height})" if width and height else title,
                })
        except Exception as exc:
            logger.warning("Wikimedia Commons image fetch error: %s", exc)

        # Source 2: Wikipedia PageImages if more images needed
        if len(items) < limit:
            try:
                wiki_img_url = (
                    f"https://en.wikipedia.org/w/api.php?"
                    f"action=query&generator=search&gsrsearch={encoded}&gsrlimit=10"
                    f"&prop=pageimages&pithumbsize=600&format=json"
                )
                req = urllib.request.Request(
                    wiki_img_url,
                    headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as res:
                    data = json.loads(res.read().decode("utf-8"))
                pages = data.get("query", {}).get("pages", {})
                for _, page in pages.items():
                    article_title = page.get("title", "").strip()
                    thumb = page.get("thumbnail", {}).get("source")
                    if not thumb or thumb in seen:
                        continue
                    seen.add(thumb)
                    page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(article_title.replace(' ', '_'))}"

                    # Extract authentic image subject from filename rather than article title
                    try:
                        raw_fn = urllib.parse.unquote(urllib.parse.urlsplit(thumb).path.split("/")[-1])
                        clean_fn = re.sub(r"^\d+px-", "", raw_fn)
                        clean_title = re.sub(r"\.[a-zA-Z0-9]+$", "", clean_fn).replace("_", " ")
                    except Exception:
                        clean_title = article_title

                    items.append({
                        "title": clean_title,
                        "url": page_url,
                        "image_url": thumb,
                        "thumbnail": thumb,
                        "width": page.get("thumbnail", {}).get("width"),
                        "height": page.get("thumbnail", {}).get("height"),
                        "source": "Wikipedia",
                        "publisher": "Wikipedia",
                        "source_page_title": article_title,
                        "media_type": "image",
                        "alt_text": clean_title,
                        "text": f"Image: {clean_title}",
                        "snippet": clean_title,
                    })
            except Exception as exc:
                logger.warning("Wikipedia PageImages fetch error: %s", exc)

        return items[:limit]

    # -------------------------------------------------------------------------
    # CATEGORY: VIDEOS (YouTube initial data search)
    # -------------------------------------------------------------------------

    def _fetch_videos(self, query: str, limit: int = 15) -> List[Dict]:
        """Fetch authentic video search results with video thumbnails, duration, and channel."""
        encoded = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        items: List[Dict] = []
        seen = set()

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                html = res.read().decode("utf-8", errors="ignore")

            pattern = r"ytInitialData\s*=\s*({.+?});</script>"
            match = re.search(pattern, html)
            if not match:
                return []

            data = json.loads(match.group(1))
            contents = (
                data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            for section in contents:
                section_items = section.get("itemSectionRenderer", {}).get("contents", [])
                for item in section_items:
                    v = item.get("videoRenderer")
                    if not v:
                        continue
                    video_id = v.get("videoId")
                    if not video_id or video_id in seen:
                        continue
                    seen.add(video_id)

                    title = "".join(r.get("text", "") for r in v.get("title", {}).get("runs", []))
                    if not title:
                        continue

                    watch_url = f"https://www.youtube.com/watch?v={video_id}"
                    thumbs = v.get("thumbnail", {}).get("thumbnails", [])
                    thumb_url = thumbs[-1].get("url") if thumbs else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    duration = v.get("lengthText", {}).get("simpleText", "")
                    channel = "".join(r.get("text", "") for r in v.get("ownerText", {}).get("runs", []))
                    published = v.get("publishedTimeText", {}).get("simpleText", "")

                    items.append({
                        "title": title,
                        "url": watch_url,
                        "video_id": video_id,
                        "thumbnail": thumb_url,
                        "duration": duration,
                        "publisher": channel,
                        "published_at": published,
                        "media_type": "video",
                        "text": f"{title} - Video by {channel} ({duration})",
                        "snippet": f"Watch {title} on YouTube by {channel}. Duration: {duration or 'N/A'}",
                    })

                    if len(items) >= limit:
                        break
        except Exception as exc:
            logger.warning("Video retrieval error: %s", exc)

        return items[:limit]

    # -------------------------------------------------------------------------
    # CATEGORY: NEWS (Google News RSS Feed)
    # -------------------------------------------------------------------------

    def _fetch_news(self, query: str, limit: int = 15) -> List[Dict]:
        """Fetch authentic news articles with verified publishers and publication dates."""
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        items: List[Dict] = []
        seen = set()

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                xml = res.read().decode("utf-8", errors="ignore")

            soup = bs4.BeautifulSoup(xml, "xml")
            for item in soup.find_all("item"):
                title = item.title.text if item.title else ""
                link = item.link.text if item.link else ""
                pub_date = item.pubDate.text if item.pubDate else ""
                source = item.source.text if item.source else ""

                if not title or not link or link in seen:
                    continue
                seen.add(link)

                # Clean title (Google News titles usually end with ' - Publisher')
                clean_title = title
                if source and clean_title.endswith(f" - {source}"):
                    clean_title = clean_title[: -len(f" - {source}")].strip()

                desc_soup = bs4.BeautifulSoup(item.description.text if item.description else "", "html.parser")
                snippet = desc_soup.get_text(strip=True) or clean_title

                items.append({
                    "title": clean_title,
                    "url": link,
                    "publisher": source or "News Wire",
                    "published_at": pub_date,
                    "media_type": "news",
                    "thumbnail": None,
                    "text": f"{clean_title}. {snippet}",
                    "snippet": snippet,
                })

                if len(items) >= limit:
                    break
        except Exception as exc:
            logger.warning("Google News retrieval error: %s", exc)

        return items[:limit]

    # -------------------------------------------------------------------------
    # AUTOCOMPLETE SUGGESTIONS
    # -------------------------------------------------------------------------

    @staticmethod
    def get_suggestions(query: str, limit: int = 8) -> List[str]:
        """
        Retrieve live search suggestions for autocomplete as the user types.
        Combines DuckDuckGo and Google Suggest APIs with local cache.
        """
        if not query or not query.strip():
            return []

        clean_q = query.strip()
        cache_key = clean_q.lower()
        if cache_key in _SUGGEST_CACHE:
            return _SUGGEST_CACHE[cache_key][:limit]

        suggestions = []
        seen = set()

        # 1. DuckDuckGo Autocomplete API
        try:
            url = f"https://duckduckgo.com/ac/?q={urllib.parse.quote(clean_q)}&type=list"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=1.5) as res:
                data = json.loads(res.read().decode("utf-8"))
                if len(data) > 1 and isinstance(data[1], list):
                    for item in data[1]:
                        item_str = str(item).strip()
                        if item_str and item_str.lower() not in seen:
                            seen.add(item_str.lower())
                            suggestions.append(item_str)
        except Exception:
            pass

        # 2. Google Suggest API (high coverage fallback)
        if len(suggestions) < limit:
            try:
                url = f"https://suggestqueries.google.com/complete/search?client=chrome&q={urllib.parse.quote(clean_q)}"
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=1.5) as res:
                    data = json.loads(res.read().decode("utf-8"))
                    if len(data) > 1 and isinstance(data[1], list):
                        for item in data[1]:
                            item_str = str(item).strip()
                            if item_str and item_str.lower() not in seen:
                                seen.add(item_str.lower())
                                suggestions.append(item_str)
            except Exception:
                pass

        final = suggestions[:limit]
        if final:
            _SUGGEST_CACHE[cache_key] = final

        return final
