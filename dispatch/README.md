# Freight Dispatcher — "LoadScorer"

A truckload **load-scoring and rate-negotiation** tool for owner-operators and
dispatchers. Paste a load, and it:

1. **Geocodes the lane** and computes driving **miles** (truck routing) + deadhead.
2. Computes **cost-per-mile** and **estimated profit** (fuel + maintenance +
   a slice of fixed monthly overhead).
3. **Scores the load 0–100** (bad → good) by comparing its rate-per-mile against
   a market benchmark we build from the loads you've seen on similar lanes.
4. Tells you the **rate to push for** (the target that hits your margin and
   matches the better end of the lane's market).
5. Optionally **verifies the broker** (FMCSA authority) and **drafts a
   negotiation email** with Claude.

It's the same architecture as the sibling `finance/` deal-scorer, pointed at
loads instead of truck listings (scrape/import → parse → score → benchmark).

## How scoring works

```
base  = 50 + clamp(±50, (rate_per_mile − lane_median) / lane_median × 100)
score = base + deadhead band + margin-vs-target band + broker authority
             + risk-keyword deltas + completeness penalties      (clamped 0–100)
```

Lane benchmarks (`LaneStat`) are recomputed nightly (and on demand) as
median/p25/p75 of rate-per-mile within each `equipment | origin-region |
dest-region` cohort, widening when an exact lane has too few samples. The
scoring tables live in `app/scoring/modifiers.py` — tune them freely.

**Cold start:** until a lane has enough of your own loads, the score falls back
to a seasonally-adjusted national reference rate (`app/scoring/reference.py` +
`app/seasonality.py`), so it's useful on load #1.

### Beyond a flat rate-per-mile

- **True-net economics** (`economics.py`): profit is computed on *net* revenue —
  rate minus lumper/accessorials minus financing cost (factoring vs quick-pay vs
  net terms). It also reports **deadhead-adjusted RPM** (rate over loaded +
  deadhead) and **profit per on-duty hour** (hours-of-service aware, flags
  multi-day loads).
- **Broker reliability score** (`app/scoring/broker_rating.py`): an Elo-style
  rating (seeded 1500) that drifts on outcomes you log after a load runs — paid
  on time / short / detention honored / TONU. It feeds the load score, replacing
  a blunt authority-only check with something that learns from your experience.
- **Produce-season awareness**: reefer reference rates lift during produce season
  and by producing region.
- **Broker margin ledger (49 CFR 371.3)**: optionally log the broker margin you
  uncover via your own records request; it averages per broker. There is no
  public margin feed — this is the realistic, bottom-up way to benchmark it.

## Free data sources (all optional — the app runs with zero keys)

| Capability | Source | Without a key |
|---|---|---|
| Truck miles + geocoding | OpenRouteService (`driving-hgv`) or self-hosted OSRM | great-circle × 1.2 road factor; OSM Nominatim geocoding |
| Diesel price | EIA open-data API | configured `DEFAULT_DIESEL_CPG` |
| Broker authority | FMCSA QCMobile | "configure key" notice |
| Negotiation letter | Anthropic (Claude) | dormant; "configure key" notice |

Copy `.env.example` to `.env` and fill in whatever keys you have. See the file
for signup links.

## Run

```bash
cp dispatch/.env.example dispatch/.env   # edit the login at minimum
docker compose up --build dispatch dispatch-worker
# open http://localhost:8003
```

`dispatch` serves the web UI (port 8003); `dispatch-worker` runs the nightly
fuel refresh + lane recompute + rescore.

## Layout

- `app/economics.py` — cost-per-mile + target-rate model
- `app/scoring/` — `lane.py` (benchmark cohorts), `load.py` (the 0–100 formula),
  `engine.py` (persist scores), `modifiers.py` (tunable tables)
- `app/integrations/` — `routing.py`, `eia.py`, `fmcsa.py`
- `app/ai/negotiate.py` — Claude negotiation letter (dormant without a key)
- `app/routers/` — dashboard, loads, settings, exports
- `app/worker.py` — APScheduler background jobs

## Tests

```bash
cd dispatch && pip install -r requirements.txt pytest && pytest
```

## Notes

This is decision-support, not legal/financial advice. Rate benchmarks are built
from the loads *you* enter — they get better as you log more. No paid load-board
or rate feed is required.
