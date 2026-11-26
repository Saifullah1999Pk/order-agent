from datetime import datetime
from decimal import Decimal

from order_agent.controller.session import CallController
from order_agent.model.brief import WantedLine

NOW = datetime(2026, 11, 23, 19, 30)
REFUSAL = "Refused: you already added {n} x {item} since the restaurant last spoke. Add more only after the restaurant agrees to more."


def _c(make_brief, tmp_path) -> CallController:
    brief = make_brief(wanted=[WantedLine(item="chicken biryani", quantity=2), WantedLine(item="raita", quantity=3, optional=True)])
    return CallController(brief, reports_dir=tmp_path, now=NOW)


def _raita(n=1, name="raita"):
    return {"name": name, "quantity": n, "unit_price_pkr": 100}


def _qty(c, name="raita"):
    return sum(i.quantity for i in c.session.items if i.name == name)


async def test_second_identical_add_in_same_turn_is_refused(make_brief, tmp_path):
    c = _c(make_brief, tmp_path)
    c.llm_turn_started()
    assert (await c.perform("add_item", _raita())).ok
    out = await c.perform("add_item", _raita())
    assert not out.ok and out.message == REFUSAL.format(n=1, item="raita")
    assert _qty(c) == 1
    last = c.session.events[-1]
    assert (last.tool, last.ok, last.message) == ("add_item", False, out.message)
    assert last.args["quantity"] == 1 and last.args["name"] == "raita"


async def test_different_quantity_or_item_same_turn_allowed(make_brief, tmp_path):
    c = _c(make_brief, tmp_path)
    c.llm_turn_started()
    assert (await c.perform("add_item", _raita(1))).ok
    assert (await c.perform("add_item", _raita(2))).ok
    assert (await c.perform("add_item", {"name": "chicken biryani", "quantity": 1, "unit_price_pkr": 900})).ok


async def test_next_llm_generation_does_not_reset_the_guard(make_brief, tmp_path):
    # Pipecat reports a new assistant turn for every generation, including the re-run after tool results.
    c = _c(make_brief, tmp_path)
    c.llm_turn_started()
    assert (await c.perform("add_item", _raita())).ok
    c.llm_turn_started()
    out = await c.perform("add_item", _raita())
    assert not out.ok and out.message == REFUSAL.format(n=1, item="raita")
    assert _qty(c) == 1


async def test_restaurant_speaking_resets_the_guard(make_brief, tmp_path):
    c = _c(make_brief, tmp_path)
    c.llm_turn_started()
    assert (await c.perform("add_item", _raita())).ok
    c.restaurant_spoke()
    c.llm_turn_started()
    assert (await c.perform("add_item", _raita())).ok
    assert _qty(c) == 2


async def test_refusal_appears_in_the_built_report(make_brief, tmp_path):
    c = _c(make_brief, tmp_path)
    c.llm_turn_started()
    await c.perform("add_item", _raita())
    out = await c.perform("add_item", _raita())
    await c.finish("not_ordered", "x")
    events = [e for e in c.report.tool_events if e["tool"] == "add_item"]
    assert [e["ok"] for e in events] == [True, False]
    assert events[1]["message"] == out.message and events[1]["args"]["quantity"] == 1


async def test_refusal_uses_the_cart_name(make_brief, tmp_path):
    c = _c(make_brief, tmp_path)
    c.llm_turn_started()
    await c.perform("add_item", _raita(1, "Raita"))
    out = await c.perform("add_item", _raita(1, "raitas"))
    assert out.message == REFUSAL.format(n=1, item="Raita")


async def test_guard_inactive_when_turns_never_reported(make_brief, tmp_path):
    c = _c(make_brief, tmp_path)
    assert (await c.perform("add_item", _raita())).ok
    assert (await c.perform("add_item", _raita())).ok
    assert _qty(c) == 2


async def test_name_variants_count_as_the_same_item(make_brief, tmp_path):
    c = _c(make_brief, tmp_path)
    c.llm_turn_started()
    assert (await c.perform("add_item", _raita(1, "Raita"))).ok
    out = await c.perform("add_item", _raita(1.0, "raitas"))
    assert not out.ok and "already added" in out.message


async def test_a_refused_add_does_not_arm_the_guard(make_brief, tmp_path):
    c = _c(make_brief, tmp_path)
    c.llm_turn_started()
    assert not (await c.perform("add_item", {"name": "naan", "quantity": 1})).ok
    assert not (await c.perform("add_item", {"name": "naan", "quantity": 1})).ok
    assert "already added" not in c.session.events[-1].message


async def test_malformed_add_goes_to_normal_refusal(make_brief, tmp_path):
    c = _c(make_brief, tmp_path)
    c.llm_turn_started()
    assert (await c.perform("add_item", {"name": "raita", "quantity": "x"})).ok is False
    assert (await c.perform("add_item", None)).ok is False
