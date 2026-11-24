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


def _goals():
    for path in SCENARIOS:
        text = path.read_text(encoding="utf-8").replace("!include ../simulator.yaml", "x").replace(
            "!include ../judge.yaml", "x"
        )
        for sc in yaml.safe_load(text)["scenarios"]:
            yield path.name, " ".join(sc["goal"].split())


def test_goal_forbids_ending_the_call_before_the_customer_says_goodbye():
    # The persona LLM ends the call whenever its goal text sounds done. Goals that read "quote the
    # total, then end the call" made it hang up on its own quote (35 of 36 end_calls in the ordered
    # scenarios, see evals/confirmation/persona-hangups/ANALYSIS.md). The customer (the bot) ends
    # the call itself, so every goal must forbid end_call until the customer has said goodbye.
    for name, goal in _goals():
        assert "Do not call end_call until the customer has said goodbye" in goal, name
        assert "same turn as your own message" in goal, name
