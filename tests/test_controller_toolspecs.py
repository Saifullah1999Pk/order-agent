from types import SimpleNamespace

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
    legacy = {t.name: t for t in build_tools(CallController(brief, reports_dir=tmp_path)).standard_tools}
    for spec in TOOL_SPECS:
        schema = legacy[spec.name]
        assert spec.description == schema.description
        assert spec.properties == schema.properties
        assert spec.required == schema.required
