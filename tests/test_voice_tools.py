import pytest

from order_agent import tools as legacy_tools
from order_agent.controller.session import CallController
from order_agent.controller.toolspecs import TOOL_SPECS
from order_agent.heads.voice.tools import build_tools
from order_agent.rules import OrderSession


@pytest.fixture
def controller(brief, tmp_path):
    return CallController(brief, reports_dir=tmp_path)


def _shape(schema):
    return (schema.name, schema.description, schema.properties, schema.required)


def test_schemas_equal_tool_specs(controller):
    schemas = build_tools(controller).standard_tools
    assert len(schemas) == 7
    assert [_shape(s) for s in schemas] == [(s.name, s.description, s.properties, s.required) for s in TOOL_SPECS]


def test_schemas_equal_legacy_build_tools(controller, brief):
    async def on_end(outcome, reason):
        pass

    legacy = legacy_tools.build_tools(OrderSession(brief, brief.call_time), on_end).standard_tools
    new = build_tools(controller).standard_tools
    assert [_shape(s) for s in new] == [_shape(s) for s in legacy]


def test_every_schema_has_a_callable_handler(controller):
    assert all(callable(s.handler) for s in build_tools(controller).standard_tools)
