from __future__ import annotations

import os
from pathlib import Path


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def csv_env(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [value.strip() for value in raw_value.split(",") if value.strip()]


load_env_file()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
KAFKA_TOPIC_CHAT_RAW = os.getenv("KAFKA_TOPIC_CHAT_RAW", "chat_raw")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "chat-analyser")
KAFKA_AUTO_OFFSET_RESET = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")
CORS_ORIGINS = csv_env("CHAT_ANALYSER_CORS_ORIGINS", "http://localhost:5173")
SUMMARY_BROADCAST_DEBOUNCE_SECONDS = float(
    os.getenv("CHAT_ANALYSER_BROADCAST_DEBOUNCE_SECONDS", "0.2")
)
CHAT_ANALYSER_API_BASE = os.getenv("CHAT_ANALYSER_API_BASE", "http://127.0.0.1:8000")
