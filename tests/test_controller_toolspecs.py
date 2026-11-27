import hashlib
import json
from dataclasses import asdict

from order_agent.controller.toolspecs import TOOL_SPECS, ToolSpec
from order_agent.controller import CallController
from order_agent.heads.voice.tools import build_tools

NAMES = ["add_item", "set_price", "remove_item", "set_fees", "set_minimum_order", "confirm_order", "end_call"]


def test_names_are_unique_and_ordered():
    names = [spec.name for spec in TOOL_SPECS]
    assert names == NAMES
    assert len(set(names)) == len(names)


def test_specs_are_frozen_toolspecs():
    assert all(isinstance(spec, ToolSpec) for spec in TOOL_SPECS)


def test_specs_match_voice_function_schemas(brief, tmp_path):
    schemas = {t.name: t for t in build_tools(CallController(brief, reports_dir=tmp_path)).standard_tools}
    for spec in TOOL_SPECS:
        schema = schemas[spec.name]
        assert spec.description == schema.description
        assert spec.properties == schema.properties
        assert spec.required == schema.required


# sha256 of the LLM-visible tool text (was identical to main's tools.py 9c38b8f until feature 002 added confirm_order.restaurant_items).
# A deliberate change to a tool description or schema must update this hash on purpose.
TOOL_TEXT_SHA256 = "1dc7c245db01caa7abaac500417cea9a69aead71d03a05eca628e8cfb5e09127"


def test_tool_text_is_pinned():
    text = json.dumps([asdict(spec) for spec in TOOL_SPECS], sort_keys=True)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == TOOL_TEXT_SHA256


def test_confirm_order_has_optional_restaurant_items_array():
    spec = next(s for s in TOOL_SPECS if s.name == "confirm_order")
    prop = spec.properties["restaurant_items"]
    assert prop["type"] == "array"
    assert prop["items"]["type"] == "object"
    assert prop["items"]["properties"] == {"name": {"type": "string"}, "quantity": {"type": "integer"}}
    assert prop["items"]["required"] == ["name", "quantity"]
    assert spec.required == ["quoted_total_pkr", "delivery_minutes"]
