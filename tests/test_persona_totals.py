"""Every scenario persona carries a precomputed totals line, so the simulated restaurant never adds up itself.

This test pins the Totals line figures (not the prose menu elsewhere in the persona) to
evals/expected.yaml. Fixed format, one occurrence per persona (whitespace is normalised, so it may wrap):

    Totals (Rs, delivery included): <order> = <total>; <order> = <total> (below the minimum). When you quote a total, use these exact figures; never add it up yourself.

where <order> is `<qty> <item name>` terms joined by " + " (for example `2 chicken biryani + 1 raita`).
The total is the sum of qty x menu_pkr unit price for each term plus the delivery and tax from
fees_pkr, both read from evals/expected.yaml for that scenario. In the two minimum-order scenarios a
figure whose food subtotal is under the minimum must end with " (below the minimum)" and no other
figure may. The check recomputes every figure and reports each mismatch.
"""

import re
from decimal import Decimal
from pathlib import Path

import yaml

from order_agent.evaltools.suite import load_expected

SCENARIO_DIR = Path(__file__).parent.parent / "evals" / "scenarios"
MINIMUM_FOOD_PKR = {"minimum_reachable": Decimal(2200), "minimum_unreachable": Decimal(3000)}
TOTALS = re.compile(
    r"Totals \(Rs, delivery included\): (?P<body>.+?)\. When you quote a total, use these exact figures; never add it up yourself\."
)
CLAUSE = re.compile(r"^(?P<order>.+?) = (?P<figure>\d+)(?P<below> \(below the minimum\))?$")
TERM = re.compile(r"^(?P<qty>\d+) (?P<name>[a-z ]+?)$")


def _persona(name: str) -> str:
    text = (SCENARIO_DIR / f"{name}.yaml").read_text(encoding="utf-8")
    text = text.replace("!include ../simulator.yaml", "x").replace("!include ../judge.yaml", "x")
    return " ".join(yaml.safe_load(text)["scenarios"][0]["persona"].split())


def _food(expected, order: str) -> Decimal:
    food = Decimal(0)
    for term in order.split(" + "):
        m = TERM.match(term.strip())
        assert m, f"cannot parse term {term!r}"
        assert m["name"] in expected.menu_pkr, f"{m['name']!r} is not in menu_pkr"
        food += int(m["qty"]) * expected.menu_pkr[m["name"]]
    return food


def problems(name: str, persona: str, expected) -> list[str]:
    """Every way the persona's Totals line disagrees with expected.yaml (empty = fine)."""
    match = TOTALS.search(persona)
    if not match:
        return [f"{name}: no Totals line"]
    found = []
    fees = sum(expected.fees_pkr.values(), Decimal(0))
    for clause in match["body"].split("; "):
        m = CLAUSE.match(clause)
        if not m:
            found.append(f"{name}: bad clause {clause!r}")
            continue
        food = _food(expected, m["order"])
        if food + fees != Decimal(m["figure"]):
            found.append(f"{name}: {clause!r} should be {food + fees}")
        minimum = MINIMUM_FOOD_PKR.get(name)
        if minimum is not None and (food < minimum) != bool(m["below"]):
            found.append(f"{name}: {clause!r} has the wrong below-the-minimum mark (food {food}, minimum {minimum})")
    return found


def test_every_persona_has_a_totals_line_and_every_figure_is_right():
    expectations = load_expected()
    assert len(expectations) == 11
    for name, expected in expectations.items():
        assert problems(name, _persona(name), expected) == []


def test_check_catches_a_corrupted_figure_and_a_wrong_mark():
    expected = load_expected()
    persona = _persona("happy_path")
    assert "2 chicken biryani + 1 raita = 2100" in persona
    bad = persona.replace("2 chicken biryani + 1 raita = 2100", "2 chicken biryani + 1 raita = 1250")
    assert any("should be 2100" in p for p in problems("happy_path", bad, expected["happy_path"]))
    minimum = _persona("minimum_reachable")
    unmarked = minimum.replace(" (below the minimum)", "")
    assert any("below-the-minimum" in p for p in problems("minimum_reachable", unmarked, expected["minimum_reachable"]))
    assert problems("happy_path", "no totals here", expected["happy_path"]) == ["happy_path: no Totals line"]


def test_totals_cover_the_plausible_orders():
    """Single-dish and mixed orders the bot might plausibly place must be on the line (rule c depends on it)."""
    def orders(name):
        return {c.split(" = ")[0] for c in TOTALS.search(_persona(name))["body"].split("; ")}

    assert {"1 chicken biryani", "1 chicken biryani + 1 raita"} <= orders("happy_path")
    assert "1 chicken karahi + 1 chicken pulao" in orders("sold_out_substitute")
    assert {"1 raita", "1 prawn biryani", "1 prawn biryani + 1 raita"} <= orders("sold_out_no_substitute")
