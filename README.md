# BikroyLens

**A fair-price detector for used phones on Bikroy.com** — scrapes listings daily, uses a machine learning model to estimate what each phone should actually cost, and flags real deals instead of making you guess.

🔗 **Live site:** [frontend-ashrafi221b-3805.vercel.app](https://frontend-ashrafi221b-3805.vercel.app)
🔗 **API:** [bikroylens-used-phone-deal-detector.onrender.com](https://bikroylens-used-phone-deal-detector.onrender.com) ([docs](https://bikroylens-used-phone-deal-detector.onrender.com/docs))

---

## What it does

Bikroy.com (a major Bangladeshi marketplace) has no fair-price signal — every used-phone listing is just an asking price with no way to tell if it's a good deal or a rip-off. BikroyLens fixes that:

1. **Scrapes** used-phone listings daily across Dhaka, Chattogram, and Rajshahi (Apple, Samsung, Xiaomi, OnePlus, Nothing Phone)
2. **Normalizes** messy real-world titles ("Xiaomi Redmi Turbo 4 12+256 Jojobd, Ctg. (Brand New)") into structured brand/model/storage/condition fields
3. **Trains an XGBoost model** on the scraped data to predict what each phone should fairly cost, using out-of-fold cross-validation so the predictions are honest — not the model grading its own homework
4. **Classifies every listing** — Steal / Great Deal / Good Deal / Above Market — based on where the asking price actually falls relative to the model's fair-price range
5. **Serves it all live** through a searchable, filterable web app that updates automatically every day

## Features

- 🔍 **Search & filter** by brand, city, condition, and price range
- 🔥 **Best Deals** — top-scoring listings across the whole market
- 🆕 **Today's Update** — every phone scraped today, every deal category visible side by side
- 📊 **Insights** — price trends over time, breakdowns by city and condition
- 📱 **Listing detail pages** — asking price vs. fair-price range, with the exact percentage over/under explained
- ⚠️ **Suspicious listing flags** — catches "box open" listings priced suspiciously high for their tier
- 🔄 **Fully automated daily pipeline** — scrape → load → normalize → retrain, no manual steps

## Tech stack

| Layer | Tech |
|---|---|
| Scraping | Python, Scrapy |
| Database | PostgreSQL (Supabase) |
| Data normalization | Rule-based NLP (regex + lookup tables) |
| ML | XGBoost, scikit-learn (5-fold cross-validated out-of-fold predictions) |
| Backend API | FastAPI, psycopg2 |
| Frontend | React 19, TypeScript, Vite, TanStack Table, Recharts |
| Deployment | Vercel (frontend), Render (API) |
| Automation | macOS `launchd` — daily scrape/load/normalize/retrain cycle |

## Architecture

```
Bikroy.com
    │
    ▼
Scrapy spider ──► CSV ──► Postgres (listings)
                              │
                              ▼
                    NLP normalizer (regex-based)
                              │
                              ▼
                    Postgres (phones_normalized)
                              │
                              ▼
              XGBoost model (5-fold cross-validated)
                              │
                              ▼
              predicted_price / deal_score written back
                              │
                              ▼
                    FastAPI ──► React frontend
```

The entire cycle — scrape, load, normalize, retrain — runs once a day, fully automated, and writes straight into the same database the live site reads from. New data appears on the homepage with zero manual deployment.

## Project structure

```
bikroy_scraper/    Scrapy spider + pipeline
db/                 Postgres schema + CSV loader
nlp/                Title normalizer + populate script
ml/                 XGBoost training script + notebook
api/                FastAPI backend
frontend/           React + TypeScript app
scripts/            Daily automation entrypoint
```

## Running it locally

**Backend:**
```bash
cp .env.example .env   # add your DATABASE_URL (Supabase or any Postgres instance)
cd api
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Full pipeline** (scrape → load → normalize → retrain) needs a Python environment with the scraper/ML dependencies — see `scripts/run_daily_scrape.sh` for the exact sequence.

## Notes

This is an independent portfolio project — not affiliated with Bikroy.com in any way. Scraping respects `robots.txt` and uses conservative rate limiting (AutoThrottle).
