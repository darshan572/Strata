
import math
import re
from collections import Counter


class SearchEngine:
    def __init__(self, index, page_ranks=None):
        self.index = index

        # BM25 parameters
        self.k1 = 1.5
        self.b = 0.75

        # PageRank data
        self.page_ranks = page_ranks or {}

        # Common English stop words
        self.stop_words = {
            "a", "an", "the", "is", "are", "was", "were",
            "of", "to", "in", "on", "for", "and", "or",
            "with", "by", "from", "as", "at", "be", "this",
            "that", "it", "its", "into", "about", "over",
            "under", "after", "before", "than", "then",
            "also", "can", "could", "would", "should",
            "will", "just", "not",
        }

    # ---------------------------------------------------------
    # TOKENIZATION
    # ---------------------------------------------------------

    def tokenize(self, text):
        if not text:
            return []

        words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
        filtered = [word for word in words if word not in self.stop_words]
        return filtered if filtered else words

    # ---------------------------------------------------------
    # IDF
    # ---------------------------------------------------------

    def calculate_idf(self, word):
        total_documents = len(self.index.documents)

        if total_documents == 0:
            return 0.0

        document_frequency = len(self.index.index.get(word, set()))

        if document_frequency == 0:
            return 0.0

        return math.log(
            1 + (
                total_documents - document_frequency + 0.5
            ) / (
                document_frequency + 0.5
            )
        )

    # ---------------------------------------------------------
    # AVERAGE DOCUMENT LENGTH AND TOKEN CACHE
    # ---------------------------------------------------------

    def _ensure_corpus_cache(self):
        generation = getattr(self.index, "document_generation", None)
        if (
            generation is not None
            and generation == getattr(self, "_cached_generation", None)
        ):
            return

        token_cache = {}
        length_cache = {}
        total_length = 0

        for document_id, document in self.index.documents.items():
            words = self.tokenize(document.get("text", ""))
            token_cache[document_id] = words
            length = len(words)
            length_cache[document_id] = length
            total_length += length

        self._document_tokens = token_cache
        self._document_lengths = length_cache
        count = len(self.index.documents)
        self._average_length = total_length / count if count else 0.0
        self._cached_generation = generation

    def calculate_average_length(self):
        self._ensure_corpus_cache()
        return self._average_length

    # ---------------------------------------------------------
    # BM25
    # ---------------------------------------------------------

    def bm25_score(
        self, document_id, query_words, average_length=None, idf_cache=None
    ):
        self._ensure_corpus_cache()
        words = self._document_tokens.get(document_id, [])

        if not words:
            return 0.0

        if average_length is None:
            average_length = self._average_length

        if average_length <= 0:
            return 0.0

        word_counts = Counter(words)
        document_length = self._document_lengths.get(document_id, len(words))
        score = 0.0

        for word in query_words:
            term_frequency = word_counts[word]
            if term_frequency == 0:
                continue

            if idf_cache is not None and word in idf_cache:
                idf = idf_cache[word]
            else:
                idf = self.calculate_idf(word)

            numerator = term_frequency * (self.k1 + 1)
            denominator = term_frequency + self.k1 * (
                1 - self.b + self.b * (document_length / average_length)
            )
            score += idf * numerator / denominator

        return score

    # SCORE TRANSFORMATIONS
    # ---------------------------------------------------------

    def normalize_bm25(self, score):
        """
        Map non-negative BM25 scores to [0, 1].
        Higher scores approach 1 without depending on
        the other documents in the current result set.
        """
        score = max(0.0, score)
        return score / (score + 2.0)

    def normalize_pagerank(self, score):
        """
        Smoothly scale PageRank values for the combined score.
        The reference scale is fixed rather than calculated
        from the current search candidates.
        """
        score = max(0.0, score)
        reference = 0.0001
        return score / (score + reference)

    # ---------------------------------------------------------
    # TITLE SCORE & TERM COVERAGE
    # ---------------------------------------------------------

    def title_score(self, document, query_words, query=""):
        title = (document.get("title", "") or "").lower().strip()
        title_words = self.tokenize(title)

        if not title_words or not query_words:
            return 0.0

        matches = sum(1 for word in query_words if word in title_words)
        coverage = matches / len(query_words)
        score = coverage * 0.70

        clean_query = (query or "").lower().strip()
        if clean_query:
            if clean_query in title:
                score += 0.30
            if title.startswith(clean_query):
                score += 0.15

        return min(1.0, score)

    @staticmethod
    def _stem(word):
        w = word.lower()
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
        return w

    def term_coverage_score(self, document, query_words):
        """
        Measure proportion of unique query words appearing in document.
        Penalizes documents that only match 1 term out of a multi-term query.
        """
        if not query_words:
            return 1.0

        doc_id = document.get("id")
        doc_words = set(self._document_tokens.get(doc_id, []))
        if not doc_words:
            doc_words = set(
                self.tokenize(document.get("text", "") + " " + document.get("title", ""))
            )

        doc_stems = {self._stem(w) for w in doc_words}
        matched = sum(1 for w in query_words if w in doc_words or self._stem(w) in doc_stems)
        return matched / len(query_words)

    def url_relevance_score(self, url, query_words):
        """
        URL path and slug relevance matching.
        Rewards pages whose path matches query terms (e.g. '/tutorial' for tutorial query).
        """
        if not url or not query_words:
            return 0.0
        try:
            from urllib.parse import urlparse
            path = (urlparse(url).path or "").lower()
            path_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", path))
            path_stems = {self._stem(w) for w in path_tokens}
            matches = sum(1 for w in query_words if w in path_tokens or self._stem(w) in path_stems)
            return (matches / len(query_words)) * 0.20
        except Exception:
            return 0.0

    def detect_spam_penalty(self, document, query_words):
        """
        Penalize keyword stuffing and repetitive spam.
        """
        doc_id = document.get("id")
        doc_words = self._document_tokens.get(doc_id, [])
        if not doc_words:
            doc_words = self.tokenize(document.get("text", ""))

        if len(doc_words) < 15 or not query_words:
            return 0.0

        counts = Counter(doc_words)
        total = len(doc_words)
        for qw in query_words:
            if counts[qw] / total > 0.15:
                return 0.35
        return 0.0

    # ---------------------------------------------------------
    # PHRASE SCORE
    # ---------------------------------------------------------

    def phrase_score(self, document, query):
        if not query or not query.strip():
            return 0.0

        def normalize_phrase(text):
            words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
            return " ".join(words)

        normalized_query = normalize_phrase(query)
        if not normalized_query:
            return 0.0

        title = normalize_phrase(document.get("title", ""))
        text = normalize_phrase(document.get("text", ""))

        if f" {normalized_query} " in f" {title} ":
            return 1.0

        if f" {normalized_query} " in f" {text} ":
            return 0.7

        return 0.0

    # ---------------------------------------------------------
    # INTENT CLASSIFICATION & NAVIGATIONAL BOOST
    # ---------------------------------------------------------

    def classify_query_intent(self, query):
        """
        Principled intent classification:
        - 'navigational': searching for official website, brand portal, or login
        - 'informational': searching for explanations, tutorials, guides, definitions, history
        - 'news': time-sensitive search for current events or recent articles
        - 'general': broad search
        """
        if not query or not query.strip():
            return {"type": "general", "brand": "", "action": "", "terms": [], "has_info": False}

        q_lower = query.lower().strip()
        raw_tokens = re.findall(r"\b[a-zA-Z0-9]+\b", q_lower)
        if not raw_tokens:
            return {"type": "general", "brand": "", "action": "", "terms": [], "has_info": False}

        informational_markers = {
            "what", "how", "why", "who", "when", "where",
            "history", "timeline", "origin", "evolution", "background",
            "tutorial", "guide", "learn", "course", "beginner", "introduction",
            "overview", "definition", "meaning", "explanation", "difference",
            "example", "examples", "documentation", "docs", "manual", "spec",
        }

        navigational_markers = {
            "login", "signin", "portal", "home", "homepage",
            "official", "website", "account", "download", "app"
        }

        news_markers = {
            "latest", "news", "recent", "breaking", "today", "updates", "headlines"
        }

        has_news = any(t in news_markers for t in raw_tokens)
        has_info = any(t in informational_markers for t in raw_tokens) or (
            len(raw_tokens) >= 2 and raw_tokens[0] == "what" and raw_tokens[1] == "is"
        )
        has_nav = any(t in navigational_markers for t in raw_tokens)

        brand_candidates = [
            t for t in raw_tokens
            if t not in self.stop_words
            and t not in informational_markers
            and t not in navigational_markers
            and t not in news_markers
        ]
        brand = brand_candidates[0] if brand_candidates else ""
        action = next((t for t in raw_tokens if t in navigational_markers), "")

        if has_news:
            intent_type = "news"
        elif has_info:
            intent_type = "informational"
        elif has_nav or (len(raw_tokens) <= 2 and brand):
            intent_type = "navigational"
        else:
            intent_type = "general"

        return {
            "type": intent_type,
            "brand": brand,
            "action": action,
            "terms": raw_tokens,
            "has_info": has_info,
            "has_nav": has_nav,
            "has_news": has_news,
        }

    def calculate_navigational_boost(self, url, title, query, intent=None):
        """
        Compute domain authority and navigational intent boost.
        - Navigational query: official domain and portal are rewarded (+0.50 to +0.80).
        - Informational query: navigational destination bonus is suppressed (0.0),
          so articles, guides, and tutorials can legitimately outrank bare home/login pages.
        """
        if not url or not query:
            return 0.0

        if intent is None:
            intent = self.classify_query_intent(query)

        # In informational queries (e.g. "what is LinkedIn", "LinkedIn history", "Python beginner tutorial"),
        # do NOT artificially inflate the bare root domain or login portal.
        if intent["type"] == "informational":
            return 0.0

        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if host.startswith("www."):
                host = host[4:]
            path = (parsed.path or "").strip("/").lower()
        except Exception:
            return 0.0

        q_clean = query.lower().strip()
        q_tokens = [w for w in re.findall(r"\b[a-zA-Z0-9]+\b", q_clean) if len(w) > 1]
        if not q_tokens:
            return 0.0

        domain_parts = host.split(".")
        root_name = domain_parts[0] if domain_parts else host

        boost = 0.0
        brand = intent.get("brand", "")
        action = intent.get("action", "")

        # Exact match with domain root (e.g. query 'linkedin' -> host 'linkedin.com')
        is_exact_domain = (q_clean == root_name or q_clean == host or (brand and brand == root_name))
        if is_exact_domain:
            boost += 0.55
            # If query explicitly asked for an action (e.g. 'login') and path matches:
            if action and action in path:
                boost += 0.25
            elif not path or path in ("login", "home", "index.html", "feed"):
                boost += 0.20
        elif any(t == root_name for t in q_tokens):
            boost += 0.35

        # Title starts with brand/query
        title_lower = (title or "").lower().strip()
        if brand and title_lower.startswith(brand):
            boost += 0.15
        elif title_lower.startswith(q_clean):
            boost += 0.15

        # For pure navigational searches, downweight secondary encyclopedias
        if "wikipedia.org" in host and "wiki" not in q_tokens and "wikipedia" not in q_tokens:
            boost -= 0.25

        return boost

    # ---------------------------------------------------------
    # CANDIDATE RETRIEVAL & QUERY EXPANSION
    # ---------------------------------------------------------

    def expand_query_words(self, query_words):
        """
        Expand query words with prefix matches in the inverted index so partial
        queries like 'darsha' match indexed terms like 'darshan'.
        """
        scoring_words = list(query_words)
        for word in query_words:
            if word not in self.index.index and len(word) >= 3:
                prefix_matches = [
                    k for k in self.index.index.keys()
                    if k.startswith(word)
                ]
                prefix_matches.sort(
                    key=lambda k: len(self.index.index[k]),
                    reverse=True,
                )
                for match in prefix_matches[:5]:
                    if match not in scoring_words:
                        scoring_words.append(match)
        return scoring_words

    def get_candidate_documents(self, query_words):
        if not query_words:
            return set()

        unique_words = list(dict.fromkeys(query_words))
        candidate_documents = set()
        for word in unique_words:
            exact = self.index.index.get(word)
            if exact:
                candidate_documents.update(exact)
            elif len(word) >= 3:
                for k, doc_ids in self.index.index.items():
                    if k.startswith(word):
                        candidate_documents.update(doc_ids)

        return candidate_documents

    # ---------------------------------------------------------
    # SNIPPET GENERATION
    # ---------------------------------------------------------

    def generate_snippet(self, document, query_words):
        text = document.get("text", "").strip()

        if not text:
            return ""

        if not query_words:
            return text[:300]

        lower_text = text.lower()
        positions = []

        for word in query_words:
            position = lower_text.find(word)

            if position != -1:
                positions.append(position)

        if not positions:
            return text[:300]

        position = min(positions)
        start = max(0, position - 120)
        end = min(len(text), position + 220)

        snippet = text[start:end].strip()

        if start > 0:
            snippet = "..." + snippet

        if end < len(text):
            snippet += "..."

        return snippet

    # ---------------------------------------------------------
    # MAIN SEARCH
    # ---------------------------------------------------------

    def search(self, query):
        if not query or not query.strip():
            return []

        query = query.strip()
        query_words = list(dict.fromkeys(self.tokenize(query)))
        if not query_words:
            return []

        scoring_words = self.expand_query_words(query_words)
        candidate_documents = self.get_candidate_documents(scoring_words)
        if not candidate_documents:
            return []

        self._ensure_corpus_cache()
        average_length = self._average_length
        idf_cache = {
            word: self.calculate_idf(word)
            for word in scoring_words
        }

        intent = self.classify_query_intent(query)

        results = []
        for document_id in candidate_documents:
            document = self.index.documents.get(document_id)
            if document is None:
                continue

            bm25 = self.bm25_score(
                document_id, scoring_words, average_length, idf_cache
            )
            title = self.title_score(document, query_words, query)
            phrase = self.phrase_score(document, query)
            coverage = self.term_coverage_score(document, query_words)
            pagerank = max(
                0.0, self.page_ranks.get(document.get("url", ""), 0.0)
            )

            bm25_normalized = self.normalize_bm25(bm25)
            pagerank_normalized = self.normalize_pagerank(pagerank)
            nav_boost = self.calculate_navigational_boost(
                document.get("url", ""), document.get("title", ""), query, intent=intent
            )
            url_relevance = self.url_relevance_score(
                document.get("url", ""), query_words
            )
            spam_penalty = self.detect_spam_penalty(document, query_words)

            final_score = (
                0.35 * bm25_normalized * (0.4 + 0.6 * coverage)
                + 0.25 * title
                + 0.15 * phrase
                + 0.05 * pagerank_normalized
                + nav_boost
                + url_relevance
                - spam_penalty
            )

            snippet = self.generate_snippet(document, scoring_words)
            results.append({
                "id": document_id,
                "title": document.get("title", ""),
                "url": document.get("url", ""),
                "score": round(final_score, 4),
                "bm25": round(bm25, 4),
                "bm25_normalized": round(bm25_normalized, 4),
                "title_score": round(title, 4),
                "phrase_score": round(phrase, 4),
                "term_coverage": round(coverage, 4),
                "url_relevance": round(url_relevance, 4),
                "pagerank": round(pagerank, 6),
                "pagerank_normalized": round(pagerank_normalized, 4),
                "nav_boost": round(nav_boost, 4),
                "intent": intent["type"],
                "text": snippet,
            })

        results.sort(
            key=lambda result: (
                -result["score"],
                -result["pagerank"],
                result["id"],
            )
        )
        return results
