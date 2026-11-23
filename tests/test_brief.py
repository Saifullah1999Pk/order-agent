from datetime import time
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


def _write_with_deliver_by(tmp_path, literal: str) -> Path:
    text = Path("briefs/example.yaml").read_text(encoding="utf-8")
    lines = [
        f"deliver_by: {literal}" if l.startswith("deliver_by:") else l
        for l in text.splitlines()
    ]
    path = tmp_path / "brief.yaml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_unquoted_deliver_by_loads_as_21_00(tmp_path):
    # YAML 1.1 reads an unquoted 21:00 as the int 1260; it must still mean 21:00.
    brief = load_brief(_write_with_deliver_by(tmp_path, "21:00"))
    assert brief.deliver_by == time(21, 0)


def test_quoted_deliver_by_still_works(tmp_path):
    brief = load_brief(_write_with_deliver_by(tmp_path, '"21:30"'))
    assert brief.deliver_by == time(21, 30)


@pytest.mark.parametrize("bad", ["25.5", "1500", "-60", "true", '"noon"'])
def test_invalid_deliver_by_rejected(tmp_path, bad):
    with pytest.raises(ValidationError):
        load_brief(_write_with_deliver_by(tmp_path, bad))
