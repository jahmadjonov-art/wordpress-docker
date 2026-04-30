"""Elo rating updates and bot-strength selection."""

K_FACTOR = 32
WIN_DRIFT = 50    # bot's next-game Elo bump after the player wins
LOSS_DRIFT = -50  # ...after the player loses
DRAW_DRIFT = 0
MIN_BOT_ELO = 600
MAX_BOT_ELO = 3000


def expected_score(player_elo: int, bot_elo: int) -> float:
    return 1.0 / (1.0 + 10 ** ((bot_elo - player_elo) / 400))


def score_from_result(result: str, player_color: str) -> float:
    """Convert PGN-style result to the player's score in {1, 0.5, 0}."""
    if result == "1/2-1/2":
        return 0.5
    if result == "1-0":
        return 1.0 if player_color == "w" else 0.0
    if result == "0-1":
        return 1.0 if player_color == "b" else 0.0
    raise ValueError(f"unknown result {result!r}")


def update_player_elo(player_elo: int, bot_elo: int, score: float) -> int:
    expected = expected_score(player_elo, bot_elo)
    return round(player_elo + K_FACTOR * (score - expected))


def next_bot_elo(player_elo: int, last_score: float | None) -> int:
    """Pick the bot's rating for the *next* game.

    The bot sits a touch above the player's level — it drifts up after a win,
    down after a loss, and stays put after a draw or with no history.
    """
    if last_score is None:
        drift = WIN_DRIFT  # first game ever: nudge up so it's a real challenge
    elif last_score >= 1.0:
        drift = WIN_DRIFT
    elif last_score <= 0.0:
        drift = LOSS_DRIFT
    else:
        drift = DRAW_DRIFT
    return max(MIN_BOT_ELO, min(MAX_BOT_ELO, player_elo + drift))
