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
