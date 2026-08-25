# BikroyLens — Step-by-Step Implementation Plan

This file is the execution spec: what to build, in what order, and what each step depends on. See `PROJECT_CONTEXT.md` for the "why" and the full architecture/data model — this file is the "what to do, when."

---

## Dependencies

### Python (scraper, DB, NLP, EDA, ML, API)

```bash
python3 -m venv venv && source venv/bin/activate

pip install scrapy scrapy-playwright \
            pandas sqlalchemy psycopg2-binary python-dotenv \
            scikit-learn xgboost \
            jupyter matplotlib seaborn \
            fastapi uvicorn

playwright install chromium   # only needed if scrapy-playwright ends up required
```

| Package | Used for |
|---|---|
| `scrapy` | Core scraper |
| `scrapy-playwright` | JS-rendered pages fallback (only if plain Scrapy can't see listing data in raw HTML) |
| `pandas` | CSV merging, EDA, feature prep |
| `sqlalchemy` + `psycopg2-binary` | PostgreSQL connection/ORM |
| `python-dotenv` | Loading DB credentials/API keys from `.env` |
| `scikit-learn` | Train/test split, metrics, Random Forest |
| `xgboost` | ML model (primary candidate) |
| `jupyter`, `matplotlib`, `seaborn` | EDA notebook + plots |
| `fastapi`, `uvicorn` | Backend API |

### Node/React (frontend)

```bash
npm create vite@latest bikroy-lens-frontend -- --template react
cd bikroy-lens-frontend
npm install recharts @tanstack/react-table axios
```

Optional (only if Node/Express thin layer is used instead of calling FastAPI directly from React):

```bash
npm install express
```

### Infra / deployment (no local install needed)

- Docker + Docker Compose (for local dev — Postgres + API together)
- GitHub Actions (scraper scheduling — config lives in `.github/workflows/`)
- Accounts: Supabase (Postgres), Render (FastAPI), Vercel (React)

---

## Week 1 — Scraper

### Day 1–2: Explore + prototype
1. Open bikroy.com → Mobile Phones → pick one city (Dhaka) to start, ignore other cities/brands/price filters for now
2. Confirm via "View Page Source" whether the *first-load* listing data is in raw HTML (plain Scrapy works for the initial batch) or JS-rendered (need `scrapy-playwright`)
3. **Bikroy uses infinite scroll, not "next page" links — pagination needs its own check:**
   - Open DevTools → **Network tab** → filter `Fetch/XHR` → scroll down on the results page and watch for a request firing on scroll (often something like `...&page=2` or `...&offset=40`, returning JSON or an HTML fragment)
   - **If that request exists:** plain Scrapy can hit it directly in a loop, incrementing the page/offset param each time — no browser needed. This is the preferred path; check it before reaching for Playwright.
   - **If no such request exists** (scroll only mutates the DOM client-side with no discrete endpoint): fall back to `scrapy-playwright` and drive real scroll events — `page.evaluate("window.scrollTo(0, document.body.scrollHeight)")` in a loop, waiting briefly after each for new items, stopping after 2-3 consecutive scrolls with no new listings (or a safety cap) — then extract the fully-scrolled HTML.
4. `scrapy startproject bikroy_scraper`
5. Write one spider that hits that single Dhaka URL and prints title + price + url for ~20 listings to the terminal — no pagination loop yet, no CSV yet
6. **Done when:** 20 clean listings print correctly, and you know which of the two pagination paths above you'll need for Day 3-5

### Day 3–5: Full scraper
1. Add pagination using whichever path Day 1-2 identified — either loop the discovered API endpoint's page/offset param (plain Scrapy), or drive repeated scroll-and-wait cycles via `scrapy-playwright` until no new listings load
2. Extract all required fields: title, price, condition, location, posted_date, url, photo_count, seller_type
3. Add the brand filter (5 brands) and price filter (approximate ranges per brand/city, since Bikroy has no exact price filter — see `links.md`; target tiers are ৳20k–50k, ৳50k–1.1L, ৳1.1L+, but actual scrape bracket bounds fluctuate to fit real Bikroy query results) into the scrape URL/request params to reduce crawl size
4. Add a loop over all target cities (Dhaka, Chittagong, Rajshahi) — each city is a separate base URL, not a query param
5. Output to CSV via Scrapy's `-o` flag, one file per run, named with the date (e.g. `bikroy_2026-08-25.csv`)
6. Add a small delay between requests (AutoThrottle or manual delay) to avoid rate-limiting/blocking
7. **Done when:** a single run produces 400–1200+ listings across all target cities/brands in one CSV

### Day 6–7: Scheduling
1. Set up a GitHub Actions workflow (`.github/workflows/scrape.yml`) on a daily cron schedule
2. Each run: checkout repo → install deps → run `scrapy crawl bikroy -o data/bikroy_$(date +%F).csv` → commit/upload the new CSV
3. **Never overwrite** previous days' CSVs — each day's file is additive
4. **Done when:** two consecutive scheduled runs each produce their own dated CSV, and you can manually diff the URL sets between them (new/gone listings) as a sanity check

---

## Week 2 — Database + NLP Normalizer

1. Provision a PostgreSQL instance on Supabase
2. Create the `listings` and `phones_normalized` tables (see schema in `PROJECT_CONTEXT.md`)
3. Write a loader script: reads each day's CSV → **dedupes by `url` within that day first** (scrape brackets overlap per city/brand since Bikroy has no exact price filter, so the same listing can appear in two bracket CSVs on one day — keep one row) → bulk inserts into `listings` (append-only across days, never UPDATE existing rows)
4. Write the NLP normalizer: regex + brand/model lookup dictionary, parses `raw_title` → brand/model/ram/storage/condition_clean
5. Populate `phones_normalized` from `listings` using the normalizer, one row per listing per scrape day, **including `price_tier` bucketed from the actual `price` field** (20-50k / 50k-1.1L / 1.1L+ — not from which scrape bracket URL caught it)
6. Implement the `is_suspicious` flag: `"box open"` in title AND price above the 80th percentile of prices within that listing's `price_tier` (per-tier threshold, computed from current data — not a fixed ৳ cutoff, since tiers now start at 20k and the top tier is uncapped)
7. Handle missing data: drop rows with missing price (unusable for ML target); keep rows with missing condition/RAM/storage but leave those fields null; bucket missing location as "unspecified" rather than dropping
8. **Done when:** you can query `phones_normalized` and get clean brand/model/condition breakdowns for at least a few days of real data

---

## Week 3–4 — EDA + ML Model

### Week 3: EDA (Jupyter notebook)
1. Price distribution per model
2. Price by condition (mint/good/fair/poor)
3. Price by location (city/area comparison)
4. Price trend over time (median per week — will be thin at first, fills in as more days accumulate; does not require 30 days to start)
5. Listing age vs final price
6. Save each output as JSON for later use by the frontend/API

### Week 4: ML model
1. Feature engineering: brand, model, storage, ram, condition, location, photo_count, seller_type
2. Train XGBoost and/or Random Forest to predict `price`
3. Train/test split, log RMSE
4. Compute predicted fair price range (±10%) per listing
5. Compute deal_score = `100 - ((listing_price - predicted_price)/predicted_price*100)`, clipped 0–100
6. **Done when:** model produces sane fair-price predictions and deal scores on held-out test data

---

## Week 5–6 — FastAPI + React

### FastAPI
1. `GET /api/search?model=&location=` → fair_price_min/max, median, listings[]
2. `GET /api/listings?model=` → sorted by deal_score desc
3. `GET /api/insights?model=` → insight cards (best area, trend, warnings)

### React dashboard
1. Search bar wired to `/api/search`
2. Recharts: price distribution chart + trend chart
3. TanStack Table: listings table with deal_score column, sortable/filterable
4. Match the agreed mockup layout

### Node/Express — optional for v1
1. Thin layer: serve React build, proxy to FastAPI
2. Can be skipped entirely for the demo — call FastAPI directly from React

---

## Week 7 — Deployment

1. PostgreSQL → Supabase
2. FastAPI → Render (auto-deploys on push to GitHub)
3. React → Vercel
4. Scraper → already on GitHub Actions cron (from Week 1)
5. Write one `docker-compose.yml` for local dev (Postgres + FastAPI together)
6. **Done when:** the live URL works end-to-end — search a phone, see real results, ৳0 hosting cost

---

## Week 8 — Demo polish

1. Seed 30 days of fake-but-realistic historical data so trend charts look populated on day one of the demo
2. Record a 60-second Loom video: open the site, search Samsung A32, point at the ৳ price, show a steal listing
3. Write Fiverr gig copy
4. Publish

---

## Cross-cutting rules (apply throughout, not just one week)

- **CSV/data handling:** never overwrite a previous day's raw scrape file; merging is just concatenation keyed on `url`; repeat appearances of the same `url` **across days** are price-history, not duplicates — but repeat appearances of the same `url` **within the same day** (from overlapping price-bracket scrapes) ARE duplicates and must be deduped to one row at load time
- **Missing data:** drop only when price is missing; otherwise keep the row, leave the field null
- **Filters:** brand + price filters are applied at scrape time (fixed project scope); city is a separate crawl per city, not a query filter; NLP normalizer re-verifies brand from title text regardless of Bikroy's own brand tag; scrape-time price brackets are approximate (Bikroy has no exact price filter, so bracket bounds vary per brand/city — see `links.md`) and only reduce crawl size — the canonical `price_tier` is always computed downstream from the actual scraped `price`, never from the bracket URL used
