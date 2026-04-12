from __future__ import annotations

import random

from .models import ChatMessageIn


USERNAMES = [
    "pixelfox",
    "chatmage",
    "mod_jules",
    "lagwatcher",
    "speedrunner92",
    "cozyviewer",
    "nightowl",
    "capslockhero",
]

MESSAGES = [
    "thsi boss fight is impossible",
    "teh audio is lagging again",
    "this game sux",
    "please fix the lag",
    "the puzzle room looks amazing",
    "why is chat so slow today",
    "that ending was wild",
    "ban the spam bots please",
    "this game sucks!!",
    "what keyboard are you using",
    "audio desync again",
    "teh stream is stuttering",
]


def random_message() -> ChatMessageIn:
    return ChatMessageIn(
        username=random.choice(USERNAMES),
        body=random.choice(MESSAGES),
    )
