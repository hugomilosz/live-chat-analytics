from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone

from .models import DashboardSummary, ProcessedMessage, SpamClusterSummary, TopicSummary
from .normalisation import cluster_key_for, extract_topic_terms, normalise_text


class ChatPipeline:
    def __init__(self) -> None:
        self.raw_messages: deque[dict] = deque(maxlen=500)
        self.processed_messages: deque[ProcessedMessage] = deque(maxlen=500)
        self.topic_counter: Counter[str] = Counter()
        self.cluster_counts: Counter[str] = Counter()
        self.cluster_examples: dict[str, str] = {}
        self.cluster_users: defaultdict[str, set[str]] = defaultdict(set)

    def ingest(self, username: str, body: str) -> ProcessedMessage:
        timestamp = datetime.now(timezone.utc)
        self.raw_messages.append(
            {
                "username": username,
                "body": body,
                "timestamp": timestamp,
            }
        )

        normalised_body = normalise_text(body)
        cluster_key = cluster_key_for(normalised_body)
        processed = ProcessedMessage(
            username=username,
            original_body=body,
            normalised_body=normalised_body,
            cluster_key=cluster_key,
            timestamp=timestamp,
        )

        self.processed_messages.append(processed)
        self.cluster_counts[cluster_key] += 1
        self.cluster_examples.setdefault(cluster_key, normalised_body)
        self.cluster_users[cluster_key].add(username)

        for topic in extract_topic_terms(normalised_body):
            self.topic_counter[topic] += 1

        return processed

    def summary(self) -> DashboardSummary:
        one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
        recent = [
            message
            for message in self.processed_messages
            if message.timestamp >= one_minute_ago
        ]

        top_topics = [
            TopicSummary(topic=topic, count=count)
            for topic, count in self.topic_counter.most_common(6)
        ]

        spam_clusters = [
            SpamClusterSummary(
                text=self.cluster_examples[key],
                count=count,
                users=sorted(self.cluster_users[key]),
            )
            for key, count in self.cluster_counts.most_common(5)
            if count >= 2
        ]

        return DashboardSummary(
            total_messages=len(self.processed_messages),
            messages_last_minute=len(recent),
            unique_users_last_minute=len({message.username for message in recent}),
            top_topics=top_topics,
            spam_clusters=spam_clusters,
            recent_messages=list(reversed(list(self.processed_messages)[-12:])),
        )
