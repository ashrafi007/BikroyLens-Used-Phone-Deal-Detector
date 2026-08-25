import os
import re
from datetime import datetime, timezone

import scrapy


class BikroySpider(scrapy.Spider):
    """
    Reads every bracket URL from links.md (the project's verified,
    per-brand/city/price-tier scrape filters — see PROJECT_CONTEXT.md),
    pages through each bracket's search results, follows every listing
    to its detail page, and scrapes the full field set from there
    (detail-page-per-listing design, as decided for this project).

    Same-listing dedup across overlapping brackets happens live, via
    self.followed_urls, instead of waiting for the loader step.
    """

    name = "bikroy"
    allowed_domains = ["bikroy.com"]
    custom_settings = {
        "CLOSESPIDER_ITEMCOUNT": 1000,  # today's target
    }
    MAX_PAGES_PER_BRACKET = 4

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.followed_urls = set()

    async def start(self):
        # Scrapy 2.13+ replaced the old sync start_requests() hook with this
        # async generator — start_requests() alone is silently never called.
        links_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "links.md"
        )
        with open(links_path, encoding="utf-8") as f:
            text = f.read()
        urls = re.findall(r'"(https://bikroy\.com/[^"]+)"', text)
        self.logger.info(f"Loaded {len(urls)} bracket URLs from links.md")

        for bracket_url in urls:
            yield scrapy.Request(
                self._with_page(bracket_url, 1),
                callback=self.parse_search,
                meta={"bracket_url": bracket_url, "page": 1},
            )

    @staticmethod
    def _with_page(url, page):
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}page={page}"

    def parse_search(self, response):
        bracket_url = response.meta["bracket_url"]
        page = response.meta["page"]

        hrefs = response.css("a.qa-advert-list-item::attr(href)").getall()
        new_on_page = 0
        for href in hrefs:
            # strip tracking query params (?page=&pos=&lid=...), keep canonical path
            full_url = response.urljoin(href.split("?")[0])
            if full_url in self.followed_urls:
                continue
            self.followed_urls.add(full_url)
            new_on_page += 1
            yield scrapy.Request(
                full_url, callback=self.parse_detail, meta={"bracket_url": bracket_url}
            )

        # keep paging this bracket only while it's still surfacing new listings
        if new_on_page > 0 and page < self.MAX_PAGES_PER_BRACKET:
            yield scrapy.Request(
                self._with_page(bracket_url, page + 1),
                callback=self.parse_search,
                meta={"bracket_url": bracket_url, "page": page + 1},
            )

    def parse_detail(self, response):
        title = response.css(
            ".b-advert-title-inner.b-advert-title-inner--h1::text"
        ).get(default="").strip()

        price = response.css('[itemprop="price"]::attr(content)').get()

        condition_raw = response.css(
            '.b-advert-attribute__value[itemprop="itemCondition"]::text'
        ).get(default="").strip()

        region_text = response.css(".b-advert-info-statistics--region::text").get(default="")
        location, posted_date = self._split_location_date(region_text.strip())

        photo_count = len(response.css(".qa-carousel-thumbnail__image"))

        description = " ".join(
            t.strip()
            for t in response.css('[itemprop="description"] ::text').getall()
            if t.strip()
        )

        # Best-effort heuristic: no clean structured individual-vs-business
        # field was found on the detail page (see conversation notes) —
        # sellers who list a physical shop location in their description
        # are treated as business, everyone else as individual.
        seller_type = "business" if "shop location" in description.lower() else "individual"

        yield {
            "raw_title": title,
            "price": price,
            "condition_raw": condition_raw,
            "location": location,
            "posted_date": posted_date,
            "url": response.url,
            "photo_count": photo_count,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "seller_type": seller_type,
            "description": description,
        }

    @staticmethod
    def _split_location_date(text):
        # e.g. "Dhaka, Jamuna Future Park, 2 hours ago"
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if len(parts) >= 3:
            location = ", ".join(parts[:-1])
            posted_date = parts[-1]
        elif len(parts) == 2:
            location, posted_date = parts
        elif len(parts) == 1:
            location, posted_date = parts[0], ""
        else:
            location, posted_date = "", ""
        return location, posted_date
