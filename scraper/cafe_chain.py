"""
Scraper for a cafe/retail chain's own careers page.

Real-world equivalent: local chain career pages (cafes, grocery,
retail) commonly list all open roles across their branches on one
page, often in a <ul>/<li> structure with a fixed set of "detail"
rows per role rather than one clean semantic field per element -
which is why this parser pulls detail text by label ("Pay:",
"Schedule:", "Date Listed:") instead of by CSS class.
"""

from pathlib import Path
from typing import Iterable, List
from bs4 import BeautifulSoup

from .base import BaseScraper
from .schema import Listing


class CafeChainScraper(BaseScraper):
    source_site = "cafe_chain"
    FIXTURE_DIR = Path(__file__).parent / "fixtures"
    BASE_URL = "https://beanandleaf.example.com"

    def page_urls(self) -> Iterable[str]:
        if self.FIXTURE_MODE:
            yield "cafe_chain_careers.html"
            return
        yield f"{self.BASE_URL}/careers"

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> List[Listing]:
        listings = []
        for role in soup.select("li.role"):
            name_el = role.select_one("span.role-name")
            loc_el = role.select_one("span.role-location")
            blurb_el = role.select_one("div.role-blurb")
            link_el = role.select_one("a.apply-btn")

            if not name_el:
                self.logger.warning("Skipping role with no name on %s", page_url)
                continue

            details = self._parse_detail_rows(role)

            role_id = role.get("id", "")
            source_url = self.BASE_URL + link_el["href"] if link_el else f"{self.BASE_URL}/{role_id}"

            listing = Listing(
                title=name_el.get_text(strip=True),
                employer="Bean & Leaf",
                location=loc_el.get_text(strip=True) if loc_el else "Riverdale",
                job_type=self._job_type_from_schedule(details.get("Schedule", "")),
                pay_raw=details.get("Pay", ""),
                posted_date=None,
                source_site=self.source_site,
                source_url=source_url,
                description=blurb_el.get_text(strip=True) if blurb_el else "",
            )
            self.enrich_pay(listing)
            self.enrich_date(listing, details.get("Date Listed", ""))
            listings.append(listing)

        return listings

    @staticmethod
    def _parse_detail_rows(role_el) -> dict:
        """
        Detail rows look like: <div class="detail"><strong>Pay:</strong> $16-18/hr</div>
        Pull them into {"Pay": "$16-18/hr", "Schedule": ..., "Date Listed": ...}
        by reading the <strong> label rather than relying on class names,
        since this site doesn't give each field its own class.
        """
        out = {}
        for row in role_el.select("div.detail"):
            label_el = row.select_one("strong")
            if not label_el:
                continue
            label = label_el.get_text(strip=True).rstrip(":")
            value = row.get_text(strip=True).replace(label_el.get_text(strip=True), "", 1).strip()
            out[label] = value
        return out

    @staticmethod
    def _job_type_from_schedule(schedule_text: str) -> str:
        s = schedule_text.lower()
        if "full-time" in s:
            return "full-time"
        if "casual" in s:
            return "casual"
        return "part-time"
