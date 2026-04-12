from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.similarity import fuzzy_jaccard_similarity, token_similarity


def test_token_similarity_detects_keyboard_adjacent_substitution() -> None:
    assert token_similarity("game", "gamd") >= 0.9


def test_token_similarity_detects_transposition() -> None:
    assert token_similarity("game", "gaem") >= 0.89


def test_token_similarity_handles_repeated_letters_without_rewriting_words() -> None:
    assert token_similarity("missile", "misssile") >= 0.9
    assert token_similarity("missile", "miller") < 0.74


def test_fuzzy_jaccard_similarity_matches_typo_variants() -> None:
    score = fuzzy_jaccard_similarity({"game", "sucks"}, {"gamd", "sucks"})

    assert score >= 0.9
