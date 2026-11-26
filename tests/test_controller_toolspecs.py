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


# sha256 of the LLM-visible tool text, verified identical to main's order_agent/tools.py (9c38b8f).
# A deliberate change to a tool description or schema must update this hash on purpose.
TOOL_TEXT_SHA256 = "435f0ac703d61bc705f2d03ca3d5202556c107b6ca8b09db2022940ae79be8c8"


def test_tool_text_is_pinned():
    text = json.dumps([asdict(spec) for spec in TOOL_SPECS], sort_keys=True)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == TOOL_TEXT_SHA256
