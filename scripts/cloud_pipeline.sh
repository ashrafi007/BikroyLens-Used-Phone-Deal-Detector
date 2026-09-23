#!/bin/bash
# Cloud entrypoint for the daily scrape -> load -> normalize -> retrain
# cycle, run as a Render Cron Job instead of the Mac's launchd timer.
#
# Deliberately simpler than run_daily_scrape.sh: that script's 30-min-tick
# + daytime-window + skip-if-already-done pattern exists specifically to
# work around a laptop that sleeps and misses ticks unpredictably. A cloud
# cron job doesn't have that problem -- Render runs it once, reliably, at
# whatever time the cron schedule says, so this just does the whole cycle
# start to finish in one go, no gating needed.
#
# No git commit/push here either: the ephemeral container's checkout isn't
# meant to accumulate history the way the Mac's persistent clone does --
# Postgres (listings, phones_normalized, model_training_history) is the
# single source of truth this pipeline writes to, which is what the live
# site actually reads from.

set -e
DATE=$(date -u +%F)

echo "=== BikroyLens cloud pipeline: ${DATE} ==="

echo "--- scraping ---"
cd bikroy_scraper
scrapy crawl bikroy -O "../data/bikroy_${DATE}.csv" -L INFO
cd ..

echo "--- loading into Postgres ---"
python3 db/load_listings.py "data/bikroy_${DATE}.csv"

echo "--- normalizing ---"
python3 nlp/populate_normalized.py

echo "--- retraining ---"
python3 ml/train_model.py

echo "=== done ==="
