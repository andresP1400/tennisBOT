"""Resolve reviewed result names only when their historical identity is unique."""

from __future__ import annotations

import re

import pandas as pd

from pipeline.personal_state import normalize_name


def identity_aliases(history: pd.DataFrame) -> dict[str, tuple[int, str]]:
    """Exclude ambiguous initials rather than assigning another player's results."""
    candidates: dict[str, dict[int, str]] = {}
    for side in ("winner", "loser"):
        pairs = history[[f"{side}_id", f"{side}_name"]].drop_duplicates()
        for identifier, name in pairs.itertuples(index=False, name=None):
            for alias in name_aliases(str(name)):
                candidates.setdefault(alias, {})[int(identifier)] = str(name)
    return {
        alias: next(iter(players.items()))
        for alias, players in candidates.items()
        if len(players) == 1
    }


def name_aliases(name: str) -> set[str]:
    """Keep full surnames, allowing explicitly abbreviated given-name initials."""
    words = name.split()
    aliases = {normalize_name(name)}
    for boundary in range(1, len(words)):
        surname = " ".join(words[boundary:])
        initials = [word[0] for word in words[:boundary]]
        for count in range(1, len(initials) + 1):
            aliases.add(normalize_name(surname + " " + "".join(initials[:count])))
    return aliases


def official_name(value: str) -> str:
    """Official WTA names use surname-first ordering and an optional country suffix."""
    clean = re.sub(r"\s+[A-Z]{3}$", "", value).strip()
    if "," not in clean:
        return clean
    surname, given = clean.split(",", 1)
    return f"{given.strip()} {surname.strip()}"
