from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.config import CHAT_ANALYSER_API_BASE
from app.replay import build_replay_schedule, load_replay_messages


@dataclass(frozen=True)
class ReplayStats:
    sent_messages: int
    duration_seconds: float

    @property
    def average_messages_per_second(self) -> float:
        if self.duration_seconds <= 0:
            return float(self.sent_messages)
        return self.sent_messages / self.duration_seconds


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
        default=CHAT_ANALYSER_API_BASE,
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
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Ignore source timestamps and send messages as fast as possible.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-message output and print only replay summary metrics.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent HTTP workers to use in benchmark mode.",
    )
    return parser.parse_args()


def summarise_replay(sent_messages: int, duration_seconds: float) -> ReplayStats:
    return ReplayStats(
        sent_messages=sent_messages,
        duration_seconds=max(duration_seconds, 0.0),
    )


def print_replay_summary(stats: ReplayStats) -> None:
    print(
        "Replay finished: "
        f"{stats.sent_messages} messages in {stats.duration_seconds:.2f}s "
        f"({stats.average_messages_per_second:.1f} msgs/sec average)"
    )


def post_replay_message(endpoint: str, message) -> None:
    payload = json.dumps(
        {"username": message.username, "body": message.body}
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        response.read()


def run_benchmark_replay(
    endpoint: str,
    messages,
    *,
    concurrency: int,
) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(post_replay_message, endpoint, message)
            for message in messages
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def main() -> int:
    args = parse_args()
    if args.concurrency < 1:
        print("--concurrency must be at least 1.", file=sys.stderr)
        return 1

    messages = load_replay_messages(
        args.path,
        username_field=args.username_field,
        body_field=args.body_field,
        timestamp_field=args.timestamp_field,
    )
    if args.limit is not None:
        messages = messages[: max(args.limit, 0)]

    schedule = build_replay_schedule(
        messages,
        speed=args.speed,
        preserve_timing=not args.benchmark,
    )
    if not schedule:
        print("No replay messages found.")
        return 0

    start_time = time.monotonic()
    endpoint = f"{args.api_base.rstrip('/')}/api/messages"
    mode_label = "benchmark mode" if args.benchmark else f"{args.speed}x speed"

    print(f"Replaying {len(schedule)} messages from {args.path} in {mode_label}")

    try:
        if args.benchmark and args.concurrency > 1:
            run_benchmark_replay(
                endpoint,
                [message for _delay_seconds, message in schedule],
                concurrency=args.concurrency,
            )
        else:
            for index, (delay_seconds, message) in enumerate(schedule, start=1):
                sleep_seconds = delay_seconds - (time.monotonic() - start_time)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

                post_replay_message(endpoint, message)

                if not args.quiet:
                    print(
                        f"[{index:03d}/{len(schedule):03d}] {message.username}: {message.body}"
                    )
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        print(
            f"Replay failed: HTTP {error.code} {error.reason}. Response: {details}",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as error:
        print(f"Replay failed: {error}", file=sys.stderr)
        return 1

    stats = summarise_replay(
        sent_messages=len(schedule),
        duration_seconds=time.monotonic() - start_time,
    )
    print_replay_summary(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
