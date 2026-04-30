import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/chess.db")
ENGINE_PATH = os.getenv("ENGINE_PATH", "/usr/games/stockfish")
PLAYER_NAME = os.getenv("PLAYER_NAME", "you")
START_ELO = int(os.getenv("START_ELO", "1000"))
ENGINE_THINK_SECONDS = float(os.getenv("ENGINE_THINK_SECONDS", "0.3"))

DATA_DIR = "/data"
