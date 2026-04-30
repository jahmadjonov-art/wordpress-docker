"""Rule-based commentary on a human's move.

Given the position before the move, the move that was played, the engine's
preferred move, and a centipawn-loss number, produce a short natural-ish
sentence that names the tier (solid/inaccuracy/mistake/blunder), points to
the better move when there is one, and slots in a feature observation
(hanging piece, fork, check, etc.) chosen from the resulting position.
"""

from dataclasses import dataclass

import chess


PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}

PIECE_NAME = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

CENTER_SQUARES = (chess.D4, chess.E4, chess.D5, chess.E5)


@dataclass
class Commentary:
    tier: str  # 'solid' | 'inaccuracy' | 'mistake' | 'blunder'
    text: str


def tier_for(cp_loss: int, mate_lost: bool) -> str:
    if mate_lost:
        return "blunder"
    if cp_loss < 20:
        return "solid"
    if cp_loss < 80:
        return "inaccuracy"
    if cp_loss < 200:
        return "mistake"
    return "blunder"


def _piece_at_to(board_after: chess.Board, move: chess.Move) -> chess.Piece | None:
    return board_after.piece_at(move.to_square)


def _hanging(board_after: chess.Board, square: int, mover_color: bool) -> bool:
    """A piece is hanging if the opponent attacks it more than the mover defends it."""
    attackers = board_after.attackers(not mover_color, square)
    defenders = board_after.attackers(mover_color, square)
    return len(attackers) > len(defenders)


def _is_fork(board_after: chess.Board, move: chess.Move, mover_color: bool) -> tuple[bool, list[int]]:
    """Does the moved piece attack two or more enemy pieces of equal/greater value?"""
    moved = board_after.piece_at(move.to_square)
    if moved is None:
        return False, []
    own_value = PIECE_VALUE[moved.piece_type]
    targets: list[int] = []
    for sq in board_after.attacks(move.to_square):
        target = board_after.piece_at(sq)
        if target is None or target.color == mover_color:
            continue
        # Pinning a king or threatening any equal/greater piece counts.
        if target.piece_type == chess.KING or PIECE_VALUE[target.piece_type] >= own_value:
            targets.append(sq)
    return len(targets) >= 2, targets


def _center_delta(before: chess.Board, after: chess.Board, color: bool) -> int:
    def count(b: chess.Board) -> int:
        return sum(len(b.attackers(color, sq)) for sq in CENTER_SQUARES)

    return count(after) - count(before)


def _develops_minor(before: chess.Board, move: chess.Move, color: bool) -> bool:
    if before.fullmove_number > 12:
        return False
    piece = before.piece_at(move.from_square)
    if piece is None or piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return False
    back_rank = 0 if color == chess.WHITE else 7
    return chess.square_rank(move.from_square) == back_rank


def _feature_note(before: chess.Board, after: chess.Board, move: chess.Move) -> str | None:
    """Pick the most interesting positive feature of a played move."""
    mover_color = not after.turn  # `after` has the side-to-move flipped
    if after.is_checkmate():
        return "checkmate"
    if before.is_castling(move):
        return "tucks the king to safety"
    if before.is_capture(move):
        captured_type = before.piece_type_at(move.to_square)
        if captured_type is None and before.is_en_passant(move):
            captured_type = chess.PAWN
        if captured_type is not None:
            return f"wins a {PIECE_NAME[captured_type]}"
    is_fork, targets = _is_fork(after, move, mover_color)
    if is_fork:
        return f"forks {len(targets)} pieces"
    if before.gives_check(move):
        return "puts the king in check"
    if _develops_minor(before, move, mover_color):
        return "develops a minor piece"
    delta = _center_delta(before, after, mover_color)
    if delta >= 2:
        return "increases pressure on the center"
    return None


def _bad_consequence(before: chess.Board, after: chess.Board, move: chess.Move) -> str:
    """Describe the most concrete thing wrong with the move."""
    mover_color = not after.turn
    if after.is_checkmate():
        return "lets the opponent deliver mate"
    moved = _piece_at_to(after, move)
    if moved is not None and _hanging(after, move.to_square, mover_color):
        return f"leaves the {PIECE_NAME[moved.piece_type]} hanging on {chess.square_name(move.to_square)}"
    # Find the worst hanging own piece anywhere on the board.
    worst: tuple[int, int] | None = None  # (value, square)
    for sq, p in after.piece_map().items():
        if p.color != mover_color:
            continue
        if _hanging(after, sq, mover_color):
            v = PIECE_VALUE[p.piece_type]
            if worst is None or v > worst[0]:
                worst = (v, sq)
    if worst is not None:
        sq = worst[1]
        piece_type = after.piece_type_at(sq)
        return f"leaves the {PIECE_NAME[piece_type]} on {chess.square_name(sq)} undefended"
    return "loses material or weakens the position"


def comment_on_move(
    board_before: chess.Board,
    move: chess.Move,
    san: str,
    best_move: chess.Move | None,
    best_san: str | None,
    cp_loss: int,
    mate_lost: bool = False,
) -> Commentary:
    """Build a one- to two-sentence comment on a played move."""
    board_after = board_before.copy()
    board_after.push(move)

    tier = tier_for(cp_loss, mate_lost)
    feature = _feature_note(board_before, board_after, move)

    if tier == "solid":
        if feature:
            text = f"{san} — solid; {feature}."
        else:
            text = f"{san} — solid."
        return Commentary(tier=tier, text=text)

    bad = _bad_consequence(board_before, board_after, move)

    if best_san and best_move and best_move != move:
        # Describe why the engine's pick was better, in terms of *its* result.
        best_after = board_before.copy()
        best_after.push(best_move)
        best_feature = _feature_note(board_before, best_after, best_move) or "keeps the position balanced"
    else:
        best_san = None
        best_feature = None

    if tier == "inaccuracy":
        if best_san:
            text = f"{san} is a bit loose. {best_san} was stronger — it {best_feature}."
        else:
            text = f"{san} is a bit loose."
    elif tier == "mistake":
        if best_san:
            text = f"{san} is a mistake — it {bad}. Better was {best_san}, which {best_feature}."
        else:
            text = f"{san} is a mistake — it {bad}."
    else:  # blunder
        if best_san:
            text = f"Blunder. {san} {bad}. {best_san} would have kept you in the game."
        else:
            text = f"Blunder. {san} {bad}."

    return Commentary(tier=tier, text=text)


def bot_move_note(board_before: chess.Board, move: chess.Move, san: str) -> str:
    """Short note explaining the bot's reply, used as a hint to the player."""
    board_after = board_before.copy()
    board_after.push(move)
    if board_after.is_checkmate():
        return f"{san} — checkmate."
    if board_after.is_check():
        return f"{san} — check."
    if board_before.is_capture(move):
        captured = board_before.piece_type_at(move.to_square)
        if captured is None and board_before.is_en_passant(move):
            captured = chess.PAWN
        if captured is not None:
            return f"{san} — captures your {PIECE_NAME[captured]}."
    is_fork, targets = _is_fork(board_after, move, not board_after.turn)
    if is_fork:
        return f"{san} — eyes {len(targets)} of your pieces at once."
    if board_before.is_castling(move):
        return f"{san} — castles."
    return f"{san}."
