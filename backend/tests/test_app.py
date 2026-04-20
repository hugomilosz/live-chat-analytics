from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


sys.modules["confluent_kafka"] = MagicMock()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_module


pipeline = main_module.pipeline
client = TestClient(main_module.app)


def reset_pipeline() -> None:
    pipeline.raw_messages.clear()
    pipeline.processed_messages.clear()
    pipeline.total_ingested_messages = 0
    pipeline.topic_counter.clear()
    pipeline.topic_group_counts.clear()
    pipeline.cluster_counts.clear()
    pipeline.cluster_examples.clear()
    pipeline.cluster_variants.clear()
    pipeline.cluster_variant_counts.clear()
    pipeline.cluster_users.clear()
    pipeline.topic_group_labels.clear()
    pipeline.topic_group_variants.clear()
    pipeline.topic_group_users.clear()
    pipeline.topic_group_examples.clear()
    pipeline.next_cluster_number = 1
    pipeline.next_topic_group_number = 1
    main_module.subscribers.clear()


@pytest.fixture(autouse=True)
def _setup() -> None:
    reset_pipeline()


def ingest_messages(messages: list[dict[str, str]]) -> None:
    for message in messages:
        pipeline.ingest(message["username"], message["body"])


def test_health_check_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_message_accepts_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_messages = []

    def fake_send_message(message: dict[str, str]) -> None:
        captured_messages.append(message)

    monkeypatch.setattr(main_module, "send_message", fake_send_message)

    response = client.post(
        "/api/messages",
        json={"username": "user1", "body": "hello world"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert captured_messages == [{"username": "user1", "body": "hello world"}]


def test_near_duplicate_messages_form_single_cluster() -> None:
    messages = [
        {"username": "u1", "body": "this game sux"},
        {"username": "u2", "body": "this game suxx"},
        {"username": "u3", "body": "this gaem sucks"},
        {"username": "u4", "body": "this gamd sucks"},
        {"username": "u5", "body": "audio desync again"},
    ]

    ingest_messages(messages)

    summary = client.get("/api/summary").json()

    assert summary["total_ingested_messages"] == 5
    assert summary["total_messages"] == 5
    assert len(summary["spam_clusters"]) == 1

    cluster = summary["spam_clusters"][0]
    assert cluster["count"] == 4
    assert sorted(cluster["users"]) == ["u1", "u2", "u3", "u4"]
    assert cluster["text"] == "this game sucks"


def test_cluster_matching_uses_multiple_examples() -> None:
    messages = [
        {"username": "u1", "body": "this gaem sucks"},
        {"username": "u2", "body": "this game sucks"},
        {"username": "u3", "body": "this game suxx"},
    ]

    ingest_messages(messages)

    summary = client.get("/api/summary").json()

    assert summary["total_ingested_messages"] == 3
    assert summary["total_messages"] == 3
    assert len(summary["spam_clusters"]) == 1
    assert summary["spam_clusters"][0]["count"] == 3
    assert sorted(summary["spam_clusters"][0]["users"]) == ["u1", "u2", "u3"]

    labels = {message["cluster_label"] for message in summary["recent_messages"]}
    assert labels == {"this game sucks"}


def test_topic_groups_capture_shared_subjects_without_merging_clusters() -> None:
    messages = [
        {"username": "u1", "body": "this game is bad"},
        {"username": "u2", "body": "this game is good"},
        {"username": "u3", "body": "yhis game"},
        {"username": "u4", "body": "audio is broken"},
    ]

    ingest_messages(messages)

    summary = client.get("/api/summary").json()

    assert len(summary["spam_clusters"]) == 0

    groups = {group["phrase"]: group for group in summary["topic_groups"]}
    assert "this game" in groups

    group = groups["this game"]
    assert group["count"] == 3
    assert sorted(group["users"]) == ["u1", "u2", "u3"]
    assert len(group["sample_messages"]) == 3


def test_summary_reports_total_ingested_separately_from_retained_messages() -> None:
    messages = [
        {"username": f"user_{index}", "body": f"message number {index}"}
        for index in range(505)
    ]

    ingest_messages(messages)

    summary = client.get("/api/summary").json()

    assert summary["total_ingested_messages"] == 505
    assert summary["total_messages"] == 500


def test_spam_clusters_include_rolling_window_severity() -> None:
    messages = [
        {"username": "u1", "body": "this game sucks"},
        {"username": "u2", "body": "this game sucks!!"},
        {"username": "u3", "body": "this game sux"},
        {"username": "u4", "body": "this gaem sucks"},
        {"username": "u5", "body": "this gamd sucks"},
        {"username": "u6", "body": "this game suxx"},
    ]

    ingest_messages(messages)

    summary = client.get("/api/summary").json()

    assert len(summary["spam_clusters"]) == 1
    cluster = summary["spam_clusters"][0]
    assert cluster["recent_count"] == 6
    assert cluster["recent_unique_users"] == 6
    assert cluster["severity"] == "high"
    assert "6 similar messages in 30s" in cluster["severity_reason"]
    assert "spread across 6 users" in cluster["severity_reason"]


def test_topic_groups_surface_two_word_phrases() -> None:
    messages = [
        {"username": "u1", "body": "stream audio is bad"},
        {"username": "u2", "body": "stream audio is good"},
        {"username": "u3", "body": "stream audio is delayed"},
    ]

    ingest_messages(messages)

    summary = client.get("/api/summary").json()

    assert len(summary["topic_groups"]) == 1

    group = summary["topic_groups"][0]
    assert group["phrase"] == "stream audio"
    assert group["count"] == 3
    assert sorted(group["users"]) == ["u1", "u2", "u3"]
    assert len(group["sample_messages"]) == 3


def test_simulate_endpoint_queues_messages_through_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued_messages = []

    def fake_send_message(message: dict[str, str]) -> None:
        queued_messages.append(message)
        pipeline.ingest(message["username"], message["body"])

    monkeypatch.setattr(main_module, "send_message", fake_send_message)

    response = client.post("/api/simulate?count=5")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "accepted"
    assert len(payload["inserted"]) == 5
    assert len(queued_messages) == 5
    assert pipeline.summary().total_messages == 5


def test_websocket_receives_summary_after_brokered_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_send_message(message: dict[str, str]) -> None:
        pipeline.ingest(message["username"], message["body"])
        main_module.broadcast_event.set()

    monkeypatch.setattr(main_module, "send_message", fake_send_message)

    with TestClient(main_module.app) as client:
        with client.websocket_connect("/ws") as websocket:
            response = client.post(
                "/api/messages",
                json={"username": "demo_user", "body": "thsi game sux!!!"},
            )
            summary = websocket.receive_json()

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert summary["total_messages"] == 1
    assert summary["spam_clusters"] == []
    assert summary["recent_messages"][0]["cluster_label"] == "this game sucks"
