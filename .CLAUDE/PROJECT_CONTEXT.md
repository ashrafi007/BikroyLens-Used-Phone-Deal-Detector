# BikroyLens — Fair Phone Price Finder

## What this project is

BikroyLens is a fair-price estimator and deal-score engine for used and new phones listed on Bikroy.com (Bangladesh's largest classifieds marketplace). It scrapes phone listings daily, learns what a "fair" price looks like for each phone model/condition/location combination using machine learning, and surfaces underpriced listings (good deals) and overpriced/suspicious listings (potential scams or misrepresented condition) to end users through a searchable web dashboard.

**Problem it solves:** Buyers browsing Bikroy have no way to know if ৳15,000 for a "Samsung A32, good condition" is a steal or a ripoff — pricing on the platform is entirely seller-set with no benchmark. BikroyLens builds that benchmark from real market data and shows a "deal score" (0–100) next to every listing.

**Business model:** Portfolio/freelance project — built to be pitched as a Fiverr gig / SaaS-style demo, or resold as a market-intelligence tool for phone resellers.

## Scope (as of project start, 2026-08-23)

- **Brands covered:** Samsung, Apple (iPhone), Xiaomi, OnePlus, Nothing Phone (5 brands only — not all brands on Bikroy; Honor and Oppo both dropped from original scope)
- **Price range:** tiered, no upper cap — ৳20,000–50,000 / ৳50,000–1,10,000 / ৳1,10,000+ (previously a single ≤৳20,000 budget-only range)
- **Locations:** Dhaka, Chittagong, Rajshahi only (narrowed from an original multi-city list)
- **Target volume:** ~1,000 listings/day across all cities/brands/tiers combined. This is a ceiling, not a fixed quota — actual daily count will vary depending on real inventory. With the 1.1L+ tier now in scope, premium brands (Apple, OnePlus, Nothing) should contribute meaningfully more rows than under the old ≤20k-only range.

## Team & ownership

Solo project — built entirely by Ash (me). All roles below (scraper, EDA/ML, backend, frontend) are owned by the same person; no teammates.

## Architecture / pipeline

```
Bikroy.com
   ↓ (Scrapy spider, daily via GitHub Actions cron)
Raw CSV (one file per day, e.g. bikroy_2026-08-23.csv) — never overwritten
   ↓ (bulk insert)
PostgreSQL `listings` table (raw scraped fields, append-only, one row per listing per scrape day)
   ↓ (NLP normalizer: regex + brand/model lookup dict)
PostgreSQL `phones_normalized` table (brand, model, RAM, storage, condition_clean, is_suspicious)
   ↓ (EDA in Jupyter → JSON outputs)
   ↓ (ML training: XGBoost/Random Forest)
Trained model → predicted fair price + deal score per listing
   ↓
FastAPI backend (serves search/listings/insights endpoints)
   ↓
React dashboard (search bar, price charts via Recharts, listings table via TanStack Table)
```

## Data model

```sql
listings
  id, raw_title, price, condition_raw,
  location, posted_date, url, photo_count,
  scraped_at, seller_type

phones_normalized
  listing_id, brand, model, storage, ram,
  condition_clean (mint/good/fair/poor),
  price_tier (20-50k / 50k-1.1L / 1.1L+),
  is_suspicious (bool)
```

- `listings` is append-only: every daily scrape adds new rows (one row per listing seen that day), even if the same listing (same `url`) was already seen on a previous day. This builds price/listing history over time — it is the project's core data moat.
- A listing is considered "new" if its `url` has never appeared before. A listing is considered "gone"/delisted if its `url` stops appearing in the most recent full scrape (only trustworthy if the scraper covers ALL pages, not a capped subset).
- `is_suspicious` is flagged when a listing's title mentions "box open" AND its price falls in the top 20% of prices within its own `price_tier` (20-50k / 50k-1.1L / 1.1L+) — computed as the 80th percentile of that tier's price distribution from current data, not a fixed ৳ cutoff (the old fixed >৳17,000 threshold assumed a single ≤20k range and no longer applies now that tiers start at 20k and the top tier is uncapped). Heuristic proxy for "claims premium condition but priced like it's used/damaged," scaled per tier.
- **`price_tier` is assigned downstream from the actual scraped `price`, not from which scrape-bracket URL caught the listing.** Bikroy has no exact price-filter support, so the `price_min`/`price_max` used in scrape URLs are approximate and vary per brand/city (see `links.md`) — they exist purely to reduce crawl size. The normalizer/loader buckets each listing into 20-50k / 50k-1.1L / 1.1L+ using its real `price` field against these fixed lines, independent of the loose scrape bracket.
- **Same-day dedupe by `url`:** because scrape brackets sometimes overlap (e.g. a tier-1 URL ending at ৳49,000 and a tier-2 URL starting at ৳49,000), the same listing can be returned by two bracket URLs on the same day. This is not price-history (which is *across* days) — the loader must dedupe to one row per `url` per scrape day before inserting into `listings`.

## NLP normalizer (rule-based, no ML)

Input example: `"Samsung A32 4/64 slimline good cond box open"`
Output: `brand=Samsung, model=Galaxy A32, ram=4GB, storage=64GB, condition=good`

Built with regex + a maintained brand/model lookup dictionary — deliberately no ML/LLM here, titles are short and formulaic enough for rules to work well and stay debuggable.

## ML model

- **Algorithm:** XGBoost or Random Forest (explicitly not deep learning — not enough data for that yet)
- **Features:** brand, model, storage, ram, condition, location, photo_count, seller_type
- **Target:** price
- **Output:** predicted fair price, with a fair price *range* of ±10% around the point prediction
- **Deal score formula:** `100 - ((listing_price - predicted_price) / predicted_price * 100)`, clipped to 0–100. Higher score = better deal (listing priced below predicted fair value).
- **Evaluation:** train/test split, RMSE logged.

## API surface (FastAPI)

```
GET /api/search?model=samsung-a32&location=dhaka
  → fair_price_min, fair_price_max, median, listings[]

GET /api/listings?model=samsung-a32
  → listings sorted by deal_score desc

GET /api/insights?model=samsung-a32
  → insight cards (best area, price trend, warnings)
```

## Frontend (React)

- Search bar → calls FastAPI → renders results
- Recharts: price distribution chart, 30-day price trend chart
- TanStack Table: sortable/filterable listings table with deal_score column
- Layout should match the team's agreed mockup (not yet attached in this repo — add when available)

## Deployment (target: ৳0/month)

| Component | Platform |
|---|---|
| PostgreSQL | Supabase (free tier) |
| FastAPI | Render (free tier) |
| React | Vercel (free tier) |
| Scraper scheduling | GitHub Actions (scheduled workflow, replaces APScheduler) |

Local dev via a single `docker-compose.yml`. Render auto-deploys on push to GitHub.

## Key decisions & rationale (for future reference)

- **Scrapy over requests+BeautifulSoup** for the production scraper: built-in pagination, retries, auto-throttling (politeness), and native CSV export. `scrapy-playwright` is the fallback only if Bikroy's listing pages turn out to require JS rendering (check via "View Page Source" — if title/price text isn't in raw HTML, JS rendering is in play).
- **GitHub Actions over APScheduler** for scheduling: no need to run a persistent process anywhere; GitHub's scheduler triggers the scrape, and this pairs naturally with the free-tier deployment plan.
- **No Bikroy filters used for city selection** (location is a separate URL per city, looped over in the spider) **but brand + price filters ARE applied at scrape time** now that the brand/price scope is fixed — this reduces pages crawled. The NLP normalizer still re-derives brand from the title text as a safety net, since sellers sometimes mis-tag brand on Bikroy.
- **Daily CSVs are never merged/overwritten at scrape time** — each day's run is its own dated file. Combining across days (for analysis or DB loading) happens downstream by concatenating on the `url` key, treating repeat appearances of the same `url` as price-history snapshots, not duplicates to remove.
- **30 real days of scraped data is NOT a prerequisite for building the ML model** — training starts in Week 3-4 on whatever real data has accumulated by then. Seeding 30 days of *fake* historical data (Week 8) is purely so demo trend charts look populated on day one of the pitch — it's a separate, cosmetic step.
