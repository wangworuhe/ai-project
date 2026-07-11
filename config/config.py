import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
DATABASE_DIR = STORAGE_DIR / "database"
LOG_DIR = STORAGE_DIR / "logs"
UPLOAD_DIR = STORAGE_DIR / "uploads"
OUTPUT_DIR = STORAGE_DIR / "outputs"

# Load project-local secrets for development. Existing system environment
# variables take precedence, which keeps deployment configuration unchanged.
load_dotenv(PROJECT_ROOT / ".env")

for directory in (DATABASE_DIR, LOG_DIR, UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

class Config:
    PROJECT_ROOT = str(PROJECT_ROOT)
    STORAGE_DIR = str(STORAGE_DIR)
    DATABASE_PATH = str(DATABASE_DIR / "database.db")
    LOG_FILE = str(LOG_DIR / "app.log")
    UPLOAD_DIR = str(UPLOAD_DIR)
    OUTPUT_DIR = str(OUTPUT_DIR)

    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # 通过环境变量覆盖
