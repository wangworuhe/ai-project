"""Shared storage conventions for synthesized audio files."""

from datetime import datetime
from pathlib import Path

from config.config import Config


def create_timestamped_mp3_path(provider: str) -> tuple[str, str]:
    """Return a unique provider-specific MP3 path and its media URL suffix."""
    if provider not in {"azure", "google"}:
        raise ValueError(f"Unsupported TTS provider: {provider}")

    output_dir = Path(Config.OUTPUT_DIR) / provider
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    filename = f"{timestamp}.mp3"
    path = output_dir / filename
    sequence = 2
    while path.exists():
        filename = f"{timestamp}-{sequence:02d}.mp3"
        path = output_dir / filename
        sequence += 1

    return str(path), f"{provider}/{filename}"
