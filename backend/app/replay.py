from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {".json", ".jsonl", ".ndjson", ".csv"}


@dataclass(frozen=True)
class ReplayMessage:
    username: str
    body: str
    timestamp: float | None = None


def load_replay_messages(
    path: str | Path,
    username_field: str = "username",
    body_field: str = "body",
    timestamp_field: str = "timestamp",
) -> list[ReplayMessage]:
    replay_path = Path(path)
    suffix = replay_path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported replay file type '{suffix}'. Use one of: {supported}")

    if suffix == ".json":
        raw_rows = load_json_rows(replay_path)
    elif suffix in {".jsonl", ".ndjson"}:
        raw_rows = load_jsonl_rows(replay_path)
    else:
        raw_rows = load_csv_rows(replay_path)

    return [
        normalise_replay_row(row, username_field, body_field, timestamp_field)
        for row in raw_rows
    ]


def build_replay_schedule(
    messages: list[ReplayMessage],
    speed: float = 1.0,
) -> list[tuple[float, ReplayMessage]]:
    if speed <= 0:
        raise ValueError("Replay speed must be greater than 0.")

    if not messages:
        return []

    timestamps = [message.timestamp for message in messages if message.timestamp is not None]
    if len(timestamps) != len(messages):
        return [(0.0, message) for message in messages]

    first_timestamp = timestamps[0]
    schedule = []
    for message in messages:
        delay_seconds = max((message.timestamp - first_timestamp) / speed, 0.0)
        schedule.append((delay_seconds, message))
    return schedule


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [ensure_mapping(row) for row in payload]
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        return [ensure_mapping(row) for row in payload["messages"]]
    raise ValueError("JSON replay files must contain a list or a {'messages': [...]} object.")


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(ensure_mapping(json.loads(stripped)))
    return rows


def load_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def ensure_mapping(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("Each replay entry must be an object/dictionary.")
    return row


def normalise_replay_row(
    row: dict[str, Any],
    username_field: str,
    body_field: str,
    timestamp_field: str,
) -> ReplayMessage:
    username = str(row.get(username_field, "")).strip()
    body = str(row.get(body_field, "")).strip()

    if not username:
        raise ValueError(f"Replay row is missing username field '{username_field}'.")
    if not body:
        raise ValueError(f"Replay row is missing body field '{body_field}'.")

    timestamp_value = row.get(timestamp_field)
    timestamp = parse_timestamp(timestamp_value)
    return ReplayMessage(username=username, body=body, timestamp=timestamp)


def parse_timestamp(value: Any) -> float | None:
    if value in {None, ""}:
        return None

    if isinstance(value, (int, float)):
        numeric_value = float(value)
        return numeric_value / 1000 if numeric_value > 10_000_000_000 else numeric_value

    if not isinstance(value, str):
        raise ValueError(f"Unsupported timestamp value: {value!r}")

    stripped = value.strip()
    if not stripped:
        return None

    try:
        numeric_value = float(stripped)
        return numeric_value / 1000 if numeric_value > 10_000_000_000 else numeric_value
    except ValueError:
        pass

    iso_value = stripped.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(iso_value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()
