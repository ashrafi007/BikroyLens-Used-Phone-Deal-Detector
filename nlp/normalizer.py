"""
BikroyLens NLP normalizer — Week 2.

Deliberately rule-based (regex + lookup dictionaries), not ML. Titles on
Bikroy are short and formulaic enough ("[Brand] [Model] [Storage] [Color]")
that pattern matching handles them reliably and stays debuggable — if a
rule misfires, you can see exactly which one, unlike an ML model's guess.

Anything that doesn't confidently match is left as None, never guessed —
same missing-data philosophy as the rest of the project.
"""

import re

# ----------------------------------------------------------------------
# Brand detection — checked in order. Xiaomi/OnePlus sub-brands (Redmi,
# Poco, Nord) are matched even when the parent brand name never appears
# in the title, which is the common case in real data.
# ----------------------------------------------------------------------
BRAND_PATTERNS = [
    ("Apple", re.compile(r"\biphone\b|\bapple\b", re.I)),
    ("Samsung", re.compile(r"\bsamsung\b|\bgalaxy\b", re.I)),
    ("Xiaomi", re.compile(r"\bxiaomi\b|\bredmi\b|\bpoco\b", re.I)),
    ("OnePlus", re.compile(r"\boneplus\b|\bnord\b", re.I)),
    ("Nothing Phone", re.compile(r"\bnothing\b", re.I)),
]

# ----------------------------------------------------------------------
# Model extraction — one generic pattern per brand family, capturing the
# naming *convention* rather than a hardcoded list of exact models. This
# means a brand-new model (e.g. a "Galaxy S26" that didn't exist when
# this was written) still gets parsed correctly, as long as the naming
# convention holds — same bet the project already makes on titles being
# formulaic. Only run against a title once its brand is already known,
# so "Galaxy" being optional for Samsung doesn't create cross-brand
# ambiguity.
# ----------------------------------------------------------------------
MODEL_PATTERNS = {
    "Apple": re.compile(
        r"iphone\s+(\d+\s*(?:pro\s*max|pro|plus|mini|e)?|xs\s*max|xs|xr|x|air)", re.I
    ),
    "Samsung": re.compile(
        r"(?:galaxy\s+)?(s\d+\s*(?:ultra|plus|fe)?|a\d+\s*(?:5g)?|m\d+\s*(?:5g)?|z\s*fold\d*|z\s*flip\d*|note\d*)",
        re.I,
    ),
    "Xiaomi": re.compile(
        r"(redmi\s+(?:note\s*\d+\w*|turbo\s*\d+\w*|k\d+\w*|pro|\d+\w*)|poco\s+[a-z]\d+|mi\s+\d+\w*|civi\s*\d*\w*|xiaomi\s+\d+\w*)\s*(?:pro|ultra|max)?",
        re.I,
    ),
    "OnePlus": re.compile(r"(oneplus\s+(?:\d+\w*|ace\s*\d*)|nord\s+\w*)", re.I),
    "Nothing Phone": re.compile(r"phone\s*\(?(\d+a?)\)?", re.I),
}

# ----------------------------------------------------------------------
# Storage / RAM — two notations seen in real data:
#   standalone:  "256 GB" / "256GB"          (storage only — the common case)
#   combined:    "12/256" / "8GB/128GB"      (RAM/storage together)
# ----------------------------------------------------------------------
COMBINED_RAM_STORAGE_RE = re.compile(r"\b(\d{1,2})\s*(?:gb)?\s*/\s*(\d{2,4})\s*(?:gb)?\b", re.I)
STANDALONE_STORAGE_RE = re.compile(r"\b(\d{2,4})\s*gb\b", re.I)
STANDALONE_STORAGE_TB_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*tb\b", re.I)

# ----------------------------------------------------------------------
# Condition grading — condition_raw from the scrape is Used, Brand New,
# or Refurbished (Bikroy's own field; not just a Used/New binary as
# originally assumed). These keywords refine "Used" into a specific grade
# when the title actually states one; otherwise it stays a generic "used"
# bucket rather than guessing a grade that isn't there. "Refurbished" is
# kept as its own value rather than folded into good/fair/poor — it's a
# distinct axis (professionally reconditioned), not a condition grade.
# ----------------------------------------------------------------------
CONDITION_KEYWORDS = [
    ("mint", re.compile(r"\bmint\b|\bexcellent\b|\bbrand\s*new\s*condition\b", re.I)),
    ("good", re.compile(r"\bgood\s*cond|\bfresh\b|\blike\s*new\b", re.I)),
    ("fair", re.compile(r"\bfair\b|\baverage\b|\bscratch", re.I)),
    ("poor", re.compile(r"\bpoor\b|\bcrack|\bdamage|\bfaulty\b|\bbroken\b", re.I)),
]


def _extract_brand(title):
    for brand, pattern in BRAND_PATTERNS:
        if pattern.search(title):
            return brand
    return None


def _extract_model(title, brand):
    pattern = MODEL_PATTERNS.get(brand)
    if not pattern:
        return None
    m = pattern.search(title)
    if not m:
        return None
    # normalize whitespace ("14   Pro" -> "14 Pro")
    return re.sub(r"\s+", " ", m.group(0)).strip()


def _extract_storage_and_ram(title):
    m = COMBINED_RAM_STORAGE_RE.search(title)
    if m:
        return f"{m.group(2)}GB", f"{m.group(1)}GB"  # storage, ram

    m = STANDALONE_STORAGE_RE.search(title)
    if m:
        return f"{m.group(1)}GB", None  # storage only, ram unknown

    m = STANDALONE_STORAGE_TB_RE.search(title)
    if m:
        return f"{int(float(m.group(1)) * 1024)}GB", None  # normalize TB -> GB

    return None, None


def _clean_condition(title, condition_raw):
    condition_raw = (condition_raw or "").strip().lower()

    for grade, pattern in CONDITION_KEYWORDS:
        if pattern.search(title):
            return grade

    if condition_raw == "brand new":
        return "mint"
    if condition_raw == "used":
        return "used"  # no finer grade stated in the title — stay generic
    if condition_raw == "refurbished":
        return "refurbished"
    return None


def parse_listing(raw_title, condition_raw=None):
    """
    Parse one listing's raw_title (+ optional condition_raw from the scrape)
    into the structured fields phones_normalized expects.

    Returns a dict with brand, model, storage, ram, condition_clean — any
    field that can't be confidently extracted is None.
    """
    title = raw_title or ""

    brand = _extract_brand(title)
    model = _extract_model(title, brand) if brand else None
    storage, ram = _extract_storage_and_ram(title)
    condition_clean = _clean_condition(title, condition_raw)

    return {
        "brand": brand,
        "model": model,
        "storage": storage,
        "ram": ram,
        "condition_clean": condition_clean,
    }
