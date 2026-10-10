import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from app.crawler.politeness import wait_for_host
from app.url_utils import is_safe_url


def _validate_redirect_hook(response, *args, **kwargs):
    if response.is_redirect:
        location = response.headers.get("location")
        if location:
            target = urljoin(response.url, location)
            if not is_safe_url(target):
                raise requests.RequestException(
                    f"Blocked SSRF redirect to restricted address: {target}"
                )


class Crawler:
    """A polite, domain-restricted breadth-first web crawler."""

    def __init__(
        self,
        max_pages=20,
        allowed_domain=None,
        max_depth=2,
        delay=1.0,
    ):
        self.max_pages = max(1, int(max_pages))
        self.allowed_domain = (
            allowed_domain.lower().strip()
            if allowed_domain
            else None
        )
        self.max_depth = max(0, int(max_depth))
        self.delay = max(0.0, float(delay))

        self.visited = set()
        self.queue = deque()
        self.robot_parsers = {}

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SylvaSearchBot/0.1",
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        self.session.hooks.setdefault("response", []).append(_validate_redirect_hook)

    # ---------------------------------------------------------
    # URL NORMALIZATION
    # ---------------------------------------------------------

    def normalize_url(self, url):
        """Normalize HTTP(S) URLs and remove fragments."""
        if not url:
            return None

        try:
            url = urldefrag(url.strip())[0]
            parsed = urlparse(url)

            if parsed.scheme.lower() not in ("http", "https"):
                return None

            if not parsed.hostname:
                return None

            scheme = parsed.scheme.lower()
            hostname = parsed.hostname.lower()

            # Preserve a non-default port, if present.
            try:
                port = parsed.port
            except ValueError:
                return None

            if port and not (
                (scheme == "http" and port == 80)
                or (scheme == "https" and port == 443)
            ):
                netloc = f"{hostname}:{port}"
            else:
                netloc = hostname

            path = parsed.path or "/"

            # Keep the root slash, remove other trailing slashes.
            if path != "/":
                path = path.rstrip("/") or "/"

            normalized = f"{scheme}://{netloc}{path}"

            # Query parameters may distinguish different pages, so keep them.
            if parsed.query:
                normalized += f"?{parsed.query}"

            return normalized

        except (TypeError, ValueError, AttributeError):
            return None

    # ---------------------------------------------------------
    # DOMAIN RESTRICTION
    # ---------------------------------------------------------

    def is_allowed_domain(self, url):
        """Keep the crawl on the configured host."""
        if not self.allowed_domain:
            return True

        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            allowed = self.allowed_domain.lower()

            # Accept a hostname or host:port as allowed_domain.
            if "://" in allowed:
                allowed = (urlparse(allowed).hostname or "").lower()
            else:
                allowed = allowed.split(":", 1)[0]

            return host == allowed

        except (TypeError, ValueError, AttributeError):
            return False

    # ---------------------------------------------------------
    # ROBOTS.TXT
    # ---------------------------------------------------------

    def get_robot_parser(self, url):
        """Fetch and cache robots.txt for each origin."""
        try:
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
        except (TypeError, ValueError, AttributeError):
            return None

        if origin in self.robot_parsers:
            return self.robot_parsers[origin]

        robots_url = f"{origin}/robots.txt"
        if not is_safe_url(robots_url):
            self.robot_parsers[origin] = None
            return None

        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            # Use our configured session/User-Agent to fetch robots.txt.
            response = self.session.get(robots_url, timeout=10)

            # An explicit missing robots.txt means no published rules.
            if response.status_code in (404, 410):
                parser.parse([])
                self.robot_parsers[origin] = parser
                return parser

            response.raise_for_status()
            parser.parse(response.text.splitlines())
            self.robot_parsers[origin] = parser
            return parser
        except requests.RequestException as error:
            # If robots.txt cannot be retrieved, log the issue and continue
            # using the crawler's fallback policy. Do not bypass a rule that
            # was successfully retrieved and parsed.
            print(f"Could not retrieve robots.txt: {robots_url} ({error})")
            self.robot_parsers[origin] = None
            return None

    def allowed_by_robots(self, url):
        """Return whether the configured crawler identity may fetch a URL."""
        parser = self.get_robot_parser(url)

        # Fail closed on retrieval errors or invalid URLs.
        if parser is None:
            return False

        try:
            return parser.can_fetch("SylvaSearchBot", url)
        except Exception as error:
            print(f"Could not evaluate robots.txt for {url}: {error}")
            # Fail closed if a retrieved policy cannot be evaluated.
            return False

    # ---------------------------------------------------------
    # LINK EXTRACTION
    # ---------------------------------------------------------

    def extract_links(self, soup, current_url):
        """Extract normalized, same-domain HTTP(S) links."""
        links = set()

        try:
            anchors = soup.find_all("a", href=True)
        except Exception:
            return links

        for anchor in anchors:
            try:
                href = (anchor.get("href") or "").strip()
                if not href:
                    continue

                lowered_href = href.lower()
                if lowered_href.startswith(
                    ("#", "javascript:", "mailto:", "tel:", "data:")
                ):
                    continue

                absolute_url = urljoin(current_url, href)
                normalized_url = self.normalize_url(absolute_url)

                if not normalized_url:
                    continue

                if not self.is_allowed_domain(normalized_url):
                    continue

                links.add(normalized_url)

            except Exception:
                continue

        return links

    def extract_media_and_metadata(self, soup, current_url):
        """Extract images, videos, thumbnails, and metadata from HTML before tag decomposition."""
        metadata = {
            "thumbnail": None,
            "images": [],
            "videos": [],
            "published_at": None,
            "publisher": None,
            "media_type": "web",
        }

        # 1. Open Graph / Twitter meta tags
        for meta in soup.find_all("meta"):
            prop = (meta.get("property") or meta.get("name") or "").lower()
            content = (meta.get("content") or "").strip()
            if not content:
                continue

            if prop in ("og:image", "twitter:image") and not metadata["thumbnail"]:
                img_url = urljoin(current_url, content)
                if img_url.startswith(("http://", "https://")) and is_safe_url(img_url):
                    metadata["thumbnail"] = img_url

            elif prop in ("og:site_name", "author", "publisher") and not metadata["publisher"]:
                metadata["publisher"] = content

            elif prop in ("article:published_time", "og:pubdate", "date") and not metadata["published_at"]:
                metadata["published_at"] = content
                metadata["media_type"] = "news"

        # 2. Extract image elements
        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or "").strip()
            if not src or src.startswith("data:"):
                continue
            img_url = urljoin(current_url, src)
            if not img_url.startswith(("http://", "https://")) or not is_safe_url(img_url):
                continue

            alt = (img.get("alt") or "").strip()
            title = (img.get("title") or alt).strip()
            width = img.get("width")
            height = img.get("height")
            try:
                width = int(width) if width and str(width).isdigit() else None
                height = int(height) if height and str(height).isdigit() else None
            except Exception:
                width, height = None, None

            if width and width < 30 and height and height < 30:
                continue

            if not metadata["thumbnail"] and (width is None or width >= 100):
                metadata["thumbnail"] = img_url

            metadata["images"].append({
                "source_page_url": current_url,
                "image_url": img_url,
                "alt_text": alt,
                "title": title or alt,
                "width": width,
                "height": height,
            })
            if len(metadata["images"]) >= 10:
                break

        # 3. Extract video elements
        for video in soup.find_all("video"):
            src = (video.get("src") or "").strip()
            if not src:
                src_elem = video.find("source")
                if src_elem:
                    src = (src_elem.get("src") or "").strip()
            if src:
                vid_url = urljoin(current_url, src)
                if vid_url.startswith(("http://", "https://")) and is_safe_url(vid_url):
                    poster = video.get("poster")
                    poster_url = urljoin(current_url, poster) if poster else metadata["thumbnail"]
                    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
                    metadata["videos"].append({
                        "source_page_url": current_url,
                        "video_url": vid_url,
                        "title": page_title,
                        "thumbnail_url": poster_url,
                        "duration": None,
                        "publisher": metadata["publisher"],
                    })
                    metadata["media_type"] = "video"

        return metadata

    # ---------------------------------------------------------
    # CONTENT EXTRACTION
    # ---------------------------------------------------------

    def extract_content(self, soup):
        """Extract unique headings, paragraphs, and list items."""
        unwanted_tags = [
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "iframe",
            "form",
            "nav",
            "footer",
            "header",
            "aside",
        ]

        for tag_name in unwanted_tags:
            for tag in list(soup.find_all(tag_name)):
                try:
                    tag.decompose()
                except Exception:
                    pass

        content_blocks = []
        tags_to_collect = ["h1", "h2", "h3", "h4", "p", "li"]

        try:
            elements = soup.find_all(tags_to_collect)
        except Exception:
            elements = []

        seen = set()

        for element in elements:
            try:
                text = element.get_text(" ", strip=True)
            except Exception:
                continue

            text = " ".join(text.split())

            # Skip very short fragments and unusually large blocks.
            if len(text) < 20 or len(text) > 3000:
                continue

            normalized = text.casefold()
            if normalized in seen:
                continue

            seen.add(normalized)
            content_blocks.append(text)

        return " ".join(content_blocks).strip()

    # ---------------------------------------------------------
    # CRAWL
    # ---------------------------------------------------------

    def crawl(self, start_url):
        """
        Crawl a website using breadth-first search.

        Returns a dictionary containing:
          documents: list of {url, title, text, links}
          blocked_by_robots: number of URLs denied by robots.txt
          request_errors: number of page download failures
        """
        start_url = self.normalize_url(start_url)
        retry_attempts = {}

        if not start_url:
            print("Invalid start URL.")
            return {
                "documents": [],
                "blocked_by_robots": 0,
                "request_errors": 0,
                "errors": [],
            }

        self.queue = deque([(start_url, 0)])
        self.visited = set()

        documents = []
        blocked_by_robots = 0
        request_errors = 0
        errors = []

        while self.queue and len(documents) < self.max_pages:
            url, depth = self.queue.popleft()

            if url in self.visited:
                continue

            if not self.is_allowed_domain(url):
                continue

            if depth > self.max_depth:
                continue

            # Mark before checking/downloading to avoid repeated attempts.
            self.visited.add(url)

            if not is_safe_url(url):
                print(f"Blocked unsafe SSRF destination: {url}")
                request_errors += 1
                errors.append({
                    "url": url,
                    "status_code": 403,
                    "retryable": False,
                    "error": "Blocked request to private or loopback destination",
                })
                continue

            if not self.allowed_by_robots(url):
                print(f"Blocked by robots.txt: {url}")
                blocked_by_robots += 1
                continue

            print(f"Crawling: {url}")

            try:
                wait_for_host(url)
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
            except requests.RequestException as error:
                print(f"Request failed: {url}")
                print(error)
                request_errors += 1

                response = getattr(error, "response", None)
                status_code = getattr(response, "status_code", None)
                retryable = (
                    status_code is None
                    or status_code in (408, 425, 429)
                    or status_code >= 500
                )
                errors.append({
                    "url": url,
                    "status_code": status_code,
                    "retryable": retryable,
                    "error": str(error),
                })

                # Retry transient failures at most twice per URL.
                attempts = retry_attempts.get(url, 0)
                if retryable and attempts < 2:
                    retry_attempts[url] = attempts + 1
                    self.visited.discard(url)
                    self.queue.append((url, depth))
                    print(
                        f"Retry queued ({attempts + 1}/2): {url}"
                    )
                continue
            except Exception as error:
                print(f"Unexpected request error: {url}")
                print(error)
                request_errors += 1
                errors.append({
                    "url": url,
                    "status_code": None,
                    "retryable": True,
                    "error": str(error),
                })
                continue

            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                print(f"Skipping non-HTML: {url}")
                continue

            try:
                soup = BeautifulSoup(response.text, "lxml")
            except Exception:
                soup = BeautifulSoup(response.text, "html.parser")

            try:
                title_tag = soup.find("title")
                title = title_tag.get_text(" ", strip=True) if title_tag else ""
            except Exception:
                title = ""

            # Extract links and media metadata before content cleaning removes tags.
            page_links = self.extract_links(soup, url)
            media_meta = self.extract_media_and_metadata(soup, url)
            print(f"Found {len(page_links)} links, {len(media_meta['images'])} images")

            text = self.extract_content(soup)
            if not text:
                print(f"Skipping empty page: {url}")
                continue

            documents.append(
                {
                    "url": url,
                    "title": title,
                    "text": text,
                    "links": sorted(page_links),
                    "thumbnail": media_meta.get("thumbnail"),
                    "images": media_meta.get("images", []),
                    "videos": media_meta.get("videos", []),
                    "published_at": media_meta.get("published_at"),
                    "publisher": media_meta.get("publisher"),
                    "media_type": media_meta.get("media_type", "web"),
                }
            )

            if depth < self.max_depth:
                for link in sorted(page_links):
                    if link not in self.visited:
                        self.queue.append((link, depth + 1))

            if self.delay > 0 and self.queue and len(documents) < self.max_pages:
                time.sleep(self.delay)

        print(
            "Crawl complete. "
            f"Pages crawled: {len(documents)}, "
            f"Blocked by robots: {blocked_by_robots}, "
            f"Request errors: {request_errors}"
        )

        return {
            "documents": documents,
            "blocked_by_robots": blocked_by_robots,
            "request_errors": request_errors,
            "errors": errors,
        }

    def close(self):
        """Close the underlying HTTP session."""
        self.session.close()
