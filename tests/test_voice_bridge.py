"""T027: each Pipecat event maps to exactly one controller call (contracts/controller-api.md, "Voice head mapping")."""

import ast
from pathlib import Path
from types import SimpleNamespace

from order_agent.heads.voice import bridge
from order_agent.heads.voice.bridge import register_events


class FakeEmitter:
    def __init__(self):
        self.handlers = {}

    def event_handler(self, name):
        def decorator(fn):
            self.handlers[name] = fn
            return fn

        return decorator


class FakeController:
    def __init__(self, log):
        self.log = log

    def channel_opened(self):
        self.log.append(("channel_opened",))

    async def drop(self):
        self.log.append(("drop",))

    def restaurant_spoke(self, text=None):
        self.log.append(("restaurant_spoke", text))

    def add_line(self, role, text):
        self.log.append(("add_line", role, text))

    def function_calls_started(self):
        self.log.append(("function_calls_started",))

    def llm_turn_started(self):
        self.log.append(("llm_turn_started",))

    def llm_turn_ended(self, content, interrupted=False):
        self.log.append(("llm_turn_ended", content, interrupted))


class FakeRunner:
    def __init__(self, log):
        self.log = log

    async def cancel(self):
        self.log.append(("runner.cancel",))


def _wire():
    log = []
    transport, user, assistant, llm = FakeEmitter(), FakeEmitter(), FakeEmitter(), FakeEmitter()
    register_events(transport, user, assistant, llm, FakeController(log), FakeRunner(log))
    return log, transport.handlers, user.handlers, assistant.handlers, llm.handlers


def test_registers_exactly_the_mapped_events():
    _, t, u, a, l = _wire()
    assert set(t) == {"on_client_connected", "on_client_disconnected"}
    assert set(u) == {"on_user_turn_started", "on_user_turn_message_added"}
    assert set(a) == {"on_assistant_turn_started", "on_assistant_turn_stopped"}
    assert set(l) == {"on_function_calls_started"}


async def test_client_connected_opens_the_channel():
    log, t, *_ = _wire()
    await t["on_client_connected"](None, None)
    assert log == [("channel_opened",)]


async def test_client_disconnected_drops_then_cancels_the_runner():
    log, t, *_ = _wire()
    await t["on_client_disconnected"](None, None)
    assert log == [("drop",), ("runner.cancel",)]


async def test_user_turn_started_is_restaurant_spoke_without_text():
    log, _, u, *_ = _wire()
    await u["on_user_turn_started"](None, None)
    assert log == [("restaurant_spoke", None)]


async def test_user_turn_message_added_adds_a_restaurant_line():
    log, _, u, *_ = _wire()
    await u["on_user_turn_message_added"](None, SimpleNamespace(content="Hello, Pizza Palace"))
    assert log == [("add_line", "restaurant", "Hello, Pizza Palace")]


async def test_function_calls_started():
    log, *_, l = _wire()
    await l["on_function_calls_started"](None, [object()])
    assert log == [("function_calls_started",)]


async def test_assistant_turn_started():
    log, _, _, a, _ = _wire()
    await a["on_assistant_turn_started"](None)
    assert log == [("llm_turn_started",)]


async def test_assistant_turn_stopped_passes_content_and_interrupted():
    log, _, _, a, _ = _wire()
    await a["on_assistant_turn_stopped"](None, SimpleNamespace(content="Hi.", interrupted=False))
    await a["on_assistant_turn_stopped"](None, SimpleNamespace(content="", interrupted=True))
    assert log == [("llm_turn_ended", "Hi.", False), ("llm_turn_ended", "", True)]


def test_bridge_holds_no_state_and_no_content_conditionals():
    tree = ast.parse(Path(bridge.__file__).read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.If, ast.Nonlocal, ast.Global, ast.ClassDef))]
    assert register_events(FakeEmitter(), FakeEmitter(), FakeEmitter(), FakeEmitter(), FakeController([]), FakeRunner([])) is None
