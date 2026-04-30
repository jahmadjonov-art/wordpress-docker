"""Smoke test that boots the real Stockfish binary if available.

Skipped automatically when no `stockfish` binary is on PATH or at the default
Debian package location, so this test won't fail on a dev machine without the
engine installed.
"""
import asyncio
import os
import shutil

import chess
import pytest

from app.engine import StockfishEngine


def _engine_path() -> str | None:
    for cand in ("/usr/games/stockfish", "/usr/bin/stockfish", "/usr/local/bin/stockfish"):
        if os.path.exists(cand):
            return cand
    return shutil.which("stockfish")


pytestmark = pytest.mark.skipif(_engine_path() is None, reason="stockfish not installed")


@pytest.fixture
def engine():
    eng = StockfishEngine(_engine_path())
    eng.start()
    yield eng
    eng.close()


def test_engine_returns_legal_move_at_low_elo(engine):
    board = chess.Board()
    move = asyncio.run(engine.play(board, elo=1320, time_s=0.05))
    assert move in board.legal_moves


def test_engine_analyzes_startpos(engine):
    board = chess.Board()
    analysis = asyncio.run(engine.analyze(board, time_s=0.05))
    assert analysis.best_move in board.legal_moves
    assert -200 < analysis.score_cp < 200


def test_engine_falls_back_to_skill_level_for_low_elo(engine):
    board = chess.Board()
    move = asyncio.run(engine.play(board, elo=800, time_s=0.05))
    assert move in board.legal_moves
