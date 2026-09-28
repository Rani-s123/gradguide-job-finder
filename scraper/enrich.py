"""
Post-scrape enrichment: static heuristics for two of the three
candidate-designed features.

- Trust signals (Feature 3): flags a handful of concrete scam/quality
  patterns. Deliberately conservative — this scores relative risk
  signals, it does not claim to verify legitimacy.
- Visa/work-hour hint (Feature 1): a static per-listing hint about
  whether a role is described as on-campus / intern-eligible /
  unrestricted-in-holidays. The full guardrail (checking a specific
  student's hour cap against multiple jobs) happens in the backend at
  request time, since it depends on the logged-in student's own data.

Known-chain / trusted-employer list would, in production, be a real
maintained table (or a Google Business Profile / company registry
lookup). Here it's a small static set to demonstrate the mechanism.
"""

from typing import List
from .schema import Listing

KNOWN_CHAINS = {
    "bean & leaf",
    "riverdale university",
    "riverdale university library",
    "riverdale university it services",
    "dept. of biology, riverdale university",
    "riverdale university dining services",
    "riverdale university learning center",
    "office of admissions",
    "pulsefit riverdale",
    "riverdale arena",
}

SCAM_KEYWORDS = [
    "wire transfer", "send money", "pay a fee", "registration fee",
    "gift card", "processing fee", "no experience needed easy money",
]

ON_CAMPUS_KEYWORDS = ["on-campus", "on campus", "university", "campus employment"]
VISA_POSITIVE_KEYWORDS = ["counts toward visa", "visa work eligibility", "international students welcome"]


def score_trust(listing: Listing) -> None:
    score = 60  # neutral baseline
    flags = []

    employer_lower = listing.employer.lower()
    if employer_lower in KNOWN_CHAINS:
        score += 20
        flags.append("known_employer")
    else:
        flags.append("employer_unverified")

    text = f"{listing.title} {listing.description}".lower()
    if any(k in text for k in SCAM_KEYWORDS):
        score -= 40
        flags.append("scam_keyword_match")

    if not listing.location or listing.location.strip().lower() in ("remote", "various", "various - riverdale"):
        score -= 10
        flags.append("vague_location")

    if listing.pay_min is None:
        score -= 10
        flags.append("no_parsable_pay")
    elif listing.pay_period == "hour" and listing.pay_min < 12:
        score -= 15
        flags.append("pay_below_plausible_minimum")

    if not listing.description:
        score -= 5
        flags.append("no_description")

    score = max(0, min(100, score))
    listing.trust_score = score
    listing.trust_flags = ",".join(flags)


def hint_visa_friendly(listing: Listing) -> None:
    text = f"{listing.title} {listing.description} {listing.employer}".lower()
    if any(k in text for k in ON_CAMPUS_KEYWORDS) or any(k in text for k in VISA_POSITIVE_KEYWORDS):
        listing.visa_friendly_hint = True
    elif listing.source_site == "campus_board":
        # On-campus employment is generally the safest visa-hour category
        # for international students, regardless of exact wording.
        listing.visa_friendly_hint = True
    else:
        listing.visa_friendly_hint = None  # unknown, not "no" - avoid false negatives


def enrich_all(listings: List[Listing]) -> List[Listing]:
    for listing in listings:
        score_trust(listing)
        hint_visa_friendly(listing)
    return listings
