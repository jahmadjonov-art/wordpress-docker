import pytest

from app import rating


def test_expected_score_symmetric():
    assert rating.expected_score(1500, 1500) == pytest.approx(0.5)


def test_expected_score_higher_rating_favored():
    assert rating.expected_score(1700, 1500) > 0.7
    assert rating.expected_score(1300, 1500) < 0.3


def test_score_from_result_white():
    assert rating.score_from_result("1-0", "w") == 1.0
    assert rating.score_from_result("0-1", "w") == 0.0
    assert rating.score_from_result("1/2-1/2", "w") == 0.5


def test_score_from_result_black():
    assert rating.score_from_result("1-0", "b") == 0.0
    assert rating.score_from_result("0-1", "b") == 1.0


def test_update_player_elo_win_against_equal():
    new_elo = rating.update_player_elo(1500, 1500, score=1.0)
    assert new_elo == 1500 + round(rating.K_FACTOR * 0.5)


def test_update_player_elo_loss_against_equal():
    new_elo = rating.update_player_elo(1500, 1500, score=0.0)
    assert new_elo == 1500 - round(rating.K_FACTOR * 0.5)


def test_next_bot_elo_drifts_up_after_win():
    assert rating.next_bot_elo(1200, last_score=1.0) == 1200 + rating.WIN_DRIFT


def test_next_bot_elo_drifts_down_after_loss():
    assert rating.next_bot_elo(1200, last_score=0.0) == 1200 + rating.LOSS_DRIFT


def test_next_bot_elo_no_history_pushes_up():
    # First-ever game should be a real challenge, not the player's exact rating.
    assert rating.next_bot_elo(1000, last_score=None) > 1000


def test_next_bot_elo_clamped_low():
    assert rating.next_bot_elo(rating.MIN_BOT_ELO - 200, last_score=0.0) == rating.MIN_BOT_ELO


def test_next_bot_elo_clamped_high():
    assert rating.next_bot_elo(rating.MAX_BOT_ELO + 200, last_score=1.0) == rating.MAX_BOT_ELO
