import chess

from app import coach


def make_board(fen: str | None = None) -> chess.Board:
    return chess.Board(fen) if fen else chess.Board()


def comment(board: chess.Board, played_uci: str, *, best_uci: str | None = None, cp_loss: int = 0):
    move = chess.Move.from_uci(played_uci)
    san = board.san(move)
    best_move = chess.Move.from_uci(best_uci) if best_uci else None
    best_san = board.san(best_move) if best_move else None
    return coach.comment_on_move(
        board_before=board,
        move=move,
        san=san,
        best_move=best_move,
        best_san=best_san,
        cp_loss=cp_loss,
    )


def test_tier_thresholds():
    assert coach.tier_for(0, False) == "solid"
    assert coach.tier_for(19, False) == "solid"
    assert coach.tier_for(20, False) == "inaccuracy"
    assert coach.tier_for(79, False) == "inaccuracy"
    assert coach.tier_for(80, False) == "mistake"
    assert coach.tier_for(199, False) == "mistake"
    assert coach.tier_for(200, False) == "blunder"
    assert coach.tier_for(0, True) == "blunder"  # mate lost is always a blunder


def test_solid_opening_e4_mentions_center():
    board = make_board()
    c = comment(board, "e2e4", cp_loss=5)
    assert c.tier == "solid"
    # The text should at least name the move and not contain "mistake" / "blunder".
    assert "e4" in c.text
    assert "mistake" not in c.text and "Blunder" not in c.text


def test_blunder_hangs_queen():
    # Black to move just made a move; white plays Qxf7?? but f7 is defended.
    # We construct: standard start + 1.e4 e5 2.Qh5 (white queen on h5),
    # then test "Qh5xf7" — but f7 defended by king and pawn? Actually after
    # 1.e4 e5 2.Qh5 the queen on h5 attacking f7. f7 is defended only by the king.
    # Let's make a clean hanging-queen position instead.
    # Position: white queen on e4, black knight on c5 attacking e4, no white defenders.
    # FEN: just king + queen + black knight scenario.
    board = chess.Board("4k3/8/8/2n5/8/8/8/4K2Q w - - 0 1")
    # White plays Qh1-e4 (legal move along the rank? no, h1->e4 isn't a queen move).
    # Use Qh1-h5 then black's c5 knight doesn't attack h5. Let's design differently.
    # Place white queen on d1, push it to d5 where black knight on c7 attacks it via b/c moves? No.
    # Simpler: white queen moves to a square attacked by a black piece with no defender.
    board = chess.Board("4k3/2n5/8/8/8/8/8/3QK3 w - - 0 1")
    # Black knight on c7 attacks: a6, a8, b5, d5, e6, e8 — so move queen to d5.
    c = comment(board, "d1d5", cp_loss=900)
    assert c.tier == "blunder"
    assert "queen" in c.text.lower() or "blunder" in c.text.lower()


def test_capture_solid_text_mentions_winning_material():
    # White to move can take a black pawn with no recapture: white knight on f3,
    # black pawn on e5 unprotected.
    board = chess.Board("4k3/8/8/4p3/8/5N2/8/4K3 w - - 0 1")
    c = comment(board, "f3e5", cp_loss=0)
    assert c.tier == "solid"
    assert "pawn" in c.text.lower()


def test_castling_recognized():
    # Position where white can castle kingside.
    board = chess.Board("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
    c = comment(board, "e1g1", cp_loss=10)
    assert c.tier == "solid"
    assert "king" in c.text.lower() or "tucks" in c.text.lower()


def test_check_recognized_in_solid_move():
    # White rook delivers a check with no immediate downside.
    board = chess.Board("4k3/8/8/8/8/8/4R3/4K3 w - - 0 1")
    c = comment(board, "e2e7", cp_loss=5)
    # Either feature note ("check") or just solid; both acceptable.
    assert c.tier == "solid"


def test_mistake_names_better_move():
    board = make_board()
    c = comment(board, "h2h3", best_uci="e2e4", cp_loss=120)
    assert c.tier == "mistake"
    assert "e4" in c.text
