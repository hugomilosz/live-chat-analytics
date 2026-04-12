from __future__ import annotations

from difflib import SequenceMatcher

TOKEN_MATCH_THRESHOLD = 0.74

# Omly QWERTY keyboard for now
KEYBOARD_LAYOUTS = (
    (
        ("qwertyuiop", 0.50),
        ("asdfghjkl", 0.75),
        ("zxcvbnm", 1.25),
    ),
)


def fuzzy_jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0

    right_tokens = sorted(right, key=len, reverse=True)
    used_right_indexes: set[int] = set()
    matched_score = 0.0

    for left_token in sorted(left, key=len, reverse=True):
        best_score = 0.0
        best_index = None

        for index, right_token in enumerate(right_tokens):
            if index in used_right_indexes:
                continue

            score = token_similarity(left_token, right_token)
            if score > best_score:
                best_score = score
                best_index = index

        if best_index is None or best_score < TOKEN_MATCH_THRESHOLD:
            continue

        used_right_indexes.add(best_index)
        matched_score += best_score

    return matched_score / (len(left) + len(right) - matched_score)


def token_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0

    collapsed_left = collapse_repeated_letters(left)
    collapsed_right = collapse_repeated_letters(right)
    if collapsed_left == collapsed_right:
        return 0.94

    for left_variant, right_variant in (
        (left, right),
        (collapsed_left, collapsed_right),
    ):
        if is_single_adjacent_substitution(left_variant, right_variant):
            return 0.92
        if is_single_transposition(left_variant, right_variant):
            return 0.90
        if is_single_insertion_or_deletion(left_variant, right_variant):
            return 0.82

    ratio = SequenceMatcher(None, collapsed_left, collapsed_right).ratio()
    if ratio >= 0.9:
        return ratio * 0.82

    return 0.0


def collapse_repeated_letters(word: str) -> str:
    collapsed = []
    previous = ""

    for character in word:
        if character == previous:
            continue
        collapsed.append(character)
        previous = character

    return "".join(collapsed)


def is_single_adjacent_substitution(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False

    differences = [
        (left_character, right_character)
        for left_character, right_character in zip(left, right, strict=False)
        if left_character != right_character
    ]

    if len(differences) != 1:
        return False

    left_character, right_character = differences[0]
    return right_character in KEYBOARD_NEIGHBOURS.get(left_character, frozenset())


def is_single_transposition(left: str, right: str) -> bool:
    if len(left) != len(right) or len(left) < 2:
        return False

    differences = [
        index
        for index, (left_character, right_character) in enumerate(
            zip(left, right, strict=False)
        )
        if left_character != right_character
    ]

    if len(differences) != 2:
        return False

    first, second = differences
    if second != first + 1:
        return False

    return left[first] == right[second] and left[second] == right[first]


def is_single_insertion_or_deletion(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) != 1:
        return False

    shorter, longer = sorted((left, right), key=len)
    shorter_index = 0
    longer_index = 0
    edits = 0

    while shorter_index < len(shorter) and longer_index < len(longer):
        if shorter[shorter_index] == longer[longer_index]:
            shorter_index += 1
            longer_index += 1
            continue

        edits += 1
        if edits > 1:
            return False
        longer_index += 1

    return True


def build_keyboard_neighbours() -> dict[str, frozenset[str]]:
    neighbours: dict[str, set[str]] = {}

    for layout in KEYBOARD_LAYOUTS:
        coordinates = {}
        for row_index, (row, offset) in enumerate(layout):
            for column_index, character in enumerate(row):
                coordinates[character] = (row_index, column_index + offset)

        for character, (row_index, column_position) in coordinates.items():
            current_neighbours = neighbours.setdefault(character, set())
            for other_character, (other_row, other_position) in coordinates.items():
                if other_character == character:
                    continue
                if abs(row_index - other_row) <= 1 and abs(
                    column_position - other_position
                ) <= 1.15:
                    current_neighbours.add(other_character)

    return {
        character: frozenset(current_neighbours)
        for character, current_neighbours in neighbours.items()
    }


KEYBOARD_NEIGHBOURS = build_keyboard_neighbours()
