from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.replay import build_replay_schedule, load_replay_messages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay a chat log through the Chat Analyser API.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a JSON, JSONL, NDJSON, or CSV chat log.",
    )
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8000",
        help="Base URL for the backend API.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=5.0,
        help="Replay speed multiplier. Use 1 for real-time or 10 for 10x speed.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of messages to replay.",
    )
    parser.add_argument(
        "--username-field",
        default="username",
        help="Field name for usernames in the input file.",
    )
    parser.add_argument(
        "--body-field",
        default="body",
        help="Field name for message text in the input file.",
    )
    parser.add_argument(
        "--timestamp-field",
        default="timestamp",
        help="Field name for timestamps in the input file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    messages = load_replay_messages(
        args.path,
        username_field=args.username_field,
        body_field=args.body_field,
        timestamp_field=args.timestamp_field,
    )
    if args.limit is not None:
        messages = messages[: max(args.limit, 0)]

    schedule = build_replay_schedule(messages, speed=args.speed)
    if not schedule:
        print("No replay messages found.")
        return 0

    start_time = time.monotonic()
    endpoint = f"{args.api_base.rstrip('/')}/api/messages"

    print(
        f"Replaying {len(schedule)} messages from {args.path} at {args.speed}x speed"
    )

    for index, (delay_seconds, message) in enumerate(schedule, start=1):
        sleep_seconds = delay_seconds - (time.monotonic() - start_time)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        payload = json.dumps(
            {"username": message.username, "body": message.body}
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request) as response:
                response.read()
        except urllib.error.URLError as error:
            print(f"Replay failed on message {index}: {error}", file=sys.stderr)
            return 1

        print(
            f"[{index:03d}/{len(schedule):03d}] {message.username}: {message.body}"
        )

    print("Replay finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
