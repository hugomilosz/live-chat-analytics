from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app, pipeline


client = TestClient(app)


def reset_pipeline() -> None:
    pipeline.raw_messages.clear()
    pipeline.processed_messages.clear()
    pipeline.topic_counter.clear()
    pipeline.cluster_counts.clear()
    pipeline.cluster_examples.clear()
    pipeline.cluster_variants.clear()
    pipeline.cluster_users.clear()
    pipeline.next_cluster_number = 1


def setup_function() -> None:
    reset_pipeline()


def test_health_check_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_message_updates_summary_and_recent_messages() -> None:
    # First, seed the pipeline with the "correct" version
    client.post("/api/messages", json={"username": "user1", "body": "this game sucks"})
    client.post("/api/messages", json={"username": "user2", "body": "this game sucks"})
    client.post("/api/messages", json={"username": "user3", "body": "this game sucks"})

    # Now post the noisy typo version
    response = client.post(
        "/api/messages",
        json={"username": "demo_user", "body": "thsi game sux!!!"},
    )

    assert response.status_code == 200
    message = response.json()["message"]
    
    # Should be grouped under main cluster
    assert message["cluster_label"] == "this game sucks"

def test_near_duplicate_messages_form_a_single_cluster() -> None:
    messages = [
        {"username": "u1", "body": "this game sux"},
        {"username": "u2", "body": "this game suxx"},
        {"username": "u3", "body": "this gaem sucks"},
        {"username": "u4", "body": "this gamd sucks"},
        {"username": "u5", "body": "audio desync again"},
    ]

    for payload in messages:
        response = client.post("/api/messages", json=payload)
        assert response.status_code == 200

    summary = client.get("/api/summary").json()

    assert summary["total_messages"] == 5
    assert len(summary["spam_clusters"]) == 1

    spam_cluster = summary["spam_clusters"][0]
    assert spam_cluster["count"] == 4
    assert sorted(spam_cluster["users"]) == ["u1", "u2", "u3", "u4"]
    assert spam_cluster["text"] == "this game sucks"


def test_cluster_matching_uses_multiple_examples_instead_of_one_label() -> None:
    messages = [
        {"username": "u1", "body": "this gaem sucks"},
        {"username": "u2", "body": "this game sucks"},
        {"username": "u3", "body": "this game suxx"},
    ]

    for payload in messages:
        response = client.post("/api/messages", json=payload)
        assert response.status_code == 200

    summary = client.get("/api/summary").json()

    assert summary["total_messages"] == 3
    assert len(summary["spam_clusters"]) == 1
    assert summary["spam_clusters"][0]["count"] == 3
    assert sorted(summary["spam_clusters"][0]["users"]) == ["u1", "u2", "u3"]
    assert {
        message["cluster_label"] for message in summary["recent_messages"]
    } == {"this game sucks"}


def test_simulate_endpoint_adds_messages_within_requested_bounds() -> None:
    response = client.post("/api/simulate?count=5")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "accepted"
    assert len(payload["inserted"]) == 5
    assert payload["summary"]["total_messages"] == 5
    assert payload["summary"]["messages_last_minute"] == 5
