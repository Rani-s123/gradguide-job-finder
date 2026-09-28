"""
Run all scrapers and write results to the SQLite DB the backend reads from.

Usage:
    python -m scraper.run_scraper

Re-running is safe: listings are upserted by their stable listing_id
(a hash of source_site + source_url + title), so re-scraping doesn't
create duplicates - it just refreshes existing rows.
"""

import sqlite3
from pathlib import Path

from .campus_board import CampusBoardScraper
from .cafe_chain import CafeChainScraper
from .city_board import CityBoardScraper
from .enrich import enrich_all

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"

SCRAPERS = [CampusBoardScraper, CafeChainScraper, CityBoardScraper]

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    listing_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    employer TEXT NOT NULL,
    location TEXT NOT NULL,
    job_type TEXT NOT NULL,
    pay_raw TEXT,
    pay_min REAL,
    pay_max REAL,
    pay_period TEXT,
    posted_date TEXT,
    source_site TEXT NOT NULL,
    source_url TEXT NOT NULL,
    description TEXT,
    visa_friendly_hint INTEGER,
    trust_score INTEGER,
    trust_flags TEXT,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_job_type ON listings(job_type);
CREATE INDEX IF NOT EXISTS idx_source_site ON listings(source_site);
"""


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def upsert_listings(conn, listings):
    rows = [
        (
            l.listing_id, l.title, l.employer, l.location, l.job_type,
            l.pay_raw, l.pay_min, l.pay_max, l.pay_period, l.posted_date,
            l.source_site, l.source_url, l.description,
            None if l.visa_friendly_hint is None else int(l.visa_friendly_hint),
            l.trust_score, l.trust_flags,
        )
        for l in listings
    ]
    conn.executemany(
        """
        INSERT INTO listings (
            listing_id, title, employer, location, job_type,
            pay_raw, pay_min, pay_max, pay_period, posted_date,
            source_site, source_url, description,
            visa_friendly_hint, trust_score, trust_flags
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(listing_id) DO UPDATE SET
            pay_raw=excluded.pay_raw, pay_min=excluded.pay_min, pay_max=excluded.pay_max,
            pay_period=excluded.pay_period, posted_date=excluded.posted_date,
            description=excluded.description, trust_score=excluded.trust_score,
            trust_flags=excluded.trust_flags, scraped_at=CURRENT_TIMESTAMP
        """,
        rows,
    )
    conn.commit()


def main():
    all_listings = []
    for ScraperCls in SCRAPERS:
        scraper = ScraperCls()
        print(f"\n=== Running {scraper.source_site} ===")
        listings = scraper.run()
        all_listings.extend(listings)

    print(f"\nEnriching {len(all_listings)} listings (trust score, visa hint)...")
    enrich_all(all_listings)

    conn = get_connection()
    upsert_listings(conn, all_listings)
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    conn.close()

    print(f"\nDone. {len(all_listings)} listings scraped this run, {count} total in DB at {DB_PATH}")


if __name__ == "__main__":
    main()
