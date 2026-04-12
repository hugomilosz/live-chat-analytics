from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from .models import DashboardSummary, ProcessedMessage, SpamClusterSummary, TopicSummary
from .normalisation import (
    cluster_key_for,
    extract_similarity_terms,
    extract_topic_terms,
    normalise_text,
)

DIRECT_TOKEN_MATCH_THRESHOLD = 0.6
SEQUENCE_MATCH_THRESHOLD = 0.82
MIN_TOKEN_OVERLAP_FOR_SEQUENCE_MATCH = 0.3


class ChatPipeline:
    def __init__(self) -> None:
        self.raw_messages: deque[dict] = deque(maxlen=500)
        self.processed_messages: deque[ProcessedMessage] = deque(maxlen=500)
        self.topic_counter: Counter[str] = Counter()
        self.cluster_counts: Counter[str] = Counter()
        self.cluster_examples: dict[str, str] = {}
        self.cluster_users: defaultdict[str, set[str]] = defaultdict(set)
        self.next_cluster_number = 1

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
        cluster_key = self.assign_cluster(normalised_body)
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

    def assign_cluster(self, normalised_body: str) -> str:
        best_match = None
        best_score = 0.0

        for cluster_key, example_text in self.cluster_examples.items():
            token_overlap = jaccard_similarity(
                extract_similarity_terms(normalised_body),
                extract_similarity_terms(example_text),
            )
            sequence_overlap = SequenceMatcher(
                None,
                normalised_body,
                example_text,
            ).ratio()

            if not should_merge_messages(token_overlap, sequence_overlap):
                continue

            score = (token_overlap * 0.65) + (sequence_overlap * 0.35)
            if score > best_score:
                best_match = cluster_key
                best_score = score

        if best_match is not None:
            current_example = self.cluster_examples[best_match]
            self.cluster_examples[best_match] = choose_cluster_example(
                current_example,
                normalised_body,
            )
            return best_match

        return self.create_cluster(normalised_body)

    def create_cluster(self, normalised_body: str) -> str:
        seed = cluster_key_for(normalised_body).replace(" ", "-")
        cluster_key = f"{seed}-{self.next_cluster_number}"
        self.next_cluster_number += 1
        self.cluster_examples[cluster_key] = normalised_body
        return cluster_key

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


def should_merge_messages(token_overlap: float, sequence_overlap: float) -> bool:
    return token_overlap >= DIRECT_TOKEN_MATCH_THRESHOLD or (
        token_overlap >= MIN_TOKEN_OVERLAP_FOR_SEQUENCE_MATCH
        and sequence_overlap >= SEQUENCE_MATCH_THRESHOLD
    )


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def choose_cluster_example(current: str, candidate: str) -> str:
    # Prefer cleaner labels for the dashboard when two messages belong to the
    # same cluster.
    current_score = repeated_letter_score(current)
    candidate_score = repeated_letter_score(candidate)

    if candidate_score < current_score:
        return candidate
    if candidate_score == current_score and len(candidate) > len(current):
        return candidate
    return current


def repeated_letter_score(text: str) -> int:
    return sum(max(len(run) - 1, 0) for run in find_repeated_runs(text))


def find_repeated_runs(text: str) -> list[str]:
    runs = []
    current_run = text[:1]

    for character in text[1:]:
        if current_run and character == current_run[-1]:
            current_run += character
            continue
        runs.append(current_run)
        current_run = character

    if current_run:
        runs.append(current_run)

    return runs
