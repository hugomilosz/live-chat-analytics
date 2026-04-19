from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from .models import (
    DashboardSummary,
    ProcessedMessage,
    SpamClusterSummary,
    TopicGroupSummary,
    TopicSummary,
)
from .normalisation import (
    cluster_key_for,
    extract_similarity_terms,
    extract_topic_phrase_terms,
    extract_topic_terms,
    normalise_text,
)
from .similarity import fuzzy_jaccard_similarity, token_similarity

DIRECT_TOKEN_MATCH_THRESHOLD = 0.6
SEQUENCE_MATCH_THRESHOLD = 0.82
MIN_TOKEN_OVERLAP_FOR_SEQUENCE_MATCH = 0.5
CLUSTER_VARIANT_LIMIT = 6
TOPIC_GROUP_VARIANT_LIMIT = 6
TOPIC_GROUP_MATCH_THRESHOLD = 0.72


class ChatPipeline:
    def __init__(self) -> None:
        self.raw_messages: deque[dict] = deque(maxlen=500)
        self.processed_messages: deque[ProcessedMessage] = deque(maxlen=500)
        self.total_ingested_messages = 0
        self.topic_counter: Counter[str] = Counter()
        self.topic_group_counts: Counter[str] = Counter()
        self.cluster_counts: Counter[str] = Counter()
        self.cluster_examples: dict[str, str] = {}
        self.cluster_variants: dict[str, deque[str]] = {}
        self.cluster_variant_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.cluster_users: defaultdict[str, set[str]] = defaultdict(set)
        self.topic_group_labels: dict[str, str] = {}
        self.topic_group_variants: dict[str, deque[str]] = {}
        self.topic_group_users: defaultdict[str, set[str]] = defaultdict(set)
        self.topic_group_examples: defaultdict[str, deque[str]] = defaultdict(
            lambda: deque(maxlen=4)
        )
        self.next_cluster_number = 1
        self.next_topic_group_number = 1

    def ingest(self, username: str, body: str) -> ProcessedMessage:
        timestamp = datetime.now(timezone.utc)
        self.total_ingested_messages += 1
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
            cluster_label=self.cluster_examples[cluster_key],
            timestamp=timestamp,
        )

        self.processed_messages.append(processed)
        self.cluster_counts[cluster_key] += 1
        self.cluster_examples.setdefault(cluster_key, normalised_body)
        self.cluster_users[cluster_key].add(username)

        for topic in extract_topic_terms(normalised_body):
            self.topic_counter[topic] += 1
        self.update_topic_groups(username, normalised_body)

        self.sync_cluster_labels(cluster_key)

        return processed

    def assign_cluster(self, normalised_body: str) -> str:
        best_match = None
        best_score = 0.0

        for cluster_key, variants in self.cluster_variants.items():
            score = self.best_variant_match_score(normalised_body, variants)
            if score > best_score:
                best_match = cluster_key
                best_score = score

        if best_match is not None:
            self.record_cluster_variant(best_match, normalised_body)
            self.cluster_examples[best_match] = choose_cluster_example(
                self.cluster_variants[best_match],
                self.cluster_variant_counts[best_match],
            )
            return best_match

        return self.create_cluster(normalised_body)

    def create_cluster(self, normalised_body: str) -> str:
        seed = cluster_key_for(normalised_body).replace(" ", "-")
        cluster_key = f"{seed}-{self.next_cluster_number}"
        self.next_cluster_number += 1
        self.cluster_examples[cluster_key] = normalised_body
        self.cluster_variants[cluster_key] = deque(
            [normalised_body],
            maxlen=CLUSTER_VARIANT_LIMIT,
        )
        self.cluster_variant_counts[cluster_key][normalised_body] += 1
        return cluster_key

    def best_variant_match_score(
        self,
        normalised_body: str,
        variants: deque[str],
    ) -> float:
        best_score = 0.0

        for variant_text in variants:
            token_overlap = fuzzy_jaccard_similarity(
                extract_similarity_terms(normalised_body),
                extract_similarity_terms(variant_text),
            )
            sequence_overlap = SequenceMatcher(
                None,
                normalised_body,
                variant_text,
            ).ratio()

            if not should_merge_messages(token_overlap, sequence_overlap):
                continue

            score = (token_overlap * 0.65) + (sequence_overlap * 0.35)
            if score > best_score:
                best_score = score

        return best_score

    def record_cluster_variant(self, cluster_key: str, normalised_body: str) -> None:
        self.cluster_variant_counts[cluster_key][normalised_body] += 1
        variants = self.cluster_variants.setdefault(
            cluster_key,
            deque(maxlen=CLUSTER_VARIANT_LIMIT),
        )
        if normalised_body in variants:
            return
        variants.append(normalised_body)

    def sync_cluster_labels(self, cluster_key: str) -> None:
        cluster_label = self.cluster_examples[cluster_key]
        for message in self.processed_messages:
            if message.cluster_key == cluster_key:
                message.cluster_label = cluster_label

    def update_topic_groups(self, username: str, normalised_body: str) -> None:
        topic_phrase = derive_topic_phrase(normalised_body)
        if topic_phrase is None:
            return

        topic_group_key = self.assign_topic_group(topic_phrase)
        self.topic_group_counts[topic_group_key] += 1
        self.topic_group_users[topic_group_key].add(username)

        examples = self.topic_group_examples[topic_group_key]
        if normalised_body not in examples:
            examples.append(normalised_body)

    def assign_topic_group(self, topic_phrase: str) -> str:
        best_match = None
        best_score = 0.0

        for topic_group_key, variants in self.topic_group_variants.items():
            score = best_topic_group_match_score(topic_phrase, variants)
            if score > best_score:
                best_match = topic_group_key
                best_score = score

        if best_match is not None:
            variants = self.topic_group_variants[best_match]
            if topic_phrase not in variants:
                variants.append(topic_phrase)
            self.topic_group_labels[best_match] = choose_cluster_example(variants)
            return best_match

        topic_group_key = f"topic-{self.next_topic_group_number}"
        self.next_topic_group_number += 1
        self.topic_group_labels[topic_group_key] = topic_phrase
        self.topic_group_variants[topic_group_key] = deque(
            [topic_phrase],
            maxlen=TOPIC_GROUP_VARIANT_LIMIT,
        )
        return topic_group_key

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

        topic_groups = [
            TopicGroupSummary(
                phrase=self.topic_group_labels[key],
                count=count,
                users=sorted(self.topic_group_users[key]),
                sample_messages=list(self.topic_group_examples[key]),
            )
            for key, count in self.topic_group_counts.most_common(5)
            if count >= 2
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
            total_ingested_messages=self.total_ingested_messages,
            total_messages=len(self.processed_messages),
            messages_last_minute=len(recent),
            unique_users_last_minute=len({message.username for message in recent}),
            top_topics=top_topics,
            topic_groups=topic_groups,
            spam_clusters=spam_clusters,
            recent_messages=list(reversed(list(self.processed_messages)[-12:])),
        )


def should_merge_messages(token_overlap: float, sequence_overlap: float) -> bool:
    return token_overlap >= DIRECT_TOKEN_MATCH_THRESHOLD or (
        token_overlap >= MIN_TOKEN_OVERLAP_FOR_SEQUENCE_MATCH
        and sequence_overlap >= SEQUENCE_MATCH_THRESHOLD
    )


def choose_cluster_example(
    variants: deque[str],
    variant_counts: Counter[str] | None = None,
) -> str:
    variant_counts = variant_counts or Counter()
    best_variant = ""
    best_score = float("-inf")

    for candidate in variants:
        centrality_score = sum(
            raw_message_similarity(candidate, other)
            for other in variants
            if other != candidate
        )
        frequency_score = variant_counts.get(candidate, 0) * 0.35
        readability_score = -repeated_letter_score(candidate)
        score = centrality_score + frequency_score + (readability_score * 0.05)

        if score > best_score:
            best_variant = candidate
            best_score = score

    return best_variant or variants[0]


def raw_message_similarity(left_text: str, right_text: str) -> float:
    token_overlap = fuzzy_jaccard_similarity(
        extract_similarity_terms(left_text),
        extract_similarity_terms(right_text),
    )
    sequence_overlap = SequenceMatcher(None, left_text, right_text).ratio()
    return (token_overlap * 0.65) + (sequence_overlap * 0.35)


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


def derive_topic_phrase(text: str) -> str | None:
    terms = extract_topic_phrase_terms(text)
    if len(terms) < 2:
        return None
    return " ".join(terms[:2])


def best_topic_group_match_score(topic_phrase: str, variants: deque[str]) -> float:
    best_score = 0.0

    for variant in variants:
        score = topic_phrase_similarity(topic_phrase, variant)
        if score > best_score and score >= TOPIC_GROUP_MATCH_THRESHOLD:
            best_score = score

    return best_score


def topic_phrase_similarity(left_phrase: str, right_phrase: str) -> float:
    left_tokens = left_phrase.split()
    right_tokens = right_phrase.split()

    if len(left_tokens) == len(right_tokens) == 2:
        first_score = token_similarity(left_tokens[0], right_tokens[0])
        second_score = token_similarity(left_tokens[1], right_tokens[1])
        return (first_score * 0.45) + (second_score * 0.55)

    return raw_message_similarity(left_phrase, right_phrase)
