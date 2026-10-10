import pytest
from app.search.image_scorer import ImageRelevanceScorer


class TestImageRelevanceScorer:
    """Deterministic image-search test corpus verifying relevant vs irrelevant images."""

    CORPUS = [
        # Known relevant to 'LinkedIn'
        {
            "id": 1,
            "title": "LinkedIn Official Brand Logo",
            "alt_text": "LinkedIn blue square emblem and wordmark",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/c/ca/LinkedIn_logo_initials.png",
            "source_page_title": "LinkedIn: Log In or Sign Up",
            "width": 600,
            "height": 600,
        },
        # Known relevant to 'Python'
        {
            "id": 2,
            "title": "Python Programming Language Logo",
            "alt_text": "Python official blue and yellow snake logo",
            "image_url": "https://www.python.org/static/community_logos/python-logo-master-v3-TM.png",
            "source_page_title": "Welcome to Python.org",
            "width": 800,
            "height": 250,
        },
        # Known relevant to 'Nebula space'
        {
            "id": 3,
            "title": "Orion Nebula Deep Space Cosmic Gas",
            "alt_text": "Hubble telescope view of glowing interstellar Orion nebula dust",
            "image_url": "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?w=800",
            "source_page_title": "NASA Astronomy Picture of the Day",
            "width": 1200,
            "height": 800,
        },
        # Known completely IRRELEVANT to 'LinkedIn' (Earth night photo from space)
        {
            "id": 4,
            "title": "Planet Earth City Lights at Night from Orbit",
            "alt_text": "Night view of Earth continents from space satellite orbit",
            "image_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800",
            "source_page_title": "Orbit Geography Archive",
            "width": 1200,
            "height": 800,
        },
        # Tracking pixel (should be filtered for all queries)
        {
            "id": 5,
            "title": "LinkedIn Tracker",
            "alt_text": "linkedin pixel",
            "image_url": "https://analytics.example.com/tracking/1x1.png",
            "source_page_title": "Tracking",
            "width": 1,
            "height": 1,
        },
    ]

    def test_linkedin_query_ranks_relevant_and_excludes_irrelevant(self):
        ranked = ImageRelevanceScorer.rank_and_filter_images("LinkedIn", self.CORPUS)
        assert len(ranked) > 0, "Expected at least 1 relevant image for 'LinkedIn'"
        # Top image must be the LinkedIn brand logo
        assert ranked[0]["id"] == 1
        assert "LinkedIn" in ranked[0]["title"]
        # The unrelated space photo of Earth (id 4) must be excluded!
        returned_ids = [img["id"] for img in ranked]
        assert 4 not in returned_ids, "Unrelated space photo must be excluded from LinkedIn search"
        # The 1x1 tracker must be filtered out
        assert 5 not in returned_ids, "Tracking pixel must be filtered out"

    def test_python_query_ranks_python_logo_first(self):
        ranked = ImageRelevanceScorer.rank_and_filter_images("Python", self.CORPUS)
        assert len(ranked) > 0
        assert ranked[0]["id"] == 2
        assert "Python" in ranked[0]["title"]
        returned_ids = [img["id"] for img in ranked]
        assert 4 not in returned_ids, "Earth space photo must be excluded from Python search"

    def test_nebula_query_ranks_space_nebula_and_excludes_brand_logos(self):
        ranked = ImageRelevanceScorer.rank_and_filter_images("Nebula space", self.CORPUS)
        assert len(ranked) > 0
        assert ranked[0]["id"] == 3
        assert "Nebula" in ranked[0]["title"]
        returned_ids = [img["id"] for img in ranked]
        assert 1 not in returned_ids, "LinkedIn logo must be excluded from Nebula search"
        assert 2 not in returned_ids, "Python logo must be excluded from Nebula search"

    def test_empty_state_when_no_relevant_image_exists(self):
        # Searching for something completely absent from the image corpus
        ranked = ImageRelevanceScorer.rank_and_filter_images("Quantum Submarine Archaeology", self.CORPUS)
        # Must return empty list instead of arbitrary unrelated fallback images!
        assert len(ranked) == 0, f"Expected empty list for non-matching query, got {ranked}"

    def test_deduplication_removes_duplicate_urls(self):
        corpus_with_dupes = self.CORPUS + [
            {
                "id": 99,
                "title": "LinkedIn Duplicate",
                "alt_text": "LinkedIn logo copy",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/c/ca/LinkedIn_logo_initials.png?utm_source=test",
                "source_page_title": "Another page",
                "width": 600,
                "height": 600,
            }
        ]
        ranked = ImageRelevanceScorer.rank_and_filter_images("LinkedIn", corpus_with_dupes)
        image_urls = [img["image_url"] for img in ranked]
        assert len(image_urls) == 1, "Expected deduplication of identical image URL"
