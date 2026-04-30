// Chess teaching bot — front-end glue.
//
// chessboard.js handles drag-and-drop and rendering. We treat the server as
// the source of truth: every dropped move is POSTed, and we re-set the board
// to whatever FEN the server returns (which already includes the bot's reply).

(function () {
  const game = window.GAME;
  const $status = document.getElementById("status");
  const $comments = document.getElementById("comments");
  const $resign = document.getElementById("resign");
  const $promo = document.getElementById("promo-dialog");

  let board = null;
  let busy = false;
  let pendingPromotion = null;

  function setStatus(text) {
    $status.textContent = text;
  }

  function appendComment(ply, san, tier, text) {
    const li = document.createElement("li");
    li.className = "comment " + (tier || "bot");
    li.innerHTML =
      '<span class="ply">' + ply + '.</span>' +
      '<span class="san"></span>' +
      '<span class="text"></span>';
    li.querySelector(".san").textContent = san || "";
    li.querySelector(".text").textContent = text || "";
    $comments.appendChild(li);
    $comments.scrollTop = $comments.scrollHeight;
  }

  async function askPromotion() {
    return new Promise((resolve) => {
      const onClose = () => {
        $promo.removeEventListener("close", onClose);
        resolve($promo.returnValue || "q");
      };
      $promo.addEventListener("close", onClose);
      $promo.showModal();
    });
  }

  async function postMove(from, to, promotion) {
    const res = await fetch(`/game/${game.id}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from, to, promotion }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  function isPromotion(source, target, piece) {
    // piece is e.g. "wP" or "bP". Pawn reaching last rank => promotion.
    if (piece[1] !== "P") return false;
    const targetRank = target[1];
    return (piece[0] === "w" && targetRank === "8") || (piece[0] === "b" && targetRank === "1");
  }

  async function onDrop(source, target, piece) {
    if (game.over || busy) return "snapback";
    if (source === target) return "snapback";

    let promotion = null;
    if (isPromotion(source, target, piece)) {
      promotion = await askPromotion();
    }

    busy = true;
    setStatus("Thinking…");
    let data;
    try {
      data = await postMove(source, target, promotion);
    } catch (err) {
      busy = false;
      setStatus(err.message);
      return "snapback";
    }

    const lastPlyIndex = $comments.children.length;
    appendComment(lastPlyIndex + 1, data.your_san, data.your_tier, data.your_commentary);
    if (data.bot_san) {
      appendComment(lastPlyIndex + 2, data.bot_san, "bot", data.bot_note);
    }

    board.position(data.fen, true);

    if (data.game_over) {
      game.over = true;
      $resign.disabled = true;
      setStatus("Game over: " + data.result);
    } else {
      setStatus("Your move.");
    }
    busy = false;
  }

  function onDragStart(source, piece) {
    if (game.over || busy) return false;
    // Only let the human drag their own pieces.
    const myColor = game.playerColor === "w" ? "w" : "b";
    if (piece[0] !== myColor) return false;
  }

  document.addEventListener("DOMContentLoaded", function () {
    board = Chessboard("board", {
      draggable: true,
      position: game.fen,
      orientation: game.playerColor === "w" ? "white" : "black",
      pieceTheme: "https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/img/chesspieces/wikipedia/{piece}.png",
      onDragStart: onDragStart,
      onDrop: onDrop,
    });

    window.addEventListener("resize", () => board && board.resize());

    $resign.addEventListener("click", async function () {
      if (game.over) return;
      if (!confirm("Resign this game?")) return;
      const res = await fetch(`/game/${game.id}/resign`, { method: "POST" });
      const data = await res.json();
      game.over = true;
      $resign.disabled = true;
      setStatus("Game over: " + data.result);
    });
  });
})();
