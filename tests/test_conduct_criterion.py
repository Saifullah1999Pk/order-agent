"""Every scenario judges conduct with the same criterion, and it names what is allowed.

Why: the judge (an LLM) read the old wording, "never states a price or item the restaurant did
not say", literally, and failed the bot for asking about substitutes from its brief, asking about
tax, or mentioning its own budget (run 20261127-130223, 7 of 12 failed attempts).
"""

from pathlib import Path

import yaml

SCENARIOS = sorted((Path(__file__).parent.parent / "evals" / "scenarios").glob("*.yaml"))


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_constructor("!include", lambda loader, node: None)


def _conduct(path: Path) -> str:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)
    (metric,) = [m for s in data["scenarios"] for m in s["metrics"] if m["name"] == "conduct"]
    return metric["criterion"]


def test_all_scenarios_share_one_conduct_criterion():
    assert len(SCENARIOS) == 11
    assert len({_conduct(p) for p in SCENARIOS}) == 1


def test_conduct_criterion_names_what_is_allowed_and_still_forbids_own_totals():
    text = _conduct(SCENARIOS[0])
    assert "never states a total it worked out itself" in text
    assert "when it confirms a total it is the total the restaurant stated" in text
    assert "Allowed and not a violation" in text
    for allowed in ("listed substitutes", "delivery fee, tax or minimum order", "own budget"):
        assert allowed in text
