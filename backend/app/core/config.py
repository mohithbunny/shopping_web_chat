"""App settings. Override any of these with environment variables."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"

# SQLite file lives in backend/shop.db by default.
# To move to Postgres later, set DATABASE_URL=postgresql+psycopg://user:pass@host/db
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'shop.db'}")

# IMPORTANT: set a long random SECRET_KEY in production.
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

LOW_STOCK_THRESHOLD = 5
