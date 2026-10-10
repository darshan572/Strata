import re
import urllib.parse
from typing import Dict, List, Optional


class ImageRelevanceScorer:
    """
    Principled image search relevance scorer.
    Evaluates image candidates based on alt text, title, filename,
    and source context relevance to query terms.
    Filters invalid, low-quality, tracking, or unrelated images.
    """

    STOP_WORDS = {
        "a", "an", "the", "in", "on", "at", "for", "of", "to", "and", "or", "is", "it"
    }

    # Tracking and junk patterns to filter out
    JUNK_PATTERNS = [
        r"1x1", r"spacer", r"pixel", r"tracking", r"analytics", r"beacon",
        r"ad_server", r"doubleclick", r"adservice", r"blank\.gif"
    ]

    @classmethod
    def tokenize(cls, text: str) -> List[str]:
        if not text:
            return []
        tokens = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
        meaningful = [t for t in tokens if t not in cls.STOP_WORDS and len(t) > 1]
        return meaningful if meaningful else tokens

    @classmethod
    def is_valid_image_candidate(cls, img_url: str, width: Optional[int] = None, height: Optional[int] = None) -> bool:
        """Filter out non-http URLs, trackers, and microscopic 1x1 pixels."""
        if not img_url or not isinstance(img_url, str):
            return False

        img_lower = img_url.lower()
        if not (img_lower.startswith("http://") or img_lower.startswith("https://")):
            return False

        # Filter known tracking/junk URLs
        for pattern in cls.JUNK_PATTERNS:
            if re.search(pattern, img_lower):
                return False

        # Filter 1x1 tracking pixels if dimensions known
        if width is not None and height is not None:
            if width <= 10 or height <= 10:
                return False

        return True

    @classmethod
    def score_candidate(cls, query: str, candidate: Dict) -> float:
        """
        Compute textual and contextual relevance of an image to the query.
        Returns a score in [0.0, 1.5]. Images below 0.20 are considered unrelated.
        """
        q_tokens = cls.tokenize(query)
        if not q_tokens:
            return 0.0

        alt_text = str(candidate.get("alt_text") or "").strip()
        title = str(candidate.get("title") or "").strip()
        source_title = str(candidate.get("source_page_title") or "").strip()
        img_url = str(candidate.get("image_url") or "").strip()

        # Extract meaningful filename segment from URL
        try:
            path = urllib.parse.urlparse(img_url).path
            filename = path.split("/")[-1] if "/" in path else ""
            filename = urllib.parse.unquote(filename).replace("_", " ").replace("-", " ")
        except Exception:
            filename = ""

        alt_tokens = set(cls.tokenize(alt_text))
        title_tokens = set(cls.tokenize(title))
        file_tokens = set(cls.tokenize(filename))
        source_tokens = set(cls.tokenize(source_title))

        # 1. Alt-text coverage (primary semantic description)
        alt_matches = sum(1 for w in q_tokens if w in alt_tokens)
        alt_score = (alt_matches / len(q_tokens)) * 0.45

        # 2. Title & filename coverage (direct image identifier)
        name_matches = sum(1 for w in q_tokens if w in title_tokens or w in file_tokens)
        name_score = (name_matches / len(q_tokens)) * 0.35

        # Strict Relevance Guard: If neither the image description (alt text),
        # nor the image title, nor the image filename matches ANY query token,
        # the image is merely an incidental illustration on a page (e.g. court seal on a lawsuit page).
        # We must exclude it rather than presenting an unrelated image.
        if alt_matches == 0 and name_matches == 0:
            return 0.0

        # 3. Source page context coverage
        source_matches = sum(1 for w in q_tokens if w in source_tokens)
        source_score = (source_matches / len(q_tokens)) * 0.15

        # 4. Exact phrase bonus
        clean_q = query.lower().strip()
        phrase_bonus = 0.0
        if clean_q and (clean_q in alt_text.lower() or clean_q in title.lower() or clean_q in filename.lower()):
            phrase_bonus = 0.30

        # 5. Verified Brand / Local Index Boost
        verified_boost = 0.0
        if candidate.get("source") in ("Local Index", "Strata Official Index") or candidate.get("is_verified"):
            verified_boost = 0.30

        total_score = alt_score + name_score + source_score + phrase_bonus + verified_boost
        return round(total_score, 4)

    @classmethod
    def rank_and_filter_images(
        cls, query: str, candidates: List[Dict], min_threshold: float = 0.20, limit: int = 30
    ) -> List[Dict]:
        """
        Filter invalid and irrelevant images, deduplicate, and rank by relevance.
        """
        seen_urls = set()
        scored_candidates = []

        for item in candidates:
            img_url = item.get("image_url")
            if not cls.is_valid_image_candidate(img_url, item.get("width"), item.get("height")):
                continue

            # Normalized URL for deduplication (strip query params and lowercase scheme/host)
            try:
                parsed = urllib.parse.urlparse(img_url)
                norm_key = f"{parsed.netloc.lower()}{parsed.path.lower()}"
            except Exception:
                norm_key = img_url.lower()

            if norm_key in seen_urls:
                continue
            seen_urls.add(norm_key)

            score = cls.score_candidate(query, item)
            # Exclude images that do not satisfy minimum relevance threshold
            if score < min_threshold:
                continue

            scored_item = dict(item)
            scored_item["score"] = score
            scored_candidates.append(scored_item)

        # Sort by relevance score descending
        scored_candidates.sort(key=lambda x: -x["score"])
        return scored_candidates[:limit]
