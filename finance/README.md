# Trucker Finance & Deal Scorer

A single-user FastAPI web app that pairs a **savings tracker** (weekly income,
monthly expenses, a multi-bucket owner-operator savings goal) with a
**deal finder + scorer** for used Class 8 sleeper trucks and 53ft dry van
trailers.

Designed for a solo driver saving up for an owner-operator launch. Runs
alongside the existing WordPress stack as a second Docker service.

## What it does

- Log weekly income (gross/net, miles) and monthly expenses by category
- Configure a multi-bucket savings goal (truck, trailer, taxes/plates,
  authority, insurance down, equipment, operating reserve, contingency)
  with reasonable 2025-2026 defaults
- See current balance, weekly savings rate, weeks-to-goal, and a 26-week
  savings curve on one dashboard
- Scrape Craigslist `/hvo` (commercial vehicles) and `/trb` (trailers)
  across a configurable list of metros every few hours via RSS
- Import TruckPaper / CommercialTruckTrader / MyLittleSalesman / FB
  Marketplace / eBay listings by pasting the URL — JSON-LD schema parsing
  first, then BeautifulSoup fallback, then a manual form
- Score every listing 0-100 based on price vs. cohort median plus
  make/model/engine/era/mileage/condition modifiers tuned for Class 8
  sleepers and 53ft dry vans
- Explain every score with a line-item breakdown
- Export income / expenses / listings as CSV for taxes

## Running

1. Copy the env file and set a password:
   ```
   cp finance/.env.example finance/.env
   # edit finance/.env — at minimum change FINANCE_PASS
   ```

2. Build and start (from the repo root):
   ```
   docker compose up -d finance finance-worker
   ```

3. Visit `http://localhost:8001` and log in with the credentials from
   `finance/.env`. On your phone, use `http://<laptop-lan-ip>:8001`.

The existing WordPress site stays on port 8000 and is unaffected.

## Architecture

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI app, Basic Auth, router registration |
| `app/db.py` | SQLAlchemy engine (SQLite at `/data/finance.db`), seeds default savings buckets |
| `app/models.py` | ORM: `IncomeEntry`, `ExpenseEntry`, `SavingsGoal`, `SavingsSnapshot`, `Listing`, `ListingScore`, `MarketStat`, `ScrapeRun` |
| `app/summary.py` | Balance + weekly-avg + ETA calculations |
| `app/routers/` | `dashboard`, `income`, `expenses`, `goal`, `listings`, `imports`, `admin`, `exports` |
| `app/scrapers/craigslist.py` | Per-metro RSS poller for `/hvo` + `/trb` |
| `app/scrapers/paste.py` | URL importer: JSON-LD → selectors → manual fallback |
| `app/scoring/parser.py` | Regex extractors (year/make/model/engine/miles/VIN/price) |
| `app/scoring/modifiers.py` | All tunable scoring tables in one place |
| `app/scoring/market.py` | Cohort keys + median/p25/p75 aggregation |
| `app/scoring/truck.py` | Truck scoring formula |
| `app/scoring/trailer.py` | Trailer scoring formula |
| `app/scoring/engine.py` | Dispatch + persist `ListingScore` |
| `app/worker.py` | APScheduler: Craigslist every N hours, nightly market recompute, weekly savings snapshot |

Data (SQLite + cached HTML) lives in the `finance_data` Docker volume and
is downloadable via `/admin/backup`.

## Scoring — how it works

Each listing is scored 0-100. Higher = better deal.

**Base** (50): shifted by how far asking is from the median of comparable
listings in the same cohort (category × make/model × year bucket × mileage
band). Truck curve is `±50`, trailer curve is `±40` (flatter because trailers
are more commoditised).

**Truck modifiers** include:
- Model + engine combos (Cascadia DD15 +8, T680/579 X15 +6, VNL D13 2018+ +3,
  Maxxforce **−20** with a hard cap at 35)
- Emissions era (pre-2007 reliable but CARB-restricted if `CA_OPERATION=true`,
  2010-2012 first-gen SCR **−8**, 2017+ GHG17 **+4**)
- Mileage band (<400k +3, >1M −10)
- Keywords from title+description: in-frame/rebuild **+8**, APU +2, new tires
  +3, CARB compliant +4, salvage title **−25**, as-is / needs work **−15**,
  deleted/tuned DPF **−10 with hard cap at 35** (federal fine risk + resale
  poison)
- Completeness penalties for missing year/mileage/VIN/engine

**Trailer modifiers** include:
- Age band (2020+ +5, pre-2005 −8)
- Walls (composite +5, sheet-and-post −2)
- Doors (swing +3, roll-up **−4**)
- Suspension (air +5, spring **−10**)
- Keywords: new tires +4, soft spots **−8**, needs DOT −6, roof leaks **−10**

UI bucketing: 85+ **Strong buy**, 70-84 **Good deal**, 55-69 **Fair**,
40-54 **Priced high**, <40 **Skip**. Each score displays a confidence %
based on comp count.

## Data sources — current status

| Source | How | Status |
|---|---|---|
| Craigslist | Per-metro RSS `/hvo` + `/trb` | **Automated** every `SCRAPE_INTERVAL_HOURS` |
| TruckPaper | URL paste + JSON-LD | **Manual paste** (ToS prohibits scraping) |
| CommercialTruckTrader | URL paste + JSON-LD | **Manual paste** |
| MyLittleSalesman | URL paste + JSON-LD | **Manual paste** |
| FB Marketplace | Copy-paste text into manual form | **Manual** (login-walled, anti-bot) |
| eBay Motors | URL paste | **Manual** (add Browse API in phase 2) |

The URL importer tries `<script type="application/ld+json">` Product/Vehicle
schema first — both TruckPaper and CommercialTruckTrader emit it — then
falls back to Open Graph meta tags, then to a plain-text regex extractor on
the whole page. If all three fail you land on an editable form with
whatever could be parsed.

## Roadmap (nice-to-haves)

- Playwright-based headless fetcher for paste-URL when static parsing fails
- eBay Motors Browse API integration (behind `EBAY_APP_ID`)
- Sold-comp CSV import from Ritchie Bros / IronPlanet to weight `market_stats`
  (sold prices are more honest than asking prices)
- VIN decoder via NHTSA vPIC (free)
- Saved searches + ntfy/email alert when a new listing scores > 80
- Fuel/MPG log after O-O launch (same tracker extends to operational P&L)
- PWA manifest so the dashboard installs to the phone home screen
- Vietnamese i18n

## Legal / ToS notes

- **Craigslist** explicitly permits RSS polling (see their help pages).
- **TruckPaper, CommercialTruckTrader, MyLittleSalesman** all prohibit
  automated scraping in their ToS. This app does **not** scrape them —
  the URL importer only fires on an explicit user paste of a single URL,
  treating it as user-initiated fetch (the same as clicking the link in a
  browser).
- **Facebook Marketplace** requires authentication for most listings and
  rotates DOM frequently. This app does **not** attempt to scrape it —
  the manual form is the supported path.
- Delete features (DPF/EGR delete) are federally illegal (Clean Air Act);
  the scorer actively penalizes them as both resale poison and legal risk.
