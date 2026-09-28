"""
Common listing schema.

Every site-specific scraper maps its own HTML into this shape before
it gets written to the database. This is what makes it possible to
search/filter across sites that have wildly different page structures.
"""

from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Optional
import hashlib
import re


VALID_JOB_TYPES = {"part-time", "full-time", "internship", "casual"}


@dataclass
class Listing:
    title: str
    employer: str
    location: str
    job_type: str            # one of VALID_JOB_TYPES
    pay_raw: str              # exactly as it appeared on the page, e.g. "$22-25/hr"
    posted_date: Optional[str]  # ISO date string, best-effort parsed
    source_site: str          # short key, e.g. "campus_board"
    source_url: str
    description: str = ""

    # --- derived / enrichment fields, filled in after scraping ---
    pay_min: Optional[float] = None
    pay_max: Optional[float] = None
    pay_period: Optional[str] = None   # "hour" | "year" | "unknown"
    visa_friendly_hint: Optional[bool] = None  # heuristic, see enrich.py
    trust_score: Optional[int] = None          # 0-100, see enrich.py
    trust_flags: str = ""                      # comma-joined reasons
    listing_id: str = ""                        # stable hash, set in __post_init__

    def __post_init__(self):
        if not self.listing_id:
            key = f"{self.source_site}|{self.source_url}|{self.title}"
            self.listing_id = hashlib.sha256(key.encode()).hexdigest()[:16]
        self.job_type = self.job_type.lower().strip()
        if self.job_type not in VALID_JOB_TYPES:
            # fall back to a best guess rather than dropping the listing
            self.job_type = _guess_job_type(self.title + " " + self.description)

    def as_dict(self):
        return asdict(self)


def _guess_job_type(text: str) -> str:
    t = text.lower()
    if "intern" in t:
        return "internship"
    if "casual" in t or "gig" in t or "on-call" in t:
        return "casual"
    if "part-time" in t or "part time" in t:
        return "part-time"
    return "full-time"


PAY_RANGE_RE = re.compile(
    r"\$?\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:/|per)?\s*(hr|hour|yr|year|annum)?",
    re.IGNORECASE,
)
PAY_SINGLE_RE = re.compile(
    r"\$?\s*(\d+(?:\.\d+)?)\s*(?:/|per)?\s*(hr|hour|yr|year|annum)?",
    re.IGNORECASE,
)


def parse_pay(pay_raw: str):
    """Best-effort extraction of (min, max, period) from free-text pay strings."""
    if not pay_raw:
        return None, None, None
    m = PAY_RANGE_RE.search(pay_raw)
    if m:
        lo, hi, unit = m.groups()
        period = _normalize_period(unit)
        return float(lo), float(hi), period
    m = PAY_SINGLE_RE.search(pay_raw)
    if m:
        val, unit = m.groups()
        period = _normalize_period(unit)
        return float(val), float(val), period
    return None, None, None


def _normalize_period(unit: Optional[str]) -> str:
    if not unit:
        return "unknown"
    unit = unit.lower()
    if unit in ("hr", "hour"):
        return "hour"
    if unit in ("yr", "year", "annum"):
        return "year"
    return "unknown"


def normalize_date(raw: str) -> Optional[str]:
    """
    Sites express dates inconsistently ('2 days ago', 'Posted 09/12/2026',
    '12 Sep'). This tries a few common patterns and falls back to None
    rather than guessing — a missing date is safer than a wrong one.
    """
    if not raw:
        return None
    raw = raw.strip()

    # "X days/weeks ago"
    m = re.search(r"(\d+)\s*day", raw, re.IGNORECASE)
    if m:
        from datetime import timedelta
        d = date.today() - timedelta(days=int(m.group(1)))
        return d.isoformat()
    m = re.search(r"(\d+)\s*week", raw, re.IGNORECASE)
    if m:
        from datetime import timedelta
        d = date.today() - timedelta(weeks=int(m.group(1)))
        return d.isoformat()
    if "today" in raw.lower():
        return date.today().isoformat()
    if "yesterday" in raw.lower():
        from datetime import timedelta
        return (date.today() - timedelta(days=1)).isoformat()

    # explicit formats
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue

    return None
