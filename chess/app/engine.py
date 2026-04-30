import asyncio
import threading
from dataclasses import dataclass
from typing import Optional

import chess
import chess.engine

from . import config


MATE_CP = 100_000  # cap used to convert mate scores to centipawns


@dataclass
class Analysis:
    best_move: chess.Move
    best_san: str
    score_cp: int  # from side-to-move's perspective, capped at +/- MATE_CP
    is_mate: bool
    pv: list[chess.Move]


def _score_to_cp(score: chess.engine.PovScore) -> tuple[int, bool]:
    """Convert PovScore to centipawns from white's POV. Mate scores are capped."""
    s = score.white()
    if s.is_mate():
        mate_in = s.mate()
        cp = MATE_CP if mate_in > 0 else -MATE_CP
        return cp, True
    return s.score(mate_score=MATE_CP) or 0, False


class StockfishEngine:
    """Thread-safe wrapper around a single long-lived Stockfish process.

    python-chess's SimpleEngine is sync and not safe for concurrent use, so
    every call holds a lock and runs in a worker thread to keep the FastAPI
    event loop responsive.
    """

    def __init__(self, path: str):
        self._path = path
        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._engine = chess.engine.SimpleEngine.popen_uci(self._path)

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except chess.engine.EngineError:
                pass
            self._engine = None

    def _ensure(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            raise RuntimeError("Stockfish engine not started")
        return self._engine

    def _analyze_sync(self, board: chess.Board, time_s: float) -> Analysis:
        with self._lock:
            eng = self._ensure()
            # Reset any previous strength limits before analyzing at full depth.
            try:
                eng.configure({"UCI_LimitStrength": False})
            except chess.engine.EngineError:
                pass
            info = eng.analyse(board, chess.engine.Limit(time=time_s))
        score_cp, is_mate = _score_to_cp(info["score"])
        # Flip to side-to-move POV so callers can reason about "good for me".
        if board.turn == chess.BLACK:
            score_cp = -score_cp
        pv = info.get("pv") or []
        if not pv:
            best = next(iter(board.legal_moves))
            pv = [best]
        best = pv[0]
        san = board.san(best)
        return Analysis(best_move=best, best_san=san, score_cp=score_cp, is_mate=is_mate, pv=pv)

    def _play_sync(self, board: chess.Board, elo: int, time_s: float) -> chess.Move:
        with self._lock:
            eng = self._ensure()
            options = self._strength_options(elo)
            try:
                eng.configure(options)
            except chess.engine.EngineError:
                # Some Stockfish builds reject unknown options; best-effort.
                pass
            limit = chess.engine.Limit(time=time_s)
            result = eng.play(board, limit)
        if result.move is None:
            # Fallback: pick a legal move. Should never happen unless game is over.
            return next(iter(board.legal_moves))
        return result.move

    @staticmethod
    def _strength_options(elo: int) -> dict:
        """Map a target Elo to Stockfish strength options.

        Stockfish's UCI_Elo accepts 1320-3190. Below that we fall back to the
        Skill Level knob (0-20) which makes deliberately bad moves.
        """
        if elo >= 1320:
            return {
                "UCI_LimitStrength": True,
                "UCI_Elo": max(1320, min(3190, elo)),
                "Skill Level": 20,
            }
        # Map 600..1319 -> Skill Level 0..8
        level = round((elo - 600) / 90)
        level = max(0, min(8, level))
        return {
            "UCI_LimitStrength": False,
            "Skill Level": level,
        }

    async def analyze(self, board: chess.Board, time_s: float | None = None) -> Analysis:
        return await asyncio.to_thread(
            self._analyze_sync, board, time_s or config.ENGINE_THINK_SECONDS
        )

    async def play(self, board: chess.Board, elo: int, time_s: float | None = None) -> chess.Move:
        # Weak bots think briefly so they don't compensate with raw search depth.
        default = 0.1 if elo < 1320 else config.ENGINE_THINK_SECONDS
        return await asyncio.to_thread(self._play_sync, board, elo, time_s or default)
