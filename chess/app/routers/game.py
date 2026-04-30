from datetime import datetime
from pathlib import Path
from typing import Any

import chess
import chess.pgn
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import coach, models, rating
from ..db import get_db
from ..deps import get_engine
from ..engine import StockfishEngine

BASE = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

router = APIRouter()


def _board_from(game: models.Game) -> chess.Board:
    return chess.Board(game.current_fen)


def _outcome_to_result(board: chess.Board) -> str | None:
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return None
    if outcome.winner is None:
        return "1/2-1/2"
    return "1-0" if outcome.winner == chess.WHITE else "0-1"


def _last_player_score(db: Session, player_id: int) -> float | None:
    """Score of the player's most recent finished game, or None if no games."""
    last = (
        db.query(models.Game)
        .filter(models.Game.player_id == player_id, models.Game.result.is_not(None))
        .order_by(models.Game.finished_at.desc().nullslast(), models.Game.id.desc())
        .first()
    )
    if last is None:
        return None
    return rating.score_from_result(last.result, last.player_color)


def _append_pgn(game: models.Game, board_before: chess.Board, move: chess.Move) -> None:
    """Append the move to the game's PGN string in-place."""
    san = board_before.san(move)
    if board_before.turn == chess.WHITE:
        prefix = f"{board_before.fullmove_number}. "
    else:
        # If this is the very first stored move and it's black to move,
        # PGN convention writes "1... Nf6" — we don't need that here because
        # games always start at the standard position.
        prefix = ""
    sep = " " if game.pgn else ""
    game.pgn = f"{game.pgn}{sep}{prefix}{san}"


def _serialize_move(move: models.Move) -> dict[str, Any]:
    return {
        "ply": move.ply,
        "san": move.san,
        "by": move.by,
        "tier": move.tier,
        "commentary": move.commentary,
    }


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    player = db.get(models.Player, 1)
    games = (
        db.query(models.Game)
        .filter(models.Game.player_id == player.id)
        .order_by(models.Game.id.desc())
        .limit(25)
        .all()
    )
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "player": player, "games": games},
    )


@router.post("/game/new")
async def new_game(
    db: Session = Depends(get_db),
    engine: StockfishEngine = Depends(get_engine),
):
    player = db.get(models.Player, 1)
    if player is None:
        raise HTTPException(500, "player not seeded")

    bot_elo = rating.next_bot_elo(player.elo, _last_player_score(db, player.id))
    game = models.Game(
        player_id=player.id,
        bot_elo=bot_elo,
        player_color="w",
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return RedirectResponse(url=f"/game/{game.id}", status_code=303)


@router.get("/game/{game_id}", response_class=HTMLResponse)
def view_game(game_id: int, request: Request, db: Session = Depends(get_db)):
    game = db.get(models.Game, game_id)
    if game is None:
        raise HTTPException(404)
    moves = [_serialize_move(m) for m in game.moves]
    player = db.get(models.Player, game.player_id)
    return templates.TemplateResponse(
        "board.html",
        {
            "request": request,
            "game": game,
            "moves": moves,
            "player": player,
            "game_over": game.result is not None,
        },
    )


@router.post("/game/{game_id}/move")
async def make_move(
    game_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    engine: StockfishEngine = Depends(get_engine),
):
    game = db.get(models.Game, game_id)
    if game is None:
        raise HTTPException(404)
    if game.result is not None:
        raise HTTPException(400, "game already finished")

    src = payload.get("from")
    dst = payload.get("to")
    promotion = payload.get("promotion")
    if not src or not dst:
        raise HTTPException(400, "missing from/to")

    board = _board_from(game)
    uci = f"{src}{dst}{promotion or ''}"
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        raise HTTPException(400, "malformed move")
    if move not in board.legal_moves:
        raise HTTPException(400, "illegal move")

    # Pre-move analysis: best move and eval before the human plays.
    pre = await engine.analyze(board)
    eval_before = pre.score_cp

    san = board.san(move)
    board_before = board.copy()
    board.push(move)

    # Post-move eval. board.turn flipped to the bot's POV; flip back to player.
    post = await engine.analyze(board)
    eval_after = -post.score_cp  # flip to player's POV

    cp_loss = max(0, eval_before - eval_after)
    mate_lost = pre.is_mate and pre.score_cp > 0 and eval_after < eval_before - 100
    commentary = coach.comment_on_move(
        board_before=board_before,
        move=move,
        san=san,
        best_move=pre.best_move,
        best_san=pre.best_san,
        cp_loss=cp_loss,
        mate_lost=mate_lost,
    )

    _append_pgn(game, board_before, move)
    ply = len(game.moves) + 1
    db.add(models.Move(
        game_id=game.id,
        ply=ply,
        san=san,
        uci=move.uci(),
        by="human",
        eval_cp_before=eval_before,
        eval_cp_after=eval_after,
        tier=commentary.tier,
        commentary=commentary.text,
    ))

    bot_san: str | None = None
    bot_note: str | None = None
    result = _outcome_to_result(board)

    if result is None:
        bot_move = await engine.play(board, game.bot_elo)
        bot_board_before = board.copy()
        bot_san = board.san(bot_move)
        bot_note = coach.bot_move_note(bot_board_before, bot_move, bot_san)
        board.push(bot_move)
        _append_pgn(game, bot_board_before, bot_move)
        db.add(models.Move(
            game_id=game.id,
            ply=ply + 1,
            san=bot_san,
            uci=bot_move.uci(),
            by="bot",
            commentary=bot_note,
        ))
        result = _outcome_to_result(board)

    game.current_fen = board.fen()

    if result is not None:
        game.result = result
        game.finished_at = datetime.utcnow()
        player = db.get(models.Player, game.player_id)
        score = rating.score_from_result(result, game.player_color)
        player.elo = rating.update_player_elo(player.elo, game.bot_elo, score)
        player.games_played += 1

    db.commit()

    return JSONResponse({
        "fen": board.fen(),
        "your_san": san,
        "your_commentary": commentary.text,
        "your_tier": commentary.tier,
        "bot_san": bot_san,
        "bot_note": bot_note,
        "eval_cp": eval_after,
        "result": result,
        "game_over": result is not None,
    })


@router.post("/game/{game_id}/resign")
async def resign(game_id: int, db: Session = Depends(get_db)):
    game = db.get(models.Game, game_id)
    if game is None:
        raise HTTPException(404)
    if game.result is not None:
        return JSONResponse({"result": game.result})

    # Player resigns → opposite color wins.
    game.result = "0-1" if game.player_color == "w" else "1-0"
    game.finished_at = datetime.utcnow()
    player = db.get(models.Player, game.player_id)
    score = rating.score_from_result(game.result, game.player_color)
    player.elo = rating.update_player_elo(player.elo, game.bot_elo, score)
    player.games_played += 1
    db.commit()
    return JSONResponse({"result": game.result})
