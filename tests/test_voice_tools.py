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


# --- T022: handlers

from types import SimpleNamespace  # noqa: E402


class Harness:
    def __init__(self, controller):
        self.controller = controller
        self.tools = build_tools(controller)
        self.payloads: list = []
        self.properties: list = []
        self.events: list[str] = []

    async def call(self, tool, arguments):
        schema = next(t for t in self.tools.standard_tools if t.name == tool)
        before = len(self.payloads)

        async def result_callback(result, properties=None):
            self.payloads.append(result)
            self.properties.append(properties)
            self.events.append(f"reply:report_exists={any(self.controller.reports_dir.glob('*'))}")

        await schema.handler(SimpleNamespace(arguments=arguments, result_callback=result_callback))
        assert len(self.payloads) == before + 1  # exactly one result_callback per tool call
        return self.payloads[-1]


class FakeHooks:
    def __init__(self, events):
        self.events = events

    async def inject(self, text):
        self.events.append("inject")

    async def hangup(self):
        self.events.append("hangup")


@pytest.fixture
def h(controller):
    return Harness(controller)


async def test_payload_matches_outcome_and_properties_none(h):
    result = await h.call("add_item", {"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900})
    assert result == {"ok": True, "message": result["message"]}
    assert set(result) == {"ok", "message"}
    assert h.properties[-1] is None


@pytest.mark.parametrize("bad", ["not a dict", None, 5, ["a"], {}])
@pytest.mark.parametrize("tool", [s.name for s in TOOL_SPECS])
async def test_bad_arguments_get_exactly_one_refusal(h, tool, bad):
    result = await h.call(tool, bad)
    assert result["ok"] is False
    assert h.properties[-1] is None
    assert h.controller.session.items == []


async def test_refused_end_call_lets_llm_run(h):
    result = await h.call("end_call", {"outcome": "ordered", "reason": "done"})
    assert result["ok"] is False
    assert h.properties[-1] is None
    assert not h.controller.finished


async def test_successful_end_call_stops_llm_rerun(h):
    result = await h.call("end_call", {"outcome": "not_ordered", "reason": "sold out"})
    assert result["ok"] is True
    assert h.properties[-1].run_llm is False
    assert h.controller.finished


async def test_reply_precedes_report_and_hangup(h):
    h.controller.attach_hooks(FakeHooks(h.events))
    await h.call("end_call", {"outcome": "not_ordered", "reason": "sold out"})
    assert h.events == ["reply:report_exists=False", "hangup"]
    assert any(h.controller.reports_dir.glob("*"))
