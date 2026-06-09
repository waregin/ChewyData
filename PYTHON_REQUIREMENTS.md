# Python Rewrite: Chewy Data Scraper — Requirements Document

## 1. Overview

Rebuild the existing Java-based Chewy.com web scraper in Python with the following improvements over the original:

- Headless browser via **Playwright** to handle JavaScript-rendered pages, with an option to use Chewy's internal API if discoverable
- PostgreSQL database output with full historical price/availability tracking
- Concurrent execution with anti-ban rate limiting
- Externalized configuration (YAML)
- Designed to be called by an external scheduler (cron, GitHub Actions)

The original Java scraper scraped 16 Chewy.com product categories, extracted product variants and nutritional/allergen data, and exported to Excel. The Python version preserves all of that data collection while improving reliability, extensibility, and data storage.

### Prior work (waregin/ChewyScraper)

A Selenium + BeautifulSoup proof-of-concept exists in the `ChewyScraper` repo (`main.py`). It is superseded by this build but validated several things that carry forward:

- Chewy's product pages **require a real browser** (JS rendering confirmed necessary)
- The following CSS selectors are **confirmed still working** and should be used verbatim:
  - Product cards: `class="kib-product-card__content"`
  - Pagination: `class="kib-pagination-new__list-item"`
  - Product title block: `data-testid="product-title"`
  - Brand name: `data-testid="manufacture-name"`
  - Product heading: `data-testid="product-title-heading"`
  - Price: `data-testid="advertised-price"`
- Pagination URL pattern works: replace `p{N}` in the last page URL to generate intermediate page URLs
- Brand name appears inside the product title and must be stripped from the product name string

The Selenium code should not be extended further. Playwright is chosen for the full build due to its async-native API, built-in network request interception, and better anti-bot stealth support.

---

## 2. Scope

### In Scope
- All 16 product categories from the Java version (see §6)
- All data fields from the Java version (see §5)
- Multi-page pagination crawling
- Product variant/option enumeration (chip-style and dropdown-style selectors)
- Allergen detection against a configurable list
- Nutritional data extraction (protein, fat, fiber, moisture)
- Feeding instructions extraction
- Unit price calculation
- PostgreSQL persistence with historical runs
- YAML-based configuration
- Concurrent scraping with rate limiting
- Retry logic with exponential backoff
- CLI entry point suitable for external scheduler invocation

### Out of Scope
- Built-in scheduling (use cron or GitHub Actions)
- Excel export (replaced by PostgreSQL; add later if needed)
- GUI or dashboard
- The unrelated `TopSurgeryCountdown` utility from the Java project

---

## 3. Recommended Architecture

### 3.1 API-first investigation (do before full build)

Before committing to a full Playwright implementation, inspect Chewy's network traffic with browser devtools to look for internal REST or GraphQL API calls that return product data as JSON. The Java project includes a `data.json` file that appears to be a captured API response — this suggests Chewy does have an internal API. If a usable API is found:

- Prefer `httpx` (async HTTP client) over Playwright for those endpoints
- Document the endpoint(s) in `config.yaml`
- Use Playwright only for endpoints that cannot be replicated via direct API calls

### 3.2 Technology stack

| Concern | Library | Rationale |
|---|---|---|
| HTTP / JS rendering | `playwright` (async) | Confirmed necessary (Chewy requires JS); async-native; built-in network interception; replaces Selenium POC |
| Async HTTP (if API found) | `httpx[asyncio]` | Fast, async-native HTTP client for any discovered internal API endpoints |
| HTML parsing | `beautifulsoup4` + `lxml` | Familiar, robust CSS selector support |
| Database ORM | `sqlalchemy` (async) + `asyncpg` | Async PostgreSQL access; clean schema definition |
| Migrations | `alembic` | Schema versioning |
| Configuration | `pyyaml` | YAML config parsing |
| Data validation | `pydantic` | Validate and normalize scraped fields |
| CLI | `click` or `argparse` | Command-line interface |
| Logging | `structlog` or stdlib `logging` | Structured, level-aware logging |
| Concurrency | `asyncio` | Async/await throughout |
| Testing | `pytest` + `pytest-asyncio` | Unit and integration tests |
| Dependency management | `uv` or `pip` + `pyproject.toml` | Modern Python packaging |

**Python version:** 3.11+

### 3.3 Project layout

```
chewy_scraper/
├── pyproject.toml
├── config.yaml                  # All runtime configuration
├── alembic/                     # Database migrations
│   └── versions/
├── chewy_scraper/
│   ├── __init__.py
│   ├── main.py                  # CLI entry point
│   ├── config.py                # Config loading and validation
│   ├── models.py                # SQLAlchemy ORM models
│   ├── db.py                    # Database session management
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── browser.py           # Playwright setup and teardown
│   │   ├── category.py          # Category-level crawling (pagination)
│   │   ├── product.py           # Product-level scraping (variants, data)
│   │   ├── parsers.py           # HTML parsing utilities
│   │   └── api_client.py        # Direct API calls (if Chewy API found)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── normalizer.py        # Clean and normalize raw scraped data
│   │   └── writer.py            # Write to PostgreSQL
│   └── utils/
│       ├── __init__.py
│       ├── retry.py             # Retry/backoff logic
│       └── rate_limiter.py      # Request throttling
└── tests/
    ├── test_parsers.py
    ├── test_normalizer.py
    └── fixtures/
        ├── page.html            # Copied from Java resources
        └── data.json            # Copied from Java resources
```

---

## 4. Configuration (`config.yaml`)

All values below must be configurable without code changes.

```yaml
database:
  url: "postgresql+asyncpg://user:password@localhost:5432/chewydata"
  pool_size: 5

scraping:
  concurrency: 3               # Max simultaneous browser pages / requests
  request_delay_min: 2.0       # Seconds between requests (min)
  request_delay_max: 6.0       # Seconds between requests (max, random jitter)
  retry_max_attempts: 5
  retry_backoff_base: 2.0      # Exponential backoff base (seconds)
  user_agents:                 # Rotated randomly per request
    - "Mozilla/5.0 ..."
    - "Mozilla/5.0 ..."

categories:
  - name: "Pill Treats"
    url: "https://www.chewy.com/b/pill-covers-wraps-2693"
    size_matters: true
    want_nutrition: false
    want_feeding: false
    allergen_profiles: []          # Dog treats — no allergen screening by default

  - name: "Dental Chews"
    url: "https://www.chewy.com/b/dental-chews-1463"
    size_matters: true
    want_nutrition: false
    want_feeding: false
    allergen_profiles: []

  - name: "Dry Cat Food"
    url: "https://www.chewy.com/b/dry-food-388"
    size_matters: true
    want_nutrition: true
    want_feeding: true
    allergen_profiles: ["cat"]     # Screen against the "cat" pet profile

  # ... (all 16 categories; see §6 for full allergen_profiles assignments)

# Pet profiles define which allergens matter for each animal.
# A category can be screened against multiple profiles simultaneously.
# Adding a new profile (e.g., a dog with allergies) requires no code changes.
pet_profiles:
  - name: "cat"
    allergens:
      - alfalfa
      - kelp
      - rice
      - corn
      - peanut
      - spinach
      - flax
      - pumpkin
      - tomato
      - candida albicans
      - olive
      - mulberry      # Note: Java version had typo "mulberr" — fixed here
      - pecan
      - wheat
      - timothy
      - dandelion

  # Example future profile — uncomment and populate when needed:
  # - name: "dog"
  #   allergens:
  #     - chicken
  #     - beef
```

---

## 5. Data Model (PostgreSQL Schema)

### 5.1 Tables

**`scrape_runs`** — one row per execution of the scraper
```
id              SERIAL PRIMARY KEY
started_at      TIMESTAMPTZ NOT NULL
finished_at     TIMESTAMPTZ
status          VARCHAR(20)   -- 'running', 'complete', 'failed'
notes           TEXT
```

**`pet_profiles`** — one row per named pet/animal profile
```
id              SERIAL PRIMARY KEY
name            VARCHAR(100) UNIQUE NOT NULL   -- e.g. "cat", "dog"
```

**`pet_allergens`** — allergens belonging to a profile (configurable list)
```
id              SERIAL PRIMARY KEY
profile_id      INTEGER REFERENCES pet_profiles(id)
allergen        VARCHAR(100) NOT NULL
UNIQUE (profile_id, allergen)
```

**`categories`** — one row per configured category
```
id              SERIAL PRIMARY KEY
name            VARCHAR(100) UNIQUE NOT NULL
url             TEXT NOT NULL
size_matters    BOOLEAN NOT NULL DEFAULT false
want_nutrition  BOOLEAN NOT NULL DEFAULT false
want_feeding    BOOLEAN NOT NULL DEFAULT false
```

**`category_allergen_profiles`** — which pet profiles screen each category
```
category_id     INTEGER REFERENCES categories(id)
profile_id      INTEGER REFERENCES pet_profiles(id)
PRIMARY KEY (category_id, profile_id)
```

**`products`** — one row per unique product page URL
```
id              SERIAL PRIMARY KEY
category_id     INTEGER REFERENCES categories(id)
url             TEXT UNIQUE NOT NULL
brand_name      VARCHAR(200)
item_name       TEXT
image_url       TEXT
first_seen_at   TIMESTAMPTZ NOT NULL
last_seen_at    TIMESTAMPTZ NOT NULL
```

**`product_variants`** — one row per unique SKU/option combination
```
id              SERIAL PRIMARY KEY
product_id      INTEGER REFERENCES products(id)
sku             VARCHAR(100) UNIQUE NOT NULL
option_label    TEXT          -- e.g. "2.5 oz | 10 count"
size_value      NUMERIC       -- parsed numeric size
size_unit       VARCHAR(20)   -- "oz", "lb", etc.
count_value     INTEGER       -- number of pieces/items
first_seen_at   TIMESTAMPTZ NOT NULL
last_seen_at    TIMESTAMPTZ NOT NULL
```

**`price_snapshots`** — one row per variant per run (history)
```
id              SERIAL PRIMARY KEY
run_id          INTEGER REFERENCES scrape_runs(id)
variant_id      INTEGER REFERENCES product_variants(id)
scraped_at      TIMESTAMPTZ NOT NULL
price_cents     INTEGER       -- stored as cents to avoid float precision issues
price_per_each_cents INTEGER  -- calculated unit price
currency        VARCHAR(5) DEFAULT 'USD'
```

**`nutrition_snapshots`** — one row per variant per run (for food items)
```
id              SERIAL PRIMARY KEY
run_id          INTEGER REFERENCES scrape_runs(id)
variant_id      INTEGER REFERENCES product_variants(id)
scraped_at      TIMESTAMPTZ NOT NULL
protein_pct     NUMERIC(5,2)
fat_pct         NUMERIC(5,2)
fiber_pct       NUMERIC(5,2)
moisture_pct    NUMERIC(5,2)
feeding_instructions TEXT
```

**`allergen_detections`** — per-variant, per-profile allergen flags per run
```
id              SERIAL PRIMARY KEY
run_id          INTEGER REFERENCES scrape_runs(id)
variant_id      INTEGER REFERENCES product_variants(id)
profile_id      INTEGER REFERENCES pet_profiles(id)
scraped_at      TIMESTAMPTZ NOT NULL
allergen        VARCHAR(100) NOT NULL
detected        BOOLEAN NOT NULL
UNIQUE (run_id, variant_id, profile_id, allergen)
```

### 5.2 Design notes

- Prices stored as integer cents (avoids floating-point rounding errors; the Java version used BigDecimal for this reason)
- `product_variants` is deduplicated by `sku` — same SKU found across runs updates `last_seen_at` rather than creating a new row
- Full price and nutrition history is preserved via snapshot tables; queries can reconstruct price trends over time
- Allergen detections stored per-allergen and per-profile (normalized), enabling queries like "show me all cat food variants with no detected allergens for the cat profile"

### 5.3 Primary allergen-free query pattern

The central use case is: **find the cheapest variant of every cat food product that is safe for the cat.** The query pattern:

```sql
-- All cat food variants with no allergens detected for the cat profile
-- in the most recent scrape run
SELECT
    p.brand_name,
    p.item_name,
    pv.option_label,
    pv.size_value,
    pv.size_unit,
    pv.count_value,
    ps.price_cents / 100.0 AS price,
    ps.price_per_each_cents / 100.0 AS price_per_each
FROM product_variants pv
JOIN products p ON p.id = pv.product_id
JOIN categories c ON c.id = p.category_id
JOIN price_snapshots ps ON ps.variant_id = pv.id
    AND ps.run_id = (SELECT MAX(id) FROM scrape_runs WHERE status = 'complete')
JOIN pet_profiles pp ON pp.name = 'cat'
WHERE c.id IN (
    SELECT category_id FROM category_allergen_profiles
    WHERE profile_id = pp.id
)
AND NOT EXISTS (
    SELECT 1 FROM allergen_detections ad
    WHERE ad.variant_id = pv.id
      AND ad.profile_id = pp.id
      AND ad.run_id = ps.run_id
      AND ad.detected = true
)
ORDER BY ps.price_per_each_cents ASC;
```

This query should be documented and tested as a first-class feature of the system — it is the primary output consumers care about.

---

## 6. Categories to Scrape

Preserve all 16 categories from the Java version. The `allergen_profiles` column lists which pet profiles screen each category; empty means no allergen screening.

| Category | URL slug | size_matters | want_nutrition | want_feeding | allergen_profiles |
|---|---|---|---|---|---|
| Pill Treats | `/b/pill-covers-wraps-2693` | true | false | false | — |
| Dental Chews | `/b/dental-chews-1463` | true | false | false | — |
| Bully Sticks | `/b/bully-sticks-1543` | true | false | false | — |
| Bones | `/b/bones-1542` | true | false | false | — |
| Rawhide | `/b/rawhide-1545` | true | false | false | — |
| Antlers | `/b/antlers-1541` | true | false | false | — |
| Himalayan Chews | `/b/himalayan-chews-2780` | true | false | false | — |
| Natural Chews | `/b/natural-chews-1544` | true | false | false | — |
| Rawhide Alternatives | `/b/rawhide-alternatives-9939` | true | false | false | — |
| Hard Chews | `/b/hard-chews-9938` | true | false | false | — |
| Dog Food | `/b/food-332` | true | true | true | — |
| Dry Cat Food | `/b/dry-food-388` | true | true | true | cat |
| Premium Cat Food | `/b/premium-food-11741` | true | true | true | cat |
| Wet/Canned Cat Food | `/b/wet-food-389` | true | true | true | cat |
| Raw Cat Food | `/b/raw-food-8434` | true | true | true | cat |
| Freeze-Dried Cat Food | `/b/freeze-dried-dehydrated-food-11737` | true | true | true | cat |

**Note on dog treats:** The 10 treat categories are primarily dog products and don't require allergen screening by default. If a dog with allergies is added as a profile later, assign those categories to `["dog"]` in `config.yaml` — no code change required.

---

## 7. Crawling Logic

### 7.1 Category crawl

1. Load the category URL
2. Extract total page count from the pagination component
3. Enqueue all page URLs (page 1 to N)
4. For each page, extract product card URLs
5. Deduplicate product URLs across pages

### 7.2 Product crawl

For each product URL:
1. Load the product page
2. Detect option selector style (chip or dropdown — both must be supported)
3. Enumerate all option/variant combinations
4. For each variant, generate the variant URL: `{base_product_url}/{sku}`
5. Deduplicate SKUs globally (across categories)
6. Scrape each unique variant URL

### 7.3 Concurrency model

- Use `asyncio` with a semaphore to cap concurrent browser pages (configured by `scraping.concurrency`)
- Process categories sequentially; pages within a category concurrently up to the concurrency limit
- Apply random delay between requests (uniform distribution between `request_delay_min` and `request_delay_max`)

### 7.4 CSS selectors to target

The Java version used the following selectors (verify against current Chewy HTML at build time — Chewy changes class names periodically):

| Target | Selector type | Value |
|---|---|---|
| Product title | data-testid | `product-title` |
| Price | data-testid | `advertised-price` |
| Product image | class | `styles_mainCarouselImage__wj_bU` |
| Pagination | class | `kib-pagination-new__list-item` |
| Product cards | class | `kib-product-card ...` |
| Chip options | class | `kib-chip-choice__control` |
| Dropdown options | data-testid | `dropdown-radio-input` |
| Ingredients section | id | `INGREDIENTS-section` |
| Nutrition section | id | `GUARANTEED_ANALYSIS-section` |
| Feeding instructions | id | `FEEDING_INSTRUCTIONS-section` |

**Implementation note:** Wrap all selectors in a single `selectors.yaml` or constants file so they can be updated without touching scraping logic when Chewy changes its HTML.

---

## 8. Data Extraction Rules

### 8.1 Price
- Extract raw price string (e.g., `$24.99`)
- Strip `$` and convert to integer cents (e.g., `2499`)
- If price is unavailable, store `NULL`

### 8.2 Unit price (price per each)
- Divide price by count (use `decimal.Decimal` with `ROUND_FLOOR` to match Java behavior)
- Store result as integer cents

### 8.3 Size and count
- Extract from option label string using regex
- Size: match pattern like `(\d+\.?\d*)\s*(oz|lb|g|kg)`
- Count: match pattern like `(\d+)\s*(count|ct|pack|packs|piece|pieces)`
- Also check product name for count when option label does not contain it (Java logic)

### 8.4 Nutritional data
- Parse guaranteed analysis table: label in column 0, value in column 1
- Extract min/max values; store min (conservative) or the single value if only one is given
- Fields: Crude Protein, Crude Fat, Crude Fiber, Moisture

### 8.5 Allergen detection
- Fetch text content of `#INGREDIENTS-section`
- For each allergen in the configured list, do a **case-insensitive substring match**
- Store one row per allergen per variant per run in `allergen_detections`

### 8.6 Breed size filter
- For categories with `size_matters: true`, apply filter to show large/giant breed results
- In the Java version this was a URL parameter; verify the current Chewy filter mechanism

---

## 9. Anti-Ban Measures

The Java scraper caused an IP ban. The Python version must implement:

1. **Random delays** between requests (configured range, not fixed)
2. **User-Agent rotation** from a configurable list of real browser UA strings
3. **Referrer headers** to simulate natural navigation
4. **Playwright stealth mode** (`playwright-stealth` plugin or equivalent) to pass headless browser detection
5. **Respect HTTP 429** — if a 429 response is received, back off for a configurable duration before retrying
6. **Exponential backoff** on connection errors (base configured in YAML, attempts capped)
7. **Optional proxy support** — config should have a `proxy_url` field (nullable); if set, route all requests through it

---

## 10. Retry Logic

Preserve the Java retry behavior but improve it:

| Condition | Java behavior | Python behavior |
|---|---|---|
| 404 response | Return null, count error | Log warning, skip variant, record in DB |
| Connection error | Retry up to 5x, 15s fixed delay | Retry up to N times (configured), exponential backoff |
| 429 response | Not handled | Pause for configured duration, then retry |
| 5xx response | Not handled | Retry with backoff |
| Timeout | Not handled | Retry with backoff |

---

## 11. CLI Interface

```
python -m chewy_scraper [OPTIONS]

Options:
  --categories TEXT    Comma-separated category names to run (default: all)
  --dry-run            Scrape but do not write to database
  --log-level TEXT     DEBUG, INFO, WARNING, ERROR (default: INFO)
  --config FILE        Path to config.yaml (default: ./config.yaml)
  --help               Show this message and exit.
```

Exit codes:
- `0` — completed successfully
- `1` — completed with errors (some categories/products failed)
- `2` — fatal error (database unreachable, config invalid, etc.)

---

## 12. Logging

- Structured logging to stdout (JSON format for machine readability; human-readable format when TTY detected)
- Log level configurable via CLI flag and `LOG_LEVEL` environment variable
- Log per-category progress (products found, variants scraped, errors)
- Log final summary: total variants scraped, total errors, elapsed time, run ID

---

## 13. Known Bugs to Fix

These are bugs identified in the Java version that should be corrected in Python:

| Bug | Java location | Fix |
|---|---|---|
| Allergen typo "mulberr" | `SamsonAllergensList.java` | Correct to "mulberry" in `config.yaml` |
| Silent `NumberFormatException` | `ChewyDataMain.java` | Log a warning when numeric parsing fails |
| No rate limiting | Throughout | Implement delay and backoff (see §9) |
| Partial write on exception | `finally` block | Use DB transactions; commit per-variant so partial runs are recoverable |

---

## 14. Testing Requirements

| Test type | Scope | Notes |
|---|---|---|
| Unit tests | Parsers, normalizer, price calculation | Use fixture HTML/JSON from `src/main/resources/` |
| Integration tests | DB write pipeline | Use a test PostgreSQL database or SQLite override |
| Scraper smoke test | Single category, single product | Mark with `@pytest.mark.slow`; not run in CI by default |

Minimum coverage target: 70% on `parsers.py` and `normalizer.py`.

---

## 15. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Scrape rate | No more than 1 request per 2 seconds on average |
| Resumability | If interrupted mid-run, a subsequent run should pick up where it left off (skip already-scraped SKUs in the same `run_id`, or skip if scraped within last N hours) |
| Idempotency | Running twice in a row should produce the same DB state (no duplicate rows) |
| Python version | 3.11+ |
| Platform | Linux (for cron/GH Actions); macOS for local development |

---

## 16. Suggested Implementation Order

1. **Spike: find Chewy's internal API** — With Playwright's network interception, intercept all XHR/Fetch calls while loading a Chewy category or product page. Look for JSON responses matching product data (a candidate response is already captured in `ChewyData/src/main/resources/data.json`). If a usable endpoint is found, document it and build `api_client.py` first — this could eliminate browser rendering for those pages entirely.
2. **Database schema and migrations** — Define SQLAlchemy models, run `alembic init`, generate first migration.
3. **Config loading** — `config.py` with Pydantic validation of `config.yaml`.
4. **Parsers (offline)** — Write `parsers.py` using the confirmed selectors from §1 (Prior work). Test against the fixture HTML in `ChewyData/src/main/resources/page.html`.
5. **Browser module** — Playwright setup with stealth, UA rotation, configurable delay.
6. **Category + product crawler** — Pagination (confirmed pattern from POC) and variant enumeration (the main missing piece from the POC).
7. **Pipeline / writer** — Connect scraped data to PostgreSQL via SQLAlchemy.
8. **CLI entry point** — Wire it all together with `click`.
9. **Anti-ban hardening** — Add all measures from §9.
10. **Integration test** — Run against a single cat food category end-to-end; verify allergen detection and DB writes.

---

## 17. Open Questions / Decisions to Revisit

- **Chewy API exists?** Check before starting §16.1; the `data.json` file in the Java project suggests one may be available. If so, this simplifies the scraper significantly and reduces ban risk.
- **Proxy rotation?** Depending on ban risk, a rotating proxy service (Bright Data, Oxylabs, etc.) may be necessary. The config supports it (`proxy_url`), but subscribing to one is a separate decision.
- **Export to Excel?** If stakeholders still need Excel output, an export command (`python -m chewy_scraper export --format xlsx`) can be added later via `openpyxl`. Not in scope for the initial build.
- **Cat food allergen detection?** The Java version has a comment about allergen detection on wet cat food. Confirm whether allergen detection should apply to all categories or only treats.
