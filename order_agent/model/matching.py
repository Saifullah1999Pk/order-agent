"""Item-name matching: tolerant of case, word order and plurals, never of partial names."""

import re

from order_agent.model.brief import OrderBrief, WantedLine


def _singular(word: str) -> str:
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def normalise(name: str) -> frozenset[str]:
    words = re.sub(r"[^a-z]", " ", name.lower()).split()
    return frozenset(_singular(w) for w in words)


def match_line(brief: OrderBrief, name: str) -> tuple[WantedLine, bool] | None:
    """Return (line, is_substitute) for the brief line this name fills, else None."""
    target = normalise(name)
    if not target:
        return None
    for line in brief.wanted:
        if normalise(line.item) == target:
            return line, False
        if any(normalise(sub) == target for sub in line.substitutes):
            return line, True
    return None
