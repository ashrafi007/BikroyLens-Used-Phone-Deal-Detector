-- BikroyLens database schema — Week 2
-- Run this whole file once in the Supabase SQL Editor (Dashboard → SQL Editor → New query).

-- ============================================================
-- listings: raw scraped data, append-only, one row per listing
-- per scrape day. Never UPDATEd — the loader only INSERTs.
-- ============================================================
CREATE TABLE IF NOT EXISTS listings (
    id            SERIAL PRIMARY KEY,
    raw_title     TEXT NOT NULL,
    price         NUMERIC,
    condition_raw TEXT,
    location      TEXT,
    posted_date   TEXT,
    url           TEXT NOT NULL,
    photo_count   INTEGER,
    scraped_at    TIMESTAMPTZ NOT NULL,
    seller_type   TEXT,

    -- Derived column, not a scraped field: the calendar date (UTC) portion
    -- of scraped_at. This exists purely so the constraint below can
    -- enforce "same url can't appear twice on the same scrape day" at the
    -- database level, instead of only trusting the loader's Python-side
    -- dedupe logic. The same url appearing on DIFFERENT days is expected
    -- and intentional (that's the price-history design) — this constraint
    -- only blocks same-url-same-day duplicates.
    scraped_date  DATE GENERATED ALWAYS AS ((scraped_at AT TIME ZONE 'UTC')::date) STORED,

    CONSTRAINT unique_url_per_day UNIQUE (url, scraped_date)
);

CREATE INDEX IF NOT EXISTS idx_listings_url ON listings (url);
CREATE INDEX IF NOT EXISTS idx_listings_scraped_at ON listings (scraped_at);

-- ============================================================
-- phones_normalized: cleaned/derived data, one row per listing
-- per scrape day, produced by the NLP normalizer from `listings`.
-- ============================================================
CREATE TABLE IF NOT EXISTS phones_normalized (
    id               SERIAL PRIMARY KEY,
    listing_id       INTEGER NOT NULL REFERENCES listings(id),
    brand            TEXT,
    model            TEXT,
    storage          TEXT,
    ram              TEXT,
    condition_clean  TEXT,   -- mint / good / fair / poor

    -- Bucketed from the listing's actual `price` at normalize time — NOT
    -- from which scrape-bracket URL caught it (brackets in links.md are
    -- approximate, since Bikroy has no exact price filter).
    price_tier       TEXT,   -- '20-50k' / '50k-1.1L' / '1.1L+'

    -- "box open" in title AND price in the top 20% of that listing's own
    -- price_tier (computed from current data, not a fixed ৳ cutoff).
    is_suspicious    BOOLEAN NOT NULL DEFAULT FALSE,

    -- One normalized row per raw listings row (including repeat scrapes of
    -- the same phone across days — each gets its own listings.id and thus
    -- its own normalized row). Lets the populate script use ON CONFLICT
    -- DO NOTHING to stay idempotent, same pattern as the loader.
    CONSTRAINT unique_listing_id UNIQUE (listing_id),

    -- Written by ml/train_model.py during the daily retrain, not by the
    -- normalizer. NULL until the first successful training run touches
    -- this row. Stored here (not just in the local model_results.csv)
    -- so the API — deployed separately from the scraping Mac — can serve
    -- predictions straight from Postgres without needing the model file.
    predicted_price  NUMERIC,
    fair_price_min   NUMERIC,
    fair_price_max   NUMERIC,
    deal_score       NUMERIC
);

CREATE INDEX IF NOT EXISTS idx_phones_brand_model ON phones_normalized (brand, model);
CREATE INDEX IF NOT EXISTS idx_phones_price_tier ON phones_normalized (price_tier);
CREATE INDEX IF NOT EXISTS idx_phones_listing_id ON phones_normalized (listing_id);
