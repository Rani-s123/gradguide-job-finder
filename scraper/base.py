"""
Base scraper.

Each site-specific scraper subclasses BaseScraper and implements
`fetch_pages()` and `parse_page(html, page_url)`. This class handles
the shared plumbing: polite request pacing, retry-once-on-failure,
and a `fixture` mode used in this sandbox (see README for why).
"""

from __future__ import annotations
import time
import random
import logging
from pathlib import Path
from typing import Iterable, List
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

from .schema import Listing, parse_pay, normalize_date

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

USER_AGENT = "GradGuideJobBot/1.0 (+contact: you@example.com; respects robots.txt)"


class RobotsChecker:
    """
    Caches one RobotFileParser per domain so we only fetch /robots.txt
    once per site per run, then answer can_fetch() for every subsequent
    URL on that domain. If robots.txt can't be fetched at all, we fail
    open (allow) rather than blocking the whole scrape on a network
    hiccup - the same behavior requests-respecting scrapers commonly use.
    """
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}

    def _parser_for(self, url: str) -> RobotFileParser:
        domain = urlparse(url).netloc
        if domain not in self._parsers:
            rp = RobotFileParser()
            robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
            try:
                rp.set_url(robots_url)
                rp.read()
            except Exception:
                rp = None  # treat unreadable robots.txt as "no restrictions"
            self._parsers[domain] = rp
        return self._parsers[domain]

    def can_fetch(self, url: str) -> bool:
        rp = self._parser_for(url)
        if rp is None:
            return True
        try:
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return True


class BaseScraper:
    source_site: str = "base"
    # Set to a local fixture directory to scrape saved HTML instead of the
    # live web. In this sandboxed environment, network access is restricted
    # to a small allowlist that does not include job boards, so fixture
    # mode is used here. On a normal machine, set FIXTURE_MODE = False and
    # this same parsing code runs against `requests.get(real_url)`.
    FIXTURE_MODE = True
    FIXTURE_DIR: Path | None = None

    REQUEST_DELAY_RANGE = (1.0, 2.5)  # seconds, politeness delay between requests

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.logger = logging.getLogger(self.source_site)
        self.robots = RobotsChecker(USER_AGENT)

    # ---- to be implemented by subclasses ----
    def page_urls(self) -> Iterable[str]:
        """URLs (or fixture filenames) to fetch, in order."""
        raise NotImplementedError

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> List[Listing]:
        """Turn a parsed page into a list of Listing objects."""
        raise NotImplementedError

    # ---- shared machinery ----
    def get_html(self, url_or_filename: str) -> str:
        if self.FIXTURE_MODE:
            path = self.FIXTURE_DIR / url_or_filename
            return path.read_text(encoding="utf-8")

        # Live mode: check robots.txt before every fetch, then a real
        # HTTP fetch with a polite delay and one retry.
        if not self.robots.can_fetch(url_or_filename):
            self.logger.warning("Skipping %s - disallowed by robots.txt", url_or_filename)
            raise RuntimeError(f"Blocked by robots.txt: {url_or_filename}")

        for attempt in range(2):
            try:
                resp = self.session.get(url_or_filename, timeout=15)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as e:
                self.logger.warning("fetch failed (attempt %d): %s", attempt + 1, e)
                time.sleep(2)
        raise RuntimeError(f"Could not fetch {url_or_filename} after retries")

    def run(self) -> List[Listing]:
        all_listings: List[Listing] = []
        for i, url in enumerate(self.page_urls()):
            self.logger.info("Fetching page %d: %s", i + 1, url)
            html = self.get_html(url)
            soup = BeautifulSoup(html, "html.parser")
            try:
                listings = self.parse_page(soup, url)
            except Exception as e:
                # A single malformed page/listing should not kill the whole run.
                self.logger.error("Failed to parse %s: %s", url, e)
                listings = []
            self.logger.info("  -> parsed %d listings", len(listings))
            all_listings.extend(listings)

            if not self.FIXTURE_MODE:
                time.sleep(random.uniform(*self.REQUEST_DELAY_RANGE))

        return self.dedupe(all_listings)

    @staticmethod
    def dedupe(listings: List[Listing]) -> List[Listing]:
        seen = set()
        out = []
        for l in listings:
            if l.listing_id in seen:
                continue
            seen.add(l.listing_id)
            out.append(l)
        return out

    @staticmethod
    def enrich_pay(listing: Listing) -> None:
        lo, hi, period = parse_pay(listing.pay_raw)
        listing.pay_min, listing.pay_max, listing.pay_period = lo, hi, period

    @staticmethod
    def enrich_date(listing: Listing, raw_date: str) -> None:
        listing.posted_date = normalize_date(raw_date)
