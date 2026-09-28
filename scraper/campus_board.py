"""
Scraper for a university campus job board.

Real-world equivalent: most universities publish student jobs on a
public board like this (Handshake-style or homegrown). Markup here is
div/span based with class names, spread across a couple of pages via
a "next page" link.

To point this at a live board: set FIXTURE_MODE = False and change
page_urls() to yield the real URL(s), following the "next page" link
found in each page's HTML until it disappears (see the live-mode
branch below — the pagination-following logic is already written).
"""

from pathlib import Path
from typing import Iterable, List
from bs4 import BeautifulSoup

from .base import BaseScraper
from .schema import Listing


class CampusBoardScraper(BaseScraper):
    source_site = "campus_board"
    FIXTURE_DIR = Path(__file__).parent / "fixtures"
    BASE_URL = "https://jobs.riverdale.edu"  # illustrative; not fetched in fixture mode

    def page_urls(self) -> Iterable[str]:
        if self.FIXTURE_MODE:
            # Fixture mode just lists the saved pages in order.
            yield "campus_board_page1.html"
            yield "campus_board_page2.html"
            return

        # Live mode: start at page 1 and follow the "next page" link
        # until the page no longer has one. This mirrors how a real
        # crawl loop works for this kind of board.
        next_url = f"{self.BASE_URL}/student-jobs"
        seen = set()
        while next_url and next_url not in seen:
            seen.add(next_url)
            yield next_url
            html = self.get_html(next_url)
            soup = BeautifulSoup(html, "html.parser")
            next_link = soup.select_one("a.next-page")
            next_url = next_link["href"] if next_link else None
            if next_url and not next_url.startswith("http"):
                next_url = self.BASE_URL + next_url

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> List[Listing]:
        listings = []
        for card in soup.select("div.job-card"):
            title_el = card.select_one("h3.job-title")
            employer_el = card.select_one("span.employer")
            location_el = card.select_one("span.location")
            pay_el = card.select_one("span.pay")
            type_el = card.select_one("span.type")
            posted_el = card.select_one("span.posted")
            desc_el = card.select_one("p.job-desc")
            link_el = card.select_one("a.job-link")

            if not title_el or not employer_el:
                # Skip malformed cards rather than crashing the whole run.
                self.logger.warning("Skipping malformed card on %s", page_url)
                continue

            job_id = card.get("data-job-id", "")
            source_url = self.BASE_URL + link_el["href"] if link_el else f"{self.BASE_URL}/{job_id}"

            listing = Listing(
                title=title_el.get_text(strip=True),
                employer=employer_el.get_text(strip=True),
                location=location_el.get_text(strip=True) if location_el else "Riverdale",
                job_type=type_el.get_text(strip=True) if type_el else "part-time",
                pay_raw=pay_el.get_text(strip=True) if pay_el else "",
                posted_date=None,
                source_site=self.source_site,
                source_url=source_url,
                description=desc_el.get_text(strip=True) if desc_el else "",
            )
            self.enrich_pay(listing)
            self.enrich_date(listing, posted_el.get_text(strip=True) if posted_el else "")
            listings.append(listing)

        return listings
