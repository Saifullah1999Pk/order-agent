from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from order_agent.brief import OrderBrief, load_brief


def _data() -> dict:
    return yaml.safe_load(Path("briefs/example.yaml").read_text(encoding="utf-8"))


def test_load_example_brief():
    brief = load_brief(Path("briefs/example.yaml"))
    assert brief.budget_pkr == Decimal("2500")
    assert brief.wanted[0].substitutes == ["chicken karahi", "chicken pulao"]


def test_never_list_form_normalised():
    data = _data()
    data["never"] = ["beef"]
    assert OrderBrief(**data).never == {"beef": ["beef"]}


def test_never_mapping_always_includes_rule_name():
    data = _data()
    data["never"] = {"seafood": ["fish", "prawn"]}
    assert OrderBrief(**data).never == {"seafood": ["seafood", "fish", "prawn"]}


def test_brief_rejects_zero_budget():
    data = _data()
    data["budget_pkr"] = 0
    with pytest.raises(ValidationError):
        OrderBrief(**data)


def test_brief_rejects_empty_wanted_and_zero_quantity():
    data = _data()
    data["wanted"] = []
    with pytest.raises(ValidationError):
        OrderBrief(**data)
    data["wanted"] = [{"item": "raita", "quantity": 0}]
    with pytest.raises(ValidationError):
        OrderBrief(**data)
