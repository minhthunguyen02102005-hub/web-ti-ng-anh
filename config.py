import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

# Dùng database trên mạng (Neon) nếu có DATABASE_URL, không thì dùng SQLite ở máy
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "dev-secret-key-change-later"
    )

    SQLALCHEMY_DATABASE_URI = (
        DATABASE_URL
        or "sqlite:///" + str(BASE_DIR / "instance" / "app.db")
    )

    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
