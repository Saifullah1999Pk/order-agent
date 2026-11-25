"""Every scenario persona carries a precomputed totals line, so the simulated restaurant never adds up itself.

Fixed format, one occurrence per persona (whitespace is normalised, so it may wrap over lines):

    Totals (Rs, delivery included): <order> = <total>; <order> = <total>. When you quote a total, use these exact figures; never add it up yourself.

where <order> is `<qty> <item name>` terms joined by " + " (for example `2 chicken biryani + 1 raita`).
The total is the sum of qty x menu_pkr unit price for each term plus the delivery and tax from
fees_pkr, both read from evals/expected.yaml for that scenario. This test recomputes every figure
and fails on any mismatch, which also pins the persona's menu numbers to expected.yaml.
"""

import re
from decimal import Decimal
from pathlib import Path

import yaml

from order_agent.suite import load_expected

SCENARIO_DIR = Path(__file__).parent.parent / "evals" / "scenarios"
TOTALS = re.compile(
    r"Totals \(Rs, delivery included\): (?P<body>.+?)\. When you quote a total, use these exact figures; never add it up yourself\."
)
TERM = re.compile(r"^(?P<qty>\d+) (?P<name>[a-z ]+?)$")


def _persona(name: str) -> str:
    text = (SCENARIO_DIR / f"{name}.yaml").read_text(encoding="utf-8")
    text = text.replace("!include ../simulator.yaml", "x").replace("!include ../judge.yaml", "x")
    return " ".join(yaml.safe_load(text)["scenarios"][0]["persona"].split())


def _recompute(expected, order: str) -> Decimal:
    total = sum(expected.fees_pkr.values(), Decimal(0))
    for term in order.split(" + "):
        m = TERM.match(term.strip())
        assert m, f"cannot parse term {term!r}"
        assert m["name"] in expected.menu_pkr, f"{m['name']!r} is not in menu_pkr"
        total += int(m["qty"]) * expected.menu_pkr[m["name"]]
    return total


def test_every_persona_has_a_totals_line_and_every_figure_is_right():
    expectations = load_expected()
    assert len(expectations) == 11
    for name, expected in expectations.items():
        match = TOTALS.search(_persona(name))
        assert match, f"{name}: no Totals line"
        clauses = match["body"].split("; ")
        assert clauses, name
        for clause in clauses:
            order, _, figure = clause.partition(" = ")
            assert figure.isdigit(), f"{name}: bad clause {clause!r}"
            assert _recompute(expected, order) == Decimal(figure), f"{name}: {clause!r} should be {_recompute(expected, order)}"


def test_totals_parser_catches_a_wrong_figure():
    expected = load_expected()["happy_path"]
    assert _recompute(expected, "2 chicken biryani + 1 raita") == 2100
    assert _recompute(expected, "2 chicken biryani + 1 raita") != 1250
