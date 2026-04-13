from __future__ import annotations

import re
import unicodedata


ADJACENT_KEY_FIXES = {
    "teh": "the",
    "thsi": "this",
    "waht": "what",
    "recieve": "receive",
    "adn": "and",
    "wierd": "weird",
    "becuase": "because",
    "sux": "sucks",
    "pls": "please",
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "is",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "your",
    "just",
    "from",
    "they",
    "about",
    "what",
    "when",
    "were",
    "been",
    "into",
}

LINKING_WORDS = {
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "am",
}

TOPIC_LEADING_WORDS = {
    "this",
    "that",
    "these",
    "those",
    "my",
    "your",
    "our",
    "their",
    "his",
    "her",
    "its",
    "yhis",
}


def normalise_text(text: str) -> str:
    normalised = unicodedata.normalize("NFKC", text).lower()
    normalised = re.sub(r"(.)\1{2,}", r"\1\1", normalised)
    normalised = re.sub(r"[!?.,]{2,}", " ", normalised)
    normalised = re.sub(r"\s+", " ", normalised).strip()

    words = []
    for word in normalised.split():
        cleaned = re.sub(r"[^a-z0-9']", "", word)
        words.append(resolve_known_variant(cleaned))

    return " ".join(part for part in words if part)


def cluster_key_for(text: str) -> str:
    words = [word for word in text.split() if word not in STOPWORDS]
    if not words:
        return "misc"
    return " ".join(words[:4])


def extract_similarity_terms(text: str) -> set[str]:
    return {
        word
        for word in text.split()
        if len(word) > 2 and word not in STOPWORDS and not word.isdigit()
    }


def extract_topic_terms(text: str) -> list[str]:
    return [
        word
        for word in text.split()
        if len(word) > 3 and word not in STOPWORDS and not word.isdigit()
    ]


def extract_topic_phrase_terms(text: str) -> list[str]:
    tokens = [word for word in text.split() if not word.isdigit()]
    if len(tokens) < 2:
        return []

    first, second = tokens[0], tokens[1]
    if first in TOPIC_LEADING_WORDS and second not in STOPWORDS and len(second) > 2:
        return [first, second]

    if first not in LINKING_WORDS and second not in STOPWORDS and len(second) > 2:
        return [first, second]

    if (
        len(tokens) >= 3
        and first not in LINKING_WORDS
        and second in LINKING_WORDS
        and len(tokens[2]) > 2
        and tokens[2] not in STOPWORDS
    ):
        return [first, tokens[2]]

    content_tokens = [
        word for word in tokens if len(word) > 2 and word not in STOPWORDS
    ]
    return content_tokens[:2]


def resolve_known_variant(word: str) -> str:
    if word in ADJACENT_KEY_FIXES:
        return ADJACENT_KEY_FIXES[word]

    collapsed_word = re.sub(r"([a-z])\1+", r"\1", word)
    return ADJACENT_KEY_FIXES.get(collapsed_word, word)
