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
    pipeline.cluster_users.clear()
    pipeline.next_cluster_number = 1


def setup_function() -> None:
    reset_pipeline()


def test_health_check_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_message_updates_summary_and_recent_messages() -> None:
    response = client.post(
        "/api/messages",
        json={"username": "demo_user", "body": "thsi game sux!!!"},
    )

    assert response.status_code == 200
    message = response.json()["message"]
    assert message["normalised_body"] == "this game sucks"
    assert message["cluster_key"].startswith("game-sucks-")

    summary_response = client.get("/api/summary")
    summary = summary_response.json()

    assert summary_response.status_code == 200
    assert summary["total_messages"] == 1
    assert summary["messages_last_minute"] == 1
    assert summary["unique_users_last_minute"] == 1
    assert summary["recent_messages"][0]["original_body"] == "thsi game sux!!!"
    assert summary["recent_messages"][0]["normalised_body"] == "this game sucks"
    assert "game" in {topic["topic"] for topic in summary["top_topics"]}


def test_near_duplicate_messages_form_a_single_cluster() -> None:
    messages = [
        {"username": "u1", "body": "this game sux"},
        {"username": "u2", "body": "this game suxx"},
        {"username": "u3", "body": "this gaem sucks"},
        {"username": "u4", "body": "audio desync again"},
    ]

    for payload in messages:
        response = client.post("/api/messages", json=payload)
        assert response.status_code == 200

    summary = client.get("/api/summary").json()

    assert summary["total_messages"] == 4
    assert len(summary["spam_clusters"]) == 1

    spam_cluster = summary["spam_clusters"][0]
    assert spam_cluster["count"] == 3
    assert sorted(spam_cluster["users"]) == ["u1", "u2", "u3"]
    assert spam_cluster["text"] == "this game sucks"


def test_simulate_endpoint_adds_messages_within_requested_bounds() -> None:
    response = client.post("/api/simulate?count=5")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "accepted"
    assert len(payload["inserted"]) == 5
    assert payload["summary"]["total_messages"] == 5
    assert payload["summary"]["messages_last_minute"] == 5
