# Write-up

## How the scraper works

The scraper is three independent site-specific modules (`campus_board.py`,
`cafe_chain.py`, `city_board.py`) sharing one base class (`base.py`) and one
output schema (`schema.py`).

**Design choice:** each site gets its own scraper rather than one generic
scraper, because real job sites don't share markup — a university board uses
`<div class="job-card">`, a chain's careers page uses a `<ul>`/`<li>` list
with labelled detail rows (`<strong>Pay:</strong> ...`), and a city board
uses a plain HTML `<table>`. Trying to handle all three with one generic
parser would mean fragile heuristics; instead, each parser is written
against its site's actual structure and mapped into one common `Listing`
dataclass afterward.

**The crawl loop** (`BaseScraper.run()`) is shared across all three: fetch a
page → parse it → catch and log any parse failure for a single page without
killing the whole run → move to the next page → dedupe by a stable hash of
`(source_site, source_url, title)` at the end, so re-running the scraper
upserts rather than duplicates.

**Politeness/robustness:** live mode sends a descriptive User-Agent, waits
1–2.5s between requests, and retries a failed fetch once before giving up
on that page. Malformed individual listings (missing a title, say) are
skipped with a logged warning rather than crashing the page.

**Normalization:** free-text pay strings (`"$16-18/hr"`, `"$36000-40000/year"`)
and dates (`"3 days ago"`, `"09/22/2026"`, `"Today"`) are parsed into
consistent numeric/ISO fields with regex-based best-effort parsing — falling
back to `None` rather than a wrong guess when a format isn't recognized.

**Sandbox note:** this environment's outbound network is restricted to a
package-registry allowlist, so the scraper ships in "fixture mode," reading
saved sample HTML that reproduces each site type's real structure, instead
of live URLs. The parsing code itself is unchanged between fixture and live
mode — see `README.md` for exactly what to flip to point it at real sites.

## Rationale for the 3 features

**1. Visa work-hour guardrail.** International students on a study visa
usually have a hard weekly cap on term-time work hours — and violating it
can jeopardize their immigration status, which is a much higher-stakes
mistake than a bad job fit. Generic job boards have no concept of this at
all. The tool lets a student stack multiple part-time/casual roles and
immediately see whether the combined hours would put them over their
stated cap, with a plain-language nudge to confirm anything full-time or
internship-shaped with their university's international office before
accepting — since those usually only count toward the cap under specific
program rules (CPT/co-op/vacation-period exceptions).

**2. Commute & campus proximity matching.** Many international students
arrive without a car and without local knowledge of a new city's transit
system, so a job across town is a very different proposition for them than
for a domestic student with a car and a lifetime of local geography. The
tool computes walk and transit time from a home base to each candidate
listing, so "is this job actually reachable on my schedule" is answered
before, not after, applying.

**3. Employer trust signals.** International students are a
disproportionate target for job scams, precisely because they lack a local
network to informally vet an unfamiliar employer the way a domestic student
might ("my roommate's cousin works there"). Rather than a binary
verified/unverified flag, every listing gets a 0–100 trust score computed
at scrape time from concrete, explainable signals: whether the employer
matches a known-legitimate set, whether the listing text contains common
scam-request patterns (wire transfers, upfront fees, gift cards), whether
the location is suspiciously vague, and whether the pay is missing or
implausibly low. The score is deliberately framed as a relative risk signal
in the UI, not a certification of legitimacy — it's a starting point for
caution, not a substitute for it.
