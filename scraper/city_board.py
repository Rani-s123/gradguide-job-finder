"""
Scraper for a local city job board that lists casual/part-time/full-time
work in a plain HTML table - a common pattern for smaller, older
community job boards that predate modern job-board SaaS products.
"""

from pathlib import Path
from typing import Iterable, List
from bs4 import BeautifulSoup

from .base import BaseScraper
from .schema import Listing


class CityBoardScraper(BaseScraper):
    source_site = "city_board"
    FIXTURE_DIR = Path(__file__).parent / "fixtures"
    BASE_URL = "https://riverdalejobs.local"

    def page_urls(self) -> Iterable[str]:
        if self.FIXTURE_MODE:
            yield "city_board_listings.html"
            return
        yield f"{self.BASE_URL}/listings"

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> List[Listing]:
        listings = []
        rows = soup.select("tr.listing-row")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 6:
                self.logger.warning("Skipping malformed row on %s", page_url)
                continue

            title_cell, employer_cell, area_cell, rate_cell, type_cell, when_cell = cells[:6]
            link_el = title_cell.select_one("a")

            row_id = row.get("data-id", "")
            source_url = self.BASE_URL + link_el["href"] if link_el else f"{self.BASE_URL}/{row_id}"

            listing = Listing(
                title=title_cell.get_text(strip=True),
                employer=employer_cell.get_text(strip=True),
                location=area_cell.get_text(strip=True),
                job_type=type_cell.get_text(strip=True),
                pay_raw=rate_cell.get_text(strip=True),
                posted_date=None,
                source_site=self.source_site,
                source_url=source_url,
                description="",  # this board doesn't give a description on the listing page
            )
            self.enrich_pay(listing)
            self.enrich_date(listing, when_cell.get_text(strip=True))
            listings.append(listing)

        return listings
