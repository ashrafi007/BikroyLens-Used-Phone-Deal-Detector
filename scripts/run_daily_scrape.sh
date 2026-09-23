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
DIAG_LOG="/Users/home/bikroylens-local-scrape/tick_diagnostic.log"

# Diagnostic: log every single tick's computed DATE/HOUR unconditionally,
# BEFORE the daytime check below — the daytime check exits before any of
# the normal $LOG writes happen, so a silent early-exit and a genuine
# problem look identical from the outside. This file makes every tick
# observable regardless of which path it takes.
echo "$(date '+%Y-%m-%d %H:%M:%S %Z'): DATE=$DATE HOUR=$(date +%H) TZ_env=${TZ:-unset}" >> "$DIAG_LOG"

# Daytime-only window (08:00-23:00 local) — overnight hours repeatedly hit
# deep "Standby" sleep (especially on battery) that no amount of caffeinate
# tuning fully prevented, silently missing ticks with no chance to catch up
# until someone opened the lid. Restricting to hours the Mac is naturally
# in use avoids fighting that battle at all; the skip-if-already-done
# guard below still means it just needs to catch one tick during the day.
HOUR=$(date +%H)
if [ "$HOUR" -lt 8 ] || [ "$HOUR" -ge 23 ]; then
  exit 0
fi

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
  fi
fi

# Push separately from committing, and on every tick (not just the one that
# scraped) -- this repo is also pushed to directly by interactive dev work,
# so a race is expected, not exceptional. A failed push here must NOT be
# fatal (this ran inside `set -e` unguarded before, which silently skipped
# load/normalize/retrain for the rest of the tick whenever it lost the
# race) and must be retried rather than stranding the commit forever.
if [ -n "$(git log origin/main..HEAD 2>/dev/null)" ]; then
  if ! git push >> "$LOG" 2>&1; then
    echo "$(date): push rejected (probably raced another push to main), retrying after rebase" >> "$LOG"
    if git pull --rebase origin main >> "$LOG" 2>&1 && git push >> "$LOG" 2>&1; then
      echo "$(date): push retry succeeded" >> "$LOG"
    else
      echo "$(date): push retry failed, will retry again next tick" >> "$LOG"
    fi
  fi
fi

if [ -f "data/bikroy_${DATE}.csv" ]; then
  python3 db/load_listings.py "data/bikroy_${DATE}.csv" >> "$LOG" 2>&1
  python3 nlp/populate_normalized.py >> "$LOG" 2>&1
fi

# Retrain the fair-price model once per day, gated on whether today's date
# already has a row in Postgres' model_training_history -- not on the
# scrape-skip check above, since load/normalize (and thus fresh normalized
# rows) can complete on a later tick than the scrape itself. Idempotent by
# design: safe to re-check every tick, only actually retrains once a day.
# (This used to grep a local accuracy_history.csv for today's date, but
# train_model.py now logs history to Postgres instead -- see its module
# docstring -- so the gate has to check there too, or this would retrain
# on every single tick instead of once.)
ALREADY_TRAINED_TODAY=$(python3 -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
with conn.cursor() as cur:
    cur.execute(\"SELECT COUNT(*) FROM model_training_history WHERE trained_at::date = CURRENT_DATE\")
    print(cur.fetchone()[0])
conn.close()
" 2>>"$LOG")

if [ -f "data/bikroy_${DATE}.csv" ] && [ "${ALREADY_TRAINED_TODAY:-0}" -eq 0 ] 2>/dev/null; then
  python3 ml/train_model.py >> "$LOG" 2>&1
fi
