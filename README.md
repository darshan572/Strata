# Strata Search Engine (Strata + SylvaSearch Engine)

A custom, end-to-end full-stack search engine with an authentic, responsive React interface connected directly to a high-performance Python information retrieval backend.

---

## Architecture Overview

```
Strata/
├── src/                                  # React 19 + TypeScript + Vite Frontend
│   ├── components/
│   │   ├── Header.tsx                    # Omnibar search, suggestions, category tabs
│   │   ├── SearchResultItem.tsx          # Result cards with explainable BM25 + PageRank pills
│   │   ├── KnowledgePanel.tsx            # Dynamic entity knowledge cards & image galleries
│   │   ├── CrawlerModal.tsx              # Live crawler trigger, frontier stats & PageRank graph
│   │   ├── LandingPage.tsx               # Minimalist hero search experience
│   │   └── Sidebar.tsx                   # Category drawer / column
│   ├── services/
│   │   └── api.ts                        # Robust API client with auto fallback & proxy routing
│   ├── types/                            # Typed models for documents, ranking & graphs
│   └── App.tsx                           # Main application coordinating search & engine health
├── sylvasearch/backend/                  # FastAPI Search Engine Backend
│   ├── app/
│   │   ├── crawler/                      # Polite crawler with robots.txt & per-host pacing
│   │   ├── indexer/                      # In-memory Inverted Index with posting lists
│   │   ├── search/
│   │   │   ├── engine.py                 # Multi-signal ranker: BM25 (55%), Title (25%), Phrase (15%), PageRank (5%)
│   │   │   └── pagerank.py               # Power iteration PageRank (d=0.85) on link graph
│   │   ├── database.py                   # SQLite in WAL mode with frontier crash recovery
│   │   └── main.py                       # REST API endpoints & CORS middleware
│   └── data/
│       └── sylvasearch.db                # Corpus database (185 docs, 161,408 links)
└── vite.config.ts                        # Configured with proxy routes to backend port 8000
```

---

## Multi-Factor Ranking Formulation

Results are scored dynamically using the composite formula:

$$\text{Final Score} = 0.55 \cdot \text{BM25}_{\text{norm}} + 0.25 \cdot \text{Title Match} + 0.15 \cdot \text{Phrase Match} + 0.05 \cdot \text{PageRank}_{\text{norm}}$$

Each result card displays an explainable pill with its individual scores for complete transparency.

---

## Quickstart Guide

### Option A: One-Click Launch (Recommended)
Double-click `start.bat` in the project root, or execute:
```cmd
.\start.bat
```
*This launches both the FastAPI engine and the Vite React frontend in separate terminal windows and automatically opens [http://127.0.0.1:5173](http://127.0.0.1:5173) in your default browser.*

### Option B: Manual Launch
1. **Start Backend Engine:**
   ```powershell
   cd sylvasearch/backend
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. **Start Frontend Interface:**
   ```powershell
   npm run dev
   ```

---

## Features

- **Live In-Memory BM25 Search**: Instant sub-millisecond query execution over indexed web pages.
- **Explainable Ranking**: See composite scores, BM25 weights, and PageRank authority for every result.
- **Engine Controller Console**: Click `Crawler & Frontier` in the top bar to:
  - Trigger polite crawls on any seed URL.
  - Monitor frontier queue jobs (`pending`, `processing`, `crawled`, `failed`).
  - View top PageRank authority leaderboard across 161,408 graph edges.
- **Dynamic Knowledge Graph**: Automatically generates entity overview cards (Python language specifications, PEPs, space phenomena).
- **Graceful Fault Tolerance**: If the backend is ever offline, the interface seamlessly falls back to local cache so user workflows never crash.
