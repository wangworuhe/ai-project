import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
DATABASE_DIR = STORAGE_DIR / "database"
LOG_DIR = STORAGE_DIR / "logs"
UPLOAD_DIR = STORAGE_DIR / "uploads"
OUTPUT_DIR = STORAGE_DIR / "outputs"
AZURE_OUTPUT_DIR = OUTPUT_DIR / "azure"
GOOGLE_OUTPUT_DIR = OUTPUT_DIR / "google"
GRAMMAR_DIR = STORAGE_DIR / "grammar"
GRAMMAR_EXPORT_DIR = GRAMMAR_DIR / "exports"
GRAMMAR_BOOK_PAGES_DIR = GRAMMAR_DIR / "book-pages"

# Load project-local secrets for development. Existing system environment
# variables take precedence, which keeps deployment configuration unchanged.
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_PATH = Path(
    os.environ.get("AI_PROJECT_DATABASE_PATH", DATABASE_DIR / "database.db")
).expanduser().resolve()
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

for directory in (
    DATABASE_DIR, LOG_DIR, UPLOAD_DIR, OUTPUT_DIR, AZURE_OUTPUT_DIR,
    GOOGLE_OUTPUT_DIR, GRAMMAR_DIR, GRAMMAR_EXPORT_DIR, GRAMMAR_BOOK_PAGES_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)

class Config:
    PROJECT_ROOT = str(PROJECT_ROOT)
    STORAGE_DIR = str(STORAGE_DIR)
    DATABASE_PATH = str(DATABASE_PATH)
    LOG_FILE = str(LOG_DIR / "app.log")
    UPLOAD_DIR = str(UPLOAD_DIR)
    OUTPUT_DIR = str(OUTPUT_DIR)
    AZURE_OUTPUT_DIR = str(AZURE_OUTPUT_DIR)
    GOOGLE_OUTPUT_DIR = str(GOOGLE_OUTPUT_DIR)
    GRAMMAR_DIR = str(GRAMMAR_DIR)
    GRAMMAR_EXPORT_DIR = str(GRAMMAR_EXPORT_DIR)
    GRAMMAR_BOOK_PAGES_DIR = str(GRAMMAR_BOOK_PAGES_DIR)

    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GRAMMAR_DRAFT_PROFILE = os.environ.get("GRAMMAR_DRAFT_PROFILE", "default")
    MECHA_BASE_URL = os.environ.get("MECHA_BASE_URL", "").rstrip("/")
    MECHA_API_KEY = os.environ.get("MECHA_API_KEY", "")
    GRAMMAR_AI_REVIEW_WORKER = os.environ.get(
        "GRAMMAR_AI_REVIEW_WORKER", "grammar-mistake-explainer"
    )
    GRAMMAR_AI_REVIEW_BATCH_SIZE = int(os.environ.get("GRAMMAR_AI_REVIEW_BATCH_SIZE", "20"))
    GRAMMAR_AI_REVIEW_HTTP_TIMEOUT = float(os.environ.get("GRAMMAR_AI_REVIEW_HTTP_TIMEOUT", "15"))
    GRAMMAR_AI_REVIEW_RESULT_MAX_BYTES = int(os.environ.get("GRAMMAR_AI_REVIEW_RESULT_MAX_BYTES", "1048576"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # 通过环境变量覆盖
