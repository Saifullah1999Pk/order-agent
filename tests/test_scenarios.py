from pathlib import Path

import yaml

SCENARIOS = sorted(Path(__file__).parent.parent.joinpath("evals", "scenarios").glob("*.yaml"))
GENERIC = (
    "Reply with only your own next line (one or two short sentences), then stop and wait for "
    "the customer. Never write the customer's lines."
)


def _personas():
    for path in SCENARIOS:
        text = path.read_text(encoding="utf-8").replace("!include ../simulator.yaml", "x").replace(
            "!include ../judge.yaml", "x"
        )
        for sc in yaml.safe_load(text)["scenarios"]:
            yield path.name, " ".join(sc["persona"].split())


def test_all_eleven_scenarios_found():
    assert len(list(_personas())) == 11


def test_every_persona_has_generic_one_line_rule():
    for name, persona in _personas():
        assert GENERIC in persona, name


def test_every_persona_has_an_end_condition():
    for name, persona in _personas():
        assert "Do not end the call until" in persona, name
