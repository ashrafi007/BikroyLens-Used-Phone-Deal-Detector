#!/usr/bin/env python3
"""
Loads scraped CSV files into the `listings` Postgres table.

Usage:
    python db/load_listings.py                            # loads every data/bikroy_*.csv
    python db/load_listings.py data/bikroy_2026-08-28.csv  # loads just one file

Safe to re-run any time on any file: relies on the schema's
unique(url, scraped_date) constraint (ON CONFLICT DO NOTHING), so rows
already loaded are silently skipped rather than duplicated. This is also
what makes it safe to call automatically every day from the local
scheduler without tracking "have I already loaded today's file" separately.
"""

import csv
import glob
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set (check your .env file)")
    sys.exit(1)

INSERT_SQL = """
    INSERT INTO listings
        (raw_title, price, condition_raw, location, posted_date, url,
         photo_count, scraped_at, seller_type)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (url, scraped_date) DO NOTHING
"""


def clean_row(row):
    """Convert CSV strings to proper types, per the missing-data rules in
    PROJECT_CONTEXT.md: drop a row only if price is missing/invalid
    (unusable as an ML target); otherwise keep it and leave fields null;
    bucket missing location as 'unspecified' rather than dropping."""
    price_raw = (row.get("price") or "").strip()
    try:
        price = float(price_raw)
    except ValueError:
        # Covers both genuinely missing prices and malformed/non-numeric
        # rows (e.g. a stray embedded header row read as data) — either
        # way, unusable as an ML target, so skip rather than crash.
        return None

    photo_count = (row.get("photo_count") or "").strip()

    return (
        (row.get("raw_title") or "").strip() or None,
        price,
        (row.get("condition_raw") or "").strip() or None,
        (row.get("location") or "").strip() or "unspecified",
        (row.get("posted_date") or "").strip() or None,
        (row.get("url") or "").strip(),
        int(photo_count) if photo_count.isdigit() else None,
        (row.get("scraped_at") or "").strip(),
        (row.get("seller_type") or "").strip() or None,
    )


def load_file(conn, path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    inserted = 0
    skipped_dupe = 0
    skipped_no_price = 0

    with conn.cursor() as cur:
        for row in rows:
            values = clean_row(row)
            if values is None:
                skipped_no_price += 1
                continue
            cur.execute(INSERT_SQL, values)
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped_dupe += 1
    conn.commit()

    print(
        f"{os.path.basename(path)}: {inserted} inserted, "
        f"{skipped_dupe} already existed, {skipped_no_price} skipped (no price)"
    )
    return inserted


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        files = sorted(glob.glob(os.path.join(data_dir, "bikroy_*.csv")))

    if not files:
        print("No CSV files found.")
        return

    conn = psycopg2.connect(DATABASE_URL)
    total_inserted = 0
    try:
        for path in files:
            total_inserted += load_file(conn, path)
    finally:
        conn.close()

    print(f"\nTotal newly inserted this run: {total_inserted}")


if __name__ == "__main__":
    main()
