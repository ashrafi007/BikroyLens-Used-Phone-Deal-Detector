import scrapy


class ListingItem(scrapy.Item):
    # Matches the `listings` table schema in .claude/PROJECT_CONTEXT.md
    # (id is DB-assigned at load time, not collected here)
    raw_title = scrapy.Field()
    price = scrapy.Field()
    condition_raw = scrapy.Field()
    location = scrapy.Field()
    posted_date = scrapy.Field()
    url = scrapy.Field()
    photo_count = scrapy.Field()
    scraped_at = scrapy.Field()
    seller_type = scrapy.Field()

    # Extra, not in the original schema but cheap to grab and useful for the
    # NLP normalizer later (structured RAM/storage/battery info often lives here)
    description = scrapy.Field()
