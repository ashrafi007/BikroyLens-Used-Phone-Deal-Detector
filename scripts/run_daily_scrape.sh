#!/bin/bash
# Runs the scraper locally on a timer, independent of GitHub Actions'
# self-hosted-runner dispatch entirely. That mechanism requires a live
# runner registration+connection at the exact cron tick, which proved too
# fragile (lid-close sleep, idle sleep, network blips all silently drop
# it, and GitHub does NOT queue/retry a missed scheduled tick for
# self-hosted runners). This script needs nothing but the Mac being on.
#
# Runs from its own clone outside ~/Documents — macOS blocks background
# launchd processes from writing inside ~/Documents without Full Disk
# Access, which this avoids entirely rather than requiring that grant.
#
# Week 2 addition: after scraping (or even if this tick found nothing new
# to scrape), always attempts to load today's CSV into Postgres. The
# loader is idempotent (ON CONFLICT DO NOTHING on unique(url,
# scraped_date)), so calling it every 30-min tick is harmless — it just
# means a transient DB failure on one tick gets retried automatically on
# the next, same resilience philosophy as the scrape-skip guard below.

set -e
REPO_DIR="/Users/home/bikroylens-local-scrape/repo"
DATE=$(date -u +%F)
LOG="/Users/home/bikroylens-local-scrape/scrape_${DATE}.log"

cd "$REPO_DIR"
git pull --rebase origin main >> "$LOG" 2>&1 || true

source venv/bin/activate

if [ -f "data/bikroy_${DATE}.csv" ]; then
  echo "$(date): already have data for ${DATE}, skipping scrape." >> "$LOG"
else
  cd bikroy_scraper
  scrapy crawl bikroy -O "../data/bikroy_${DATE}.csv" -L INFO >> "$LOG" 2>&1
  cd ..

  git add "data/bikroy_${DATE}.csv"
  if ! git diff --cached --quiet; then
    git commit -m "Daily scrape: ${DATE} (local scheduler)" >> "$LOG" 2>&1
    git push >> "$LOG" 2>&1
    echo "$(date): committed and pushed data for ${DATE}" >> "$LOG"
  fi
fi

if [ -f "data/bikroy_${DATE}.csv" ]; then
  python3 db/load_listings.py "data/bikroy_${DATE}.csv" >> "$LOG" 2>&1
fi
