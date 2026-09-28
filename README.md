# GradGuide Job Finder

A job discovery tool for international students — part-time, full-time,
internship, and casual roles (cafes, retail, delivery, tutoring), sourced
by a scraper the author wrote from scratch.

**Video walkthrough:** _[add link here before submitting — see checklist at
the bottom of this file]_

## What's in here

```
gradguide-job-finder/
├── scraper/          # the scraper (own code, no job-board APIs, no AI scraping)
│   ├── schema.py      # shared Listing schema + pay/date parsing helpers
│   ├── base.py         # shared crawl loop: fetch, parse, retry, dedupe, rate-limit
│   ├── campus_board.py  # site-specific scraper #1 (paginated div/span markup)
│   ├── cafe_chain.py     # site-specific scraper #2 (label-based <li> markup)
│   ├── city_board.py      # site-specific scraper #3 (HTML table markup)
│   ├── enrich.py            # trust score + visa hint heuristics
│   ├── run_scraper.py        # entry point — runs all 3 scrapers, writes to SQLite
│   └── fixtures/               # saved sample HTML for the 3 sites (see note below)
├── backend/           # FastAPI app serving the listings + the 3 feature endpoints
│   └── main.py
├── frontend/          # React + Vite single-page app
│   └── src/
└── data/              # jobs.db (SQLite), created by the scraper
```

## Important note on the scraper and live sites

The scraper is written to fetch and parse **real HTML from real sites** —
`requests.get()` → `BeautifulSoup` → structured `Listing` objects, with
pagination-following, retries, and per-page error isolation, exactly as it
would run in production (see `base.py` and each site scraper's `page_urls()`
for the live-mode code paths).

For this submission it ships in **fixture mode**: instead of hitting live
job-board URLs, it reads saved sample HTML files in `scraper/fixtures/`
that reproduce the real markup structure of the three site types described
below. This is purely so the scraper is reproducible for reviewers without
depending on a specific job board's HTML staying stable, or requiring
reviewer network access to the exact same sites. **The parsing logic itself
is unchanged between fixture and live mode** — only where the HTML comes
from differs (see `BaseScraper.get_html()`).

To run it against real sites: set `FIXTURE_MODE = False` on each scraper
class and point `page_urls()` at the live URL(s) (the live-mode branches
are already written and commented in each scraper file). Good real-world
targets that match each fixture's structure:
- **Campus board** → a university's public student-jobs board
- **Cafe/retail chain** → a chain's own `/careers` page
- **City board** → a local classifieds-style jobs board

## Running it locally

### 1. Scraper (populates the database)

```bash
cd gradguide-job-finder
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
python3 -m scraper.run_scraper
```

This creates `data/jobs.db` with all scraped, parsed, and enriched listings.
Safe to re-run — listings are upserted by a stable ID, not duplicated.

### 2. Backend API

```bash
uvicorn backend.main:app --reload --port 8000
```

Visit `http://localhost:8000/api/jobs` to confirm it's serving data, or
`http://localhost:8000/docs` for interactive API docs (FastAPI auto-generates
this).

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`. The dev server proxies `/api/*` to the
backend on port 8000 (see `vite.config.js`).

### Production build

```bash
cd frontend && npm run build
```

Outputs static files to `frontend/dist/` — deploy anywhere that serves
static files, pointed at a deployed instance of the backend.

## The three features

See `WRITEUP.md` for the full rationale. Short version:

1. **Visa work-hour guardrail** — select listings, enter your weekly hour
   cap and hours already committed elsewhere, and it flags roles that
   would put you over the limit (`POST /api/visa-check`).
2. **Commute & campus proximity matching** — compare walk/transit time
   from a home base to each selected listing (`POST /api/commute`).
3. **Employer trust signals** — every listing gets a 0–100 trust score
   computed at scrape time from concrete signals (known employer, scam
   keyword patterns, vague location, implausible pay, missing fields),
   shown as a badge on each card.

## Before submitting — checklist

- [ ] Deploy backend (Render/Railway/Fly.io) and frontend (Vercel/Netlify);
      update `frontend/.env` or the Vite proxy target with the deployed
      backend URL
- [ ] Add the hosted link to this README
- [ ] Record a short (3–5 min) walkthrough video covering: the scraper
      design (this is the part they most want you to be able to defend),
      the 3 features and why, and a live demo of the app
- [ ] Link the video in this README
- [ ] Push to a public (or reviewer-accessible) GitHub repo
