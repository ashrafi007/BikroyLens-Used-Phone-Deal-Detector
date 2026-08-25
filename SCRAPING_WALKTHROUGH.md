# How the BikroyLens Scraper Got Built — A Walkthrough

This is a record of the actual investigation and build process for `bikroy_scraper/`,
written so you can follow the reasoning, not just the result. Every step below really
happened, in this order, including the bugs.

---

## 1. Check the site can even be reached

Before writing anything, confirm the sandbox/machine actually has internet access:

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" --max-time 15 "https://bikroy.com" \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
```

Got `HTTP 200`. Note the `-A` (user-agent) flag — some sites reject requests with no
user-agent or an obviously non-browser one.

**Lesson:** always sanity-check connectivity before building anything on top of it.

---

## 2. Is the data server-rendered, or does it need a real browser?

This is *the* question that decides your whole scraper architecture. Fetched a real
search-results URL from `links.md` with plain `curl` (no JS execution at all) and
grepped the raw response for content that should only be there if the server actually
rendered the listings into the HTML:

```bash
curl -s "https://bikroy.com/dhaka/search?query=apple+iphone&price_min=19000&price_max=49000" \
  -A "..." -o search.html
grep -o "BDT" search.html | wc -l      # → 30 matches
grep -o "iPhone" search.html | wc -l   # → 51 matches
```

Both showed up in plenty — meaning Bikroy renders listing cards **server-side**. This
was a big deal: it meant we could skip `scrapy-playwright` (headless browser) entirely
for the search results, which is much faster and far less fragile than driving a real
browser.

**Lesson:** "the page looks JS-heavy in the browser" doesn't mean the *data* is
JS-rendered. Always check the raw HTTP response before reaching for a headless browser.

---

## 3. Find the real selectors — and a lucky break

Extracted one full listing card's HTML to see the actual structure:

```python
idx = html.find('js-advert-list-item')
start = html.rfind('<div', 0, idx)
print(html[start:start+4000])
```

This turned up class names like `qa-advert-price`, `qa-advert-title`,
`qa-advert-list-item`. The `qa-` prefix is a strong hint: sites often add these
specifically for their own automated *QA/test* suites, which means they're written to
be **stable** — a much safer thing to build a scraper around than a random CSS class
that could change with the next design tweak.

On the detail page, found something even better: Bikroy uses
[schema.org microdata](https://schema.org/) (`itemprop="price"`, `itemprop="name"`,
`itemprop="itemCondition"`, `itemprop="description"`) — structured markup meant for
Google's crawler. That's effectively a semi-official API for scraping detail pages:

```html
<h1 itemprop="name" class="qa-advert-title b-advert-title">
  <div class="b-advert-title-inner qa-advert-title b-advert-title-inner--h1">
    Apple iPhone 12 Pro 256 GB
  </div>
</h1>
...
<span itemprop="price" content="41500">BDT 41,500</span>
...
<div class="b-advert-attribute__value" itemprop="itemCondition">Used</div>
```

Pulling `content="41500"` directly instead of parsing "BDT 41,500" as text avoids a
whole class of parsing bugs (commas, currency symbols, whitespace).

**Lesson:** before hand-picking CSS classes, check for `itemprop=` / schema.org
microdata — sites add it for SEO and it tends to be more stable than visual styling
classes.

---

## 4. Location + posted date needed one more layer of digging

The obvious approach — grab all text inside the info block — picked up a stray
"Promoted" label from a sibling element and mangled the data. Had to narrow the
selector to the specific inner div:

```html
<div class="b-advert-info-statistics b-advert-info-statistics--region">
  <svg>...</svg> Dhaka, Jamuna Future Park, 2 hours ago
</div>
```

Selector: `.b-advert-info-statistics--region::text` (grabs the direct text node after
the `<svg>`, not its descendants) → then split on commas: last piece is the date,
everything before it is the location.

**Lesson:** always fetch a *real* example and look at the actual nesting before
trusting a "grab everything in this container" selector — sibling/parent elements
sneak in unrelated text more often than you'd expect.

---

## 5. Pagination turned out to be messy — and that's OK

Testing `?page=1` vs `?page=2` vs `?page=3` on the same bracket URL (with a persistent
cookie session, like a real browser) showed *overlapping*, cumulative results rather
than clean, distinct pages (14 → 17 → 20 items, each page mostly repeating the previous
page's items plus a few new ones).

This could have been a blocker, but it wasn't — because the pipeline was **already**
designed to dedupe listings by `url` (originally to handle overlapping *price brackets*
in `links.md`). The same dedup logic just needed to also cover overlapping *pages*
within a bracket, which it does automatically since it dedupes on the final listing URL
regardless of which page or bracket it was discovered from.

**Lesson:** messy upstream behavior doesn't always need a special-case fix — sometimes
a robustness mechanism you already built for a different reason quietly absorbs it.

---

## 6. Check you're allowed to do this

```bash
curl -s "https://bikroy.com/robots.txt"
```

```
User-agent: *
Disallow: /test/*
Disallow: /admin/*
Disallow: /crm/*
Disallow: /auth/facebook*
```

`/search` and listing detail pages aren't in the disallow list for a general
user-agent — only Bingbot has extra restrictions on `?query=` params, which doesn't
apply to us. Confirmed compliant before writing a single line of spider code.

---

## 7. Build the actual Scrapy project

```bash
python3 -m venv venv && source venv/bin/activate
pip install scrapy pandas beautifulsoup4 lxml
scrapy startproject bikroy_scraper
```

**`items.py`** — mirrors the `listings` table schema from `PROJECT_CONTEXT.md` exactly,
so there's a straight line from "what the spider yields" to "what the DB table holds":

```python
class ListingItem(scrapy.Item):
    raw_title = scrapy.Field()
    price = scrapy.Field()
    condition_raw = scrapy.Field()
    location = scrapy.Field()
    posted_date = scrapy.Field()
    url = scrapy.Field()
    photo_count = scrapy.Field()
    scraped_at = scrapy.Field()
    seller_type = scrapy.Field()
    description = scrapy.Field()  # bonus field, not in original schema
```

**`spiders/bikroy.py`** — the core design decisions baked in:

- Reads `links.md` at run time with a regex (`r'"(https://bikroy\.com/[^"]+)"'`)
  instead of hardcoding URLs — `links.md` stays the single source of truth for what
  gets scraped.
- For each bracket URL, pages up to 4 times, but **stops early** the moment a page
  yields zero *new* listings (no point paging further once a bracket is exhausted).
- Keeps a spider-wide `self.followed_urls` set — dedupes at scrape time, not just at
  DB-load time, which also saves real request quota.
- Follows every card to its own detail page and scrapes the full field set from there
  (the "click every phone" design, chosen deliberately over scraping fields off the
  card directly — simpler code, one consistent source per field, traded off against
  more total requests).

**`settings.py`** — politeness settings:

```python
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ... Chrome/120.0 Safari/537.36"
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
```

`AutoThrottle` adapts the delay based on how fast the server is actually responding —
safer than a single fixed delay, since it backs off automatically if the site is
under load.

---

## 8. The bug: a smoke test that did *nothing*

Ran a tiny 5-item test before trusting the full 1000-item crawl:

```bash
scrapy crawl bikroy -s CLOSESPIDER_ITEMCOUNT=5 -o smoketest.csv -L INFO
```

Output: spider opened, then **immediately** closed. Zero pages crawled, zero items,
no error message anywhere.

Debugging process:
1. Checked the `links.md` file path resolution manually in isolation — worked fine,
   ruled that out.
2. Reran with `-L DEBUG` and grepped for `ERROR`/`Traceback` — nothing. The code
   wasn't crashing, it just wasn't running at all.
3. Inspected the installed Scrapy version's own source directly:
   ```python
   import scrapy, inspect
   print(scrapy.__version__)          # 2.18.0
   print(inspect.getsource(scrapy.Spider.start))
   ```
   This revealed that Scrapy 2.13+ replaced the old `def start_requests(self):`
   hook with a new `async def start(self):` method — and the old hook is **not**
   automatically called anymore. My spider had defined `start_requests()`
   (correct for older Scrapy tutorials/docs found online), which the engine now
   silently ignores entirely.

Fix: renamed the method to `async def start(self):`, kept the same body (plain
`yield` inside an `async def` is valid — no `await` required).

Reran the smoke test: 21 items scraped correctly, clean data in every field.

**Lesson:** "no error, but also nothing happens" in a framework usually means a
method name/signature the framework expects has silently changed between versions.
When in doubt, read the installed library's actual source rather than trusting
half-remembered API shapes.

---

## 9. Launch the real crawl, and a second small trap

Launched the full run in the background:

```bash
nohup scrapy crawl bikroy -o data/bikroy_2026-08-25.csv -L INFO > data/scrape_2026-08-25.log 2>&1 &
echo "Started with PID $!"
```

...run inside a tool call that was *also* backgrounded. That nesting caused a false
"completed" notification almost instantly — what actually finished was the outer
wrapper shell (which returns immediately after backgrounding the real process with
`nohup ... &`), not the scrape itself. Caught this by directly checking whether the
PID was still alive (`kill -0 <pid>`) and the log's timestamp — the real process was
still running, seconds in, exactly as expected.

Fix: set up a dedicated wait condition instead of trusting the first notification —
a background loop that polls whether the PID is still alive and only reports done
once it genuinely exits:

```bash
until ! kill -0 <pid> 2>/dev/null; do sleep 5; done
echo "SCRAPE_PROCESS_EXITED"
```

**Lesson:** backgrounding a command that *itself* backgrounds another process (`nohup
... &` inside an already-backgrounded call) detaches the real work from what's being
tracked. Watch the actual PID/log, not just the wrapper's exit status.

---

## Summary of decisions worth remembering

| Decision | Why |
|---|---|
| Plain Scrapy, no Playwright | Search + detail pages are server-rendered; confirmed via raw `curl`, not by "eyeballing" the browser |
| Scrape detail page per listing, not just the card | Simpler, uniform field extraction — traded against more total requests |
| Dedupe by `url` at scrape time, not just load time | Same mechanism absorbs both overlapping price brackets *and* overlapping pagination pages |
| `itemprop=` microdata over visual CSS classes where available | More stable — added for SEO, less likely to change with a redesign |
| `AutoThrottle` over a fixed delay | Adapts to real server load instead of guessing one number |
