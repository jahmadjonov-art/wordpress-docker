# Chess teaching bot

Play chess against an adaptive Stockfish opponent that explains your moves and
the better alternatives in plain language. The bot's strength tracks your own
rating: win and it pushes harder next game, lose and it eases off.

This is a standalone subproject — it has its own `Dockerfile` and
`docker-compose.yml` and is **not** wired into the root `docker-compose.yml`
that runs the `finance/` service.

## Run

```sh
cd chess
cp .env.example .env
docker compose up --build -d
```

Then open http://localhost:8002.

## How adaptive strength works

Your local "you" player starts at `START_ELO` (1000 by default). After each
finished game, your rating updates with a standard Elo formula (K = 32). The
bot's rating for the **next** game is your current rating plus a small drift
based on the last result:

| Last game | Bot drift |
|---|---|
| You won  | +50 |
| You drew |   0 |
| You lost | −50 |

So the bot stays a touch above your level — challenging but not crushing.

If your rating drops below 1320 (Stockfish's `UCI_Elo` floor), the engine
switches to its `Skill Level` knob (0–8) with very short think times to
mimic weaker play.

## Commentary

After every move you make, Stockfish evaluates the position before and after.
The centipawn loss tiers your move:

| Loss | Tier |
|---|---|
| < 20 | Solid |
| 20–79 | Inaccuracy |
| 80–199 | Mistake |
| ≥ 200 | Blunder |

A small set of pattern detectors (hanging piece, fork, pin, check,
center-control change, castling, opening development) picks the most relevant
fact about the move, and a template stitches it into a one- or two-sentence
comment naming the move Stockfish preferred.

## Layout

```
chess/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── app/
    ├── main.py            # FastAPI app + Stockfish lifespan
    ├── config.py
    ├── db.py              # SQLite via SQLAlchemy
    ├── models.py          # Player, Game, Move
    ├── deps.py
    ├── engine.py          # Stockfish wrapper
    ├── coach.py           # rule-based commentary
    ├── rating.py          # Elo update + bot strength selection
    ├── routers/game.py    # game endpoints
    ├── templates/         # Jinja2 (base, index, board)
    └── static/            # CSS + JS (chessboard.js loaded from CDN)
```

## Tests

```sh
cd chess
pip install -r requirements.txt pytest
pytest
```

The Stockfish-dependent test (`tests/test_engine.py`) is skipped if the
`stockfish` binary isn't on `PATH`. Inside Docker it's at `/usr/games/stockfish`.
