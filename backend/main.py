"""
GradGuide Job Finder - backend API.

Run with:
    uvicorn backend.main:app --reload --port 8000

Endpoints:
    GET  /api/jobs              - search/filter listings
    GET  /api/jobs/{listing_id} - single listing detail
    POST /api/commute           - compute commute time/distance for listings vs a student's address
    POST /api/visa-check        - check a set of jobs against a student's weekly hour cap
    GET  /api/meta              - filter option metadata (job types, sources, pay bounds)
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import math
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"

app = FastAPI(title="GradGuide Job Finder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the deployed frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# GET /api/jobs
# ---------------------------------------------------------------------------

@app.get("/api/jobs")
def list_jobs(
    q: Optional[str] = Query(None, description="keyword search over title/employer/description"),
    job_type: Optional[str] = Query(None, description="comma-separated: part-time,full-time,internship,casual"),
    source_site: Optional[str] = None,
    pay_min: Optional[float] = None,
    visa_friendly_only: bool = False,
    min_trust_score: Optional[int] = None,
    sort: str = Query("posted_date", description="posted_date | pay_min | trust_score"),
    order: str = Query("desc", description="asc | desc"),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    conn = get_conn()
    clauses, params = [], []

    if q:
        clauses.append("(title LIKE ? OR employer LIKE ? OR description LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    if job_type:
        types = [t.strip() for t in job_type.split(",") if t.strip()]
        placeholders = ",".join("?" for _ in types)
        clauses.append(f"job_type IN ({placeholders})")
        params.extend(types)

    if source_site:
        clauses.append("source_site = ?")
        params.append(source_site)

    if pay_min is not None:
        clauses.append("(pay_min IS NOT NULL AND pay_min >= ?)")
        params.append(pay_min)

    if visa_friendly_only:
        clauses.append("visa_friendly_hint = 1")

    if min_trust_score is not None:
        clauses.append("(trust_score IS NOT NULL AND trust_score >= ?)")
        params.append(min_trust_score)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    if sort not in ("posted_date", "pay_min", "trust_score"):
        sort = "posted_date"
    if order not in ("asc", "desc"):
        order = "desc"

    sql = f"""
        SELECT * FROM listings
        {where_sql}
        ORDER BY {sort} {order} NULLS LAST
        LIMIT ? OFFSET ?
    """
    params_full = params + [limit, offset]

    try:
        rows = conn.execute(sql, params_full).fetchall()
    except sqlite3.OperationalError:
        # older sqlite without NULLS LAST support - fall back
        sql = f"SELECT * FROM listings {where_sql} ORDER BY {sort} {order} LIMIT ? OFFSET ?"
        rows = conn.execute(sql, params_full).fetchall()

    total = conn.execute(f"SELECT COUNT(*) FROM listings {where_sql}", params).fetchone()[0]
    conn.close()

    return {
        "total": total,
        "count": len(rows),
        "results": [dict(r) for r in rows],
    }


@app.get("/api/jobs/{listing_id}")
def get_job(listing_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM listings WHERE listing_id = ?", (listing_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    return dict(row)


@app.get("/api/meta")
def meta():
    conn = get_conn()
    job_types = [r[0] for r in conn.execute("SELECT DISTINCT job_type FROM listings").fetchall()]
    sources = [r[0] for r in conn.execute("SELECT DISTINCT source_site FROM listings").fetchall()]
    pay_bounds = conn.execute(
        "SELECT MIN(pay_min), MAX(pay_max) FROM listings WHERE pay_period = 'hour'"
    ).fetchone()
    conn.close()
    return {
        "job_types": job_types,
        "sources": sources,
        "hourly_pay_min": pay_bounds[0],
        "hourly_pay_max": pay_bounds[1],
    }


# ---------------------------------------------------------------------------
# Feature 1: Visa / work-hour guardrail
# ---------------------------------------------------------------------------

class VisaCheckRequest(BaseModel):
    weekly_hour_cap: float           # e.g. 20 for a typical student visa term-time cap
    committed_hours_elsewhere: float = 0  # hours/week already worked in other jobs
    candidate_listing_ids: List[str]
    assumed_hours_per_role: float = 15  # if a listing doesn't state hours, assume this many


@app.post("/api/visa-check")
def visa_check(req: VisaCheckRequest):
    """
    For each candidate listing, estimate whether taking it (on top of
    hours already committed elsewhere) would breach the student's
    weekly cap, and flags internships/full-time roles that are
    unlikely to fit a term-time cap at all.
    """
    conn = get_conn()
    placeholders = ",".join("?" for _ in req.candidate_listing_ids)
    rows = conn.execute(
        f"SELECT * FROM listings WHERE listing_id IN ({placeholders})",
        req.candidate_listing_ids,
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        job = dict(row)
        est_hours = req.assumed_hours_per_role
        if job["job_type"] == "full-time":
            est_hours = 40
        elif job["job_type"] == "internship":
            est_hours = 40  # most internships are full-time in practice

        projected_total = req.committed_hours_elsewhere + est_hours
        over_cap = projected_total > req.weekly_hour_cap

        results.append({
            "listing_id": job["listing_id"],
            "title": job["title"],
            "job_type": job["job_type"],
            "estimated_weekly_hours": est_hours,
            "projected_total_hours": projected_total,
            "weekly_hour_cap": req.weekly_hour_cap,
            "over_cap": over_cap,
            "visa_friendly_hint": bool(job["visa_friendly_hint"]) if job["visa_friendly_hint"] is not None else None,
            "guidance": _visa_guidance(job, over_cap),
        })

    return {"results": results}


def _visa_guidance(job: dict, over_cap: bool) -> str:
    if job["job_type"] in ("full-time", "internship"):
        return (
            "Full-time/internship roles during term usually only count toward your visa "
            "cap if they're vacation-period or officially co-op/CPT/placement work — check "
            "with your university's international office before accepting."
        )
    if over_cap:
        return "Taking this role would likely put you over your stated weekly hour cap."
    if job.get("visa_friendly_hint"):
        return "On-campus or university-affiliated - generally safest for visa work-hour rules."
    return "Fits your stated hour cap, but confirm your total hours across all jobs with your DSO/advisor."


# ---------------------------------------------------------------------------
# Feature 2: Commute / campus proximity matching
# ---------------------------------------------------------------------------

# Small static geocode table standing in for a real geocoding API call
# (no external network access in this environment). In production this
# would call a geocoding service once per unique location string and
# cache the result.
KNOWN_COORDS = {
    "main campus, riverdale": (40.700, -74.010),
    "tech building, riverdale": (40.702, -74.008),
    "science hall, riverdale": (40.699, -74.012),
    "north campus, riverdale": (40.706, -74.015),
    "bean&leaf - downtown riverdale": (40.712, -74.006),
    "bean&leaf - university ave": (40.701, -74.009),
    "bean&leaf - riverdale mall": (40.690, -73.995),
    "bean&leaf merch - downtown riverdale": (40.712, -74.006),
    "riverdale central": (40.710, -74.002),
    "industrial park, riverdale": (40.685, -74.030),
    "westside, riverdale": (40.708, -74.025),
    "downtown riverdale": (40.712, -74.006),
    "remote / riverdale office": (40.700, -74.010),
    "various - riverdale": None,
}

WALK_SPEED_KMH = 4.8
TRANSIT_SPEED_KMH = 22.0


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


class CommuteRequest(BaseModel):
    student_lat: float
    student_lng: float
    listing_ids: List[str]


@app.post("/api/commute")
def commute(req: CommuteRequest):
    """
    Computes straight-line distance and rough walk/transit time between
    the student's address and each listing's location. Listings whose
    location string isn't in the geocode table return null distance
    rather than a fabricated number.
    """
    conn = get_conn()
    placeholders = ",".join("?" for _ in req.listing_ids)
    rows = conn.execute(
        f"SELECT listing_id, title, location FROM listings WHERE listing_id IN ({placeholders})",
        req.listing_ids,
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        job = dict(row)
        coords = KNOWN_COORDS.get(job["location"].strip().lower())
        if not coords:
            results.append({
                "listing_id": job["listing_id"],
                "title": job["title"],
                "location": job["location"],
                "distance_km": None,
                "walk_minutes": None,
                "transit_minutes": None,
                "note": "Location could not be matched to a known coordinate.",
            })
            continue

        dist_km = round(haversine_km(req.student_lat, req.student_lng, *coords), 2)
        results.append({
            "listing_id": job["listing_id"],
            "title": job["title"],
            "location": job["location"],
            "distance_km": dist_km,
            "walk_minutes": round(dist_km / WALK_SPEED_KMH * 60),
            "transit_minutes": round(dist_km / TRANSIT_SPEED_KMH * 60) + 5,  # +5 min avg wait/transfer
            "note": None,
        })

    results.sort(key=lambda r: (r["distance_km"] is None, r["distance_km"]))
    return {"results": results}


@app.get("/")
def root():
    return {"status": "ok", "service": "GradGuide Job Finder API"}
