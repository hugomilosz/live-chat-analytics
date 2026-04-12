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
    "have",
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


def normalise_text(text: str) -> str:
    normalised = unicodedata.normalize("NFKC", text).lower()
    normalised = re.sub(r"(.)\1{2,}", r"\1\1", normalised)
    normalised = re.sub(r"[!?.,]{2,}", " ", normalised)
    normalised = re.sub(r"\s+", " ", normalised).strip()

    words = []
    for word in normalised.split():
        cleaned = re.sub(r"[^a-z0-9']", "", word)
        words.append(ADJACENT_KEY_FIXES.get(cleaned, cleaned))

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
