#!/usr/bin/env python3
"""
Runs the NLP normalizer over every row in `listings` and populates
`phones_normalized` — brand/model/storage/ram/condition_clean via
nlp.normalizer, plus price_tier and is_suspicious computed here.

Safe to re-run any time: relies on phones_normalized's
unique(listing_id) constraint (ON CONFLICT DO NOTHING), so listings
already normalized are silently skipped, not duplicated or reprocessed.
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nlp.normalizer import parse_listing

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set (check your .env file)")
    sys.exit(1)


def price_tier(price):
    """Bucketed from the listing's actual price — NOT from which
    scrape-bracket URL caught it. Sub-20k prices (a buffer from loose
    scrape brackets, see links.md) fall into the lowest tier rather than
    a separate bucket or being dropped."""
    if price is None:
        return None
    if price < 50000:
        return "20-50k"
    if price < 110000:
        return "50k-1.1L"
    return "1.1L+"


def get_suspicious_thresholds(cur):
    """80th percentile price within each tier, computed from current
    data — not a fixed ৳ cutoff. Recomputed fresh every run, so it
    naturally shifts as more data accumulates."""
    thresholds = {}
    tier_ranges = {
        "20-50k": (0, 50000),
        "50k-1.1L": (50000, 110000),
        "1.1L+": (110000, None),
    }
    for tier, (lo, hi) in tier_ranges.items():
        if hi is None:
            cur.execute(
                "SELECT percentile_cont(0.8) WITHIN GROUP (ORDER BY price) "
                "FROM listings WHERE price >= %s",
                (lo,),
            )
        else:
            cur.execute(
                "SELECT percentile_cont(0.8) WITHIN GROUP (ORDER BY price) "
                "FROM listings WHERE price >= %s AND price < %s",
                (lo, hi),
            )
        thresholds[tier] = cur.fetchone()[0]
    return thresholds


INSERT_SQL = """
    INSERT INTO phones_normalized
        (listing_id, brand, model, storage, ram, condition_clean,
         price_tier, is_suspicious)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (listing_id) DO NOTHING
"""


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            thresholds = get_suspicious_thresholds(cur)
            print("is_suspicious thresholds (80th percentile per tier):", thresholds)

            # Only rows not yet normalized — not a full-table rescan every
            # run. With ~2,300 rows already normalized and only ~77-80
            # genuinely new listings/day, scanning everything each run held
            # one connection open long enough to hit a server-side timeout
            # (psycopg2.OperationalError: server closed the connection
            # unexpectedly) once the table grew past a few thousand rows.
            cur.execute(
                """
                SELECT l.id, l.raw_title, l.price, l.condition_raw
                FROM listings l
                LEFT JOIN phones_normalized n ON n.listing_id = l.id
                WHERE n.id IS NULL
                """
            )
            rows = cur.fetchall()

            inserted = 0
            skipped_dupe = 0
            for listing_id, raw_title, price, condition_raw in rows:
                parsed = parse_listing(raw_title, condition_raw)
                tier = price_tier(price)

                threshold = thresholds.get(tier)
                is_suspicious = bool(
                    "box open" in (raw_title or "").lower()
                    and price is not None
                    and threshold is not None
                    and price >= threshold
                )

                cur.execute(
                    INSERT_SQL,
                    (
                        listing_id,
                        parsed["brand"],
                        parsed["model"],
                        parsed["storage"],
                        parsed["ram"],
                        parsed["condition_clean"],
                        tier,
                        is_suspicious,
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    skipped_dupe += 1

                # Commit periodically, not just once at the very end — if
                # the connection drops mid-run, this loses at most a
                # partial batch instead of the whole thing.
                if inserted % 50 == 0:
                    conn.commit()

        conn.commit()
        print(f"{inserted} inserted, {skipped_dupe} already normalized")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
