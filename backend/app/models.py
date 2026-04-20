from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class ChatMessageIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=40)
    body: str = Field(..., min_length=1, max_length=400)


class ProcessedMessage(BaseModel):
    username: str
    original_body: str
    normalised_body: str
    cluster_key: str
    cluster_label: str
    timestamp: datetime


class TopicSummary(BaseModel):
    topic: str
    count: int


class SpamClusterSummary(BaseModel):
    text: str
    count: int
    users: List[str]
    recent_count: int
    recent_unique_users: int
    severity: str
    severity_reason: str


class TopicGroupSummary(BaseModel):
    phrase: str
    count: int
    users: List[str]
    sample_messages: List[str]


class DashboardSummary(BaseModel):
    total_ingested_messages: int
    total_messages: int
    messages_last_minute: int
    unique_users_last_minute: int
    top_topics: List[TopicSummary]
    topic_groups: List[TopicGroupSummary]
    spam_clusters: List[SpamClusterSummary]
    recent_messages: List[ProcessedMessage]
