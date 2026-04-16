from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


# Mock Kafka
sys.modules["confluent_kafka"] = MagicMock()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app, pipeline

client = TestClient(app)

# Helper functions
def reset_pipeline() -> None:
    pipeline.raw_messages.clear()
    pipeline.processed_messages.clear()
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

@pytest.fixture(autouse=True)
def _setup():
    reset_pipeline()

def ingest_messages(messages):
    """Simulate Kafka consumer by directly feeding pipeline."""
    for m in messages:
        pipeline.ingest(m["username"], m["body"])

def test_health_check_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_post_message_accepts_messages() -> None:
    response = client.post(
        "/api/messages",
        json={"username": "user1", "body": "hello world"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}

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

    assert summary["total_messages"] == 3
    assert len(summary["spam_clusters"]) == 1
    assert summary["spam_clusters"][0]["count"] == 3
    assert sorted(summary["spam_clusters"][0]["users"]) == ["u1", "u2", "u3"]

    labels = {m["cluster_label"] for m in summary["recent_messages"]}
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

    groups = {g["phrase"]: g for g in summary["topic_groups"]}
    assert "this game" in groups

    group = groups["this game"]
    assert group["count"] == 3
    assert sorted(group["users"]) == ["u1", "u2", "u3"]
    assert len(group["sample_messages"]) == 3

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

def test_simulate_endpoint_respects_bounds() -> None:
    response = client.post("/api/simulate?count=5")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "accepted"
    assert len(payload["inserted"]) == 5
    assert payload["summary"]["total_messages"] == 5
    assert payload["summary"]["messages_last_minute"] == 5