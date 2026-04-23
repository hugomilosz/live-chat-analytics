from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.replay import build_replay_schedule, load_replay_messages
from replay_chat import summarise_replay


def test_load_replay_messages_reads_demo_jsonl() -> None:
    messages = load_replay_messages("backend/data/demo_chat_replay.jsonl")

    assert len(messages) == 15
    assert messages[0].username == "pixelfox"
    assert messages[0].body == "this game sux"
    assert messages[0].timestamp is not None


def test_build_replay_schedule_uses_relative_timestamps() -> None:
    messages = load_replay_messages("backend/data/demo_chat_replay.jsonl")[:3]

    schedule = build_replay_schedule(messages, speed=2.0)

    assert schedule[0][0] == 0.0
    assert 0.49 <= schedule[1][0] <= 0.51
    assert 0.99 <= schedule[2][0] <= 1.01


def test_build_replay_schedule_falls_back_to_immediate_replay_without_timestamps(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "replay_fixture.csv"
    fixture_path.write_text(
        "username,body\nalice,hello there\nbob,this game sux\n",
        encoding="utf-8",
    )

    messages = load_replay_messages(fixture_path)
    schedule = build_replay_schedule(messages, speed=5.0)

    assert [delay for delay, _message in schedule] == [0.0, 0.0]


def test_build_replay_schedule_can_ignore_source_timestamps() -> None:
    messages = load_replay_messages("backend/data/demo_chat_replay.jsonl")[:3]

    schedule = build_replay_schedule(messages, speed=1.0, preserve_timing=False)

    assert [delay for delay, _message in schedule] == [0.0, 0.0, 0.0]


def test_summarise_replay_reports_average_throughput() -> None:
    stats = summarise_replay(sent_messages=250, duration_seconds=2.5)

    assert stats.sent_messages == 250
    assert stats.duration_seconds == 2.5
    assert stats.average_messages_per_second == pytest.approx(100.0)
