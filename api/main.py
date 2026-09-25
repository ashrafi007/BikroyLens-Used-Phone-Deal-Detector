"""
BikroyLens API — FastAPI backend serving search, listings, insights, and
deal-score data straight from Postgres. No model file needed here — the
daily retrain (ml/train_model.py) already writes predicted_price/
fair_price_min/fair_price_max/deal_score onto phones_normalized, so this
API is a thin, fast read layer over data that's already computed.
"""

import os
from datetime import date
from typing import Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg2 import pool
from pydantic import BaseModel

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set (check your .env file)")

# A small pool, not one connection per request — this API will see bursts
# of concurrent requests from the frontend (a search page firing several
# fetches at once), and opening a fresh Postgres connection per request is
# slow enough to be noticeable.
db_pool = psycopg2.pool.SimpleConnectionPool(1, 10, DATABASE_URL)

# The project's actual scope (see PROJECT_CONTEXT.md) — Bikroy's own
# location text occasionally bleeds through to nearby districts outside
# these 3 (a handful of stray Khulna/Kushtia/Pabna/etc. rows), which
# clutters a city breakdown chart without being a real part of the
# dataset's intended coverage. City-grouped queries filter to just these.
TARGET_CITIES = ["Dhaka", "Chattogram", "Rajshahi"]

app = FastAPI(title="BikroyLens API")

# Wide open for now — this is a portfolio/demo project, not a
# multi-tenant product with real user data to protect. Tighten to the
# actual deployed frontend origin once that's live.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    return db_pool.getconn()


def put_conn(conn):
    db_pool.putconn(conn)


# ---------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------


class Listing(BaseModel):
    id: int
    url: str
    raw_title: str
    price: float
    condition_raw: Optional[str] = None
    condition_clean: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    posted_date: Optional[str] = None
    photo_count: Optional[int] = None
    seller_type: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    storage: Optional[str] = None
    price_tier: Optional[str] = None
    is_suspicious: bool = False
    predicted_price: Optional[float] = None
    fair_price_min: Optional[float] = None
    fair_price_max: Optional[float] = None
    deal_score: Optional[float] = None


class SearchResponse(BaseModel):
    total: int
    fair_price_min: Optional[float] = None
    fair_price_max: Optional[float] = None
    median_price: Optional[float] = None
    listings: list[Listing]


class StatsResponse(BaseModel):
    total_unique_listings: int
    total_scrape_days: int
    last_scraped: Optional[date] = None
    brands: list[dict]
    cities: list[dict]
    avg_deal_score: Optional[float] = None


class TodayResponse(BaseModel):
    scrape_date: Optional[date] = None
    total: int
    listings: list[Listing]


class InsightsResponse(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    total_listings: int
    avg_price: Optional[float] = None
    median_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    by_city: list[dict]
    by_condition: list[dict]
    price_trend: list[dict]
    best_deals: list[Listing]


# ---------------------------------------------------------------------
# Shared: the "current listings" view — latest sighting of each url,
# joined with its normalized fields and prediction. Every endpoint below
# builds on this same base query.
# ---------------------------------------------------------------------

BASE_QUERY = """
    SELECT DISTINCT ON (l.url)
        l.id, l.url, l.raw_title, l.price, l.condition_raw, l.location,
        l.posted_date, l.photo_count, l.seller_type,
        n.brand, n.model, n.storage, n.condition_clean, n.price_tier,
        n.is_suspicious, n.predicted_price, n.fair_price_min,
        n.fair_price_max, n.deal_score
    FROM listings l
    JOIN phones_normalized n ON n.listing_id = l.id
"""


# Today's scrape, unfiltered by deal_score — every listing from the most
# recent scrape day, whatever category its score lands in. This is
# deliberately different from BASE_QUERY: that one dedupes to the latest
# sighting of each url across ALL history, which is what "current
# listings" means everywhere else. Here we want exactly one day's batch,
# and the unique(url, scraped_date) constraint already guarantees at most
# one row per url for that day, so no DISTINCT ON is needed.
TODAY_QUERY = """
    SELECT l.id, l.url, l.raw_title, l.price, l.condition_raw, l.location,
        l.posted_date, l.photo_count, l.seller_type,
        n.brand, n.model, n.storage, n.condition_clean, n.price_tier,
        n.is_suspicious, n.predicted_price, n.fair_price_min,
        n.fair_price_max, n.deal_score
    FROM listings l
    JOIN phones_normalized n ON n.listing_id = l.id
    WHERE l.scraped_date = %s
"""


def row_to_listing(row):
    d = dict(row)
    d["city"] = (d.get("location") or "").split(",")[0].strip() or None
    d["is_suspicious"] = bool(d.get("is_suspicious"))
    return Listing(**d)


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------


@app.get("/")
def root():
    return {
        "service": "BikroyLens API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats", response_model=StatsResponse)
def stats():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC) t")
            total = cur.fetchone()["n"]

            cur.execute("SELECT COUNT(DISTINCT scraped_date) AS n, MAX(scraped_date) AS last FROM listings")
            row = cur.fetchone()
            total_days, last_scraped = row["n"], row["last"]

            cur.execute(
                f"""
                SELECT brand, COUNT(*) as count FROM ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC) t
                WHERE brand IS NOT NULL GROUP BY brand ORDER BY count DESC
                """
            )
            brands = [dict(r) for r in cur.fetchall()]

            cur.execute(
                f"""
                SELECT split_part(location, ',', 1) as city, COUNT(*) as count
                FROM ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC) t
                WHERE split_part(location, ',', 1) = ANY(%s)
                GROUP BY city ORDER BY count DESC
                """,
                (TARGET_CITIES,),
            )
            cities = [dict(r) for r in cur.fetchall()]

            cur.execute(
                f"""
                SELECT AVG(deal_score) as avg FROM ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC) t
                WHERE deal_score IS NOT NULL
                """
            )
            avg_deal_score = cur.fetchone()["avg"]

        return StatsResponse(
            total_unique_listings=total,
            total_scrape_days=total_days,
            last_scraped=last_scraped,
            brands=brands,
            cities=cities,
            avg_deal_score=round(avg_deal_score, 1) if avg_deal_score is not None else None,
        )
    finally:
        put_conn(conn)


@app.get("/api/today", response_model=TodayResponse)
def today(limit: int = Query(24, le=100)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT MAX(scraped_date) AS d FROM listings")
            scrape_date = cur.fetchone()["d"]
            if scrape_date is None:
                return TodayResponse(scrape_date=None, total=0, listings=[])

            cur.execute(f"SELECT COUNT(*) AS n FROM ({TODAY_QUERY}) t", (scrape_date,))
            total = cur.fetchone()["n"]

            cur.execute(f"{TODAY_QUERY} ORDER BY l.scraped_at DESC LIMIT %s", (scrape_date, limit))
            rows = cur.fetchall()

        return TodayResponse(scrape_date=scrape_date, total=total, listings=[row_to_listing(r) for r in rows])
    finally:
        put_conn(conn)


@app.get("/api/search", response_model=SearchResponse)
def search(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    city: Optional[str] = None,
    condition: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort: str = Query("deal_score", pattern="^(deal_score|price|newest)$"),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    conn = get_conn()
    try:
        where = []
        params = []
        if brand:
            where.append("brand ILIKE %s")
            params.append(brand)
        if model:
            where.append("model ILIKE %s")
            params.append(f"%{model}%")
        if city:
            where.append("location ILIKE %s")
            params.append(f"{city}%")
        if condition:
            where.append("condition_clean = %s")
            params.append(condition)
        if min_price is not None:
            where.append("price >= %s")
            params.append(min_price)
        if max_price is not None:
            where.append("price <= %s")
            params.append(max_price)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        order_sql = {
            "deal_score": "deal_score DESC NULLS LAST",
            "price": "price ASC",
            "newest": "posted_date DESC NULLS LAST",
        }[sort]

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                WITH current AS ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC)
                SELECT COUNT(*) AS n, MIN(fair_price_min) AS fpmin, MAX(fair_price_max) AS fpmax,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median
                FROM current {where_sql}
                """,
                params,
            )
            agg = cur.fetchone()

            cur.execute(
                f"""
                WITH current AS ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC)
                SELECT * FROM current {where_sql}
                ORDER BY {order_sql}
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = cur.fetchall()

        return SearchResponse(
            total=agg["n"],
            fair_price_min=agg["fpmin"],
            fair_price_max=agg["fpmax"],
            median_price=agg["median"],
            listings=[row_to_listing(r) for r in rows],
        )
    finally:
        put_conn(conn)


@app.get("/api/listings/{listing_id}", response_model=Listing)
def get_listing(listing_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"{BASE_QUERY} WHERE l.id = %s", (listing_id,))
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")
        return row_to_listing(row)
    finally:
        put_conn(conn)


@app.get("/api/deals", response_model=list[Listing])
def deals(limit: int = Query(20, le=100)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                WITH current AS ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC)
                SELECT * FROM current
                WHERE deal_score IS NOT NULL AND is_suspicious = FALSE
                ORDER BY deal_score DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [row_to_listing(r) for r in rows]
    finally:
        put_conn(conn)


@app.get("/api/insights", response_model=InsightsResponse)
def insights(brand: Optional[str] = None, model: Optional[str] = None):
    if not brand and not model:
        raise HTTPException(status_code=400, detail="Provide at least brand or model")

    conn = get_conn()
    try:
        where = []
        params = []
        if brand:
            where.append("brand ILIKE %s")
            params.append(brand)
        if model:
            where.append("model ILIKE %s")
            params.append(f"%{model}%")
        where_sql = f"WHERE {' AND '.join(where)}"

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                WITH current AS ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC)
                SELECT COUNT(*) AS n, AVG(price) AS avg_price,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median_price,
                       MIN(price) AS min_price, MAX(price) AS max_price
                FROM current {where_sql}
                """,
                params,
            )
            agg = cur.fetchone()

            cur.execute(
                f"""
                WITH current AS ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC)
                SELECT split_part(location, ',', 1) AS city, COUNT(*) AS count, AVG(price) AS avg_price
                FROM current {where_sql} AND split_part(location, ',', 1) = ANY(%s)
                GROUP BY city ORDER BY count DESC
                """,
                params + [TARGET_CITIES],
            )
            by_city = [dict(r) for r in cur.fetchall()]

            cur.execute(
                f"""
                WITH current AS ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC)
                SELECT condition_clean, COUNT(*) AS count, AVG(price) AS avg_price
                FROM current {where_sql}
                GROUP BY condition_clean ORDER BY count DESC
                """,
                params,
            )
            by_condition = [dict(r) for r in cur.fetchall()]

            # Price trend: raw listings (not deduped) grouped by scrape day —
            # this is the one place the append-only history is used directly,
            # since a real trend needs every day's snapshot, not just "latest".
            trend_where = where_sql.replace("brand", "n.brand").replace("model", "n.model")
            cur.execute(
                f"""
                SELECT l.scraped_date AS day, AVG(l.price) AS avg_price, COUNT(*) AS count
                FROM listings l JOIN phones_normalized n ON n.listing_id = l.id
                {trend_where}
                GROUP BY l.scraped_date ORDER BY l.scraped_date
                """,
                params,
            )
            price_trend = [dict(r) for r in cur.fetchall()]

            cur.execute(
                f"""
                WITH current AS ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC)
                SELECT * FROM current {where_sql} AND deal_score IS NOT NULL
                ORDER BY deal_score DESC LIMIT 5
                """
                if where
                else f"""
                WITH current AS ({BASE_QUERY} ORDER BY l.url, l.scraped_date DESC)
                SELECT * FROM current WHERE deal_score IS NOT NULL
                ORDER BY deal_score DESC LIMIT 5
                """,
                params,
            )
            best_deals = [row_to_listing(r) for r in cur.fetchall()]

        return InsightsResponse(
            brand=brand,
            model=model,
            total_listings=agg["n"],
            avg_price=round(agg["avg_price"], 0) if agg["avg_price"] else None,
            median_price=agg["median_price"],
            min_price=agg["min_price"],
            max_price=agg["max_price"],
            by_city=by_city,
            by_condition=by_condition,
            price_trend=price_trend,
            best_deals=best_deals,
        )
    finally:
        put_conn(conn)
