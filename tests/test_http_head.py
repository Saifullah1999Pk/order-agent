from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from architecture import violations
from order_agent.heads.http_api.app import create_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def reports_dir(tmp_path):
    return tmp_path / "reports"


@pytest.fixture
def client(reports_dir):
    return TestClient(create_app(reports_dir, brief_dir=ROOT / "briefs"))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_validation_errors_use_the_uniform_body(reports_dir):
    app = create_app(reports_dir)

    class Body(BaseModel):
        n: int

    @app.post("/probe")
    def probe(body: Body):
        return {}

    r = TestClient(app).post("/probe", json={"n": "x"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


@pytest.mark.parametrize(
    "src",
    [
        "import pipecat",
        "import torch",
        "from order_agent.heads.voice import x",
        "from order_agent.model.rules import OrderSession",
        "from order_agent.model.matching import match_line",
        "from order_agent.evaltools import x",
    ],
)
def test_checker_catches_forbidden_http_head_imports(src):
    assert violations(src, "heads/http_api", package="order_agent.heads.http_api") != []


def test_checker_accepts_clean_http_head_snippet():
    src = (
        "from fastapi import FastAPI\nfrom order_agent.controller import CallController\n"
        "from order_agent.model.brief import load_brief\nfrom order_agent.model.report import summarise\n"
    )
    assert violations(src, "heads/http_api", package="order_agent.heads.http_api") == []


# --- POST /sessions (T038)

import yaml  # noqa: E402

from order_agent.controller.prompt import build_system_prompt  # noqa: E402
from order_agent.model.brief import OrderBrief, load_brief  # noqa: E402


def _brief_dict():
    raw = yaml.safe_load((ROOT / "briefs" / "example.yaml").read_text(encoding="utf-8"))
    return OrderBrief(**raw).model_dump(mode="json")


def test_create_session_inline_brief(client):
    r = client.post("/sessions", json={"brief": _brief_dict()})
    assert r.status_code == 201
    body = r.json()
    assert len(body["session_id"]) == 32
    assert body["instructions"] == build_system_prompt(OrderBrief(**_brief_dict()))
    assert body["opening_text"].startswith("Nobody has spoken yet.")
    assert len(body["tools"]) == 7
    assert {t["name"] for t in body["tools"]} >= {"add_item", "end_call"}
    add = next(t for t in body["tools"] if t["name"] == "add_item")
    assert add["required"] == ["name", "quantity"] and "properties" in add and add["description"]


def test_create_session_by_brief_name(client):
    r = client.post("/sessions", json={"brief_name": "example"})
    assert r.status_code == 201
    assert r.json()["instructions"] == build_system_prompt(load_brief(ROOT / "briefs" / "example.yaml"))


def test_call_time_overrides(client):
    inline = client.post("/sessions", json={"brief": _brief_dict()}).json()["instructions"]
    other = client.post(
        "/sessions", json={"brief": _brief_dict(), "call_time": "2026-11-23T08:00:00"}
    ).json()["instructions"]
    expected = build_system_prompt(
        OrderBrief(**_brief_dict()).model_copy(update={"call_time": __import__("datetime").datetime(2026, 11, 23, 8)})
    )
    assert other == expected
    assert isinstance(inline, str)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"brief_name": "example", "brief": {}},
        {"brief_name": "does_not_exist"},
        {"brief_name": "../example"},
        {"brief_name": "..\example"},
        {"brief": {"customer_name": "only a name"}},
    ],
)
def test_create_session_422(client, payload):
    r = client.post("/sessions", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_create_session_invalid_brief_file_is_422(reports_dir, tmp_path):
    bad_dir = tmp_path / "briefs"
    bad_dir.mkdir()
    (bad_dir / "bad.yaml").write_text("customer_name: x\n", encoding="utf-8")
    c = TestClient(create_app(reports_dir, brief_dir=bad_dir))
    r = c.post("/sessions", json={"brief_name": "bad"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_create_session_429_beyond_cap(client):
    client.app.state.store.max_sessions = 2
    assert client.post("/sessions", json={"brief_name": "example"}).status_code == 201
    assert client.post("/sessions", json={"brief_name": "example"}).status_code == 201
    r = client.post("/sessions", json={"brief_name": "example"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "too_many_sessions"


# --- GET /sessions/{id} (T039)

def _new(client, name="example"):
    r = client.post("/sessions", json={"brief_name": name})
    assert r.status_code == 201
    return r.json()["session_id"]


def test_get_session_new(client):
    sid = _new(client)
    r = client.get(f"/sessions/{sid}")
    assert r.status_code == 200
    assert r.json() == {
        "session_id": sid,
        "state": "live",
        "order_state": "open",
        "transcript_lines": 0,
        "report_ready": False,
    }


def test_get_session_confirmed_after_confirm(client):
    from decimal import Decimal

    sid = _new(client)
    session = client.app.state.store.get(sid).session
    assert session.add_item("chicken biryani", 2, Decimal(900), False).ok
    assert session.set_fees(Decimal(150), Decimal(0), False).ok
    assert session.confirm_order(Decimal(1950), 45).ok
    assert client.get(f"/sessions/{sid}").json()["order_state"] == "confirmed"


def test_get_session_unknown_is_404(client):
    r = client.get("/sessions/" + "0" * 32)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "session_not_found"


# --- POST /sessions/{id}/actions (T040)

import asyncio  # noqa: E402
from datetime import datetime  # noqa: E402

from order_agent.controller import CallController  # noqa: E402


def _act(client, sid, tool, **arguments):
    return client.post(f"/sessions/{sid}/actions", json={"tool": tool, "arguments": arguments})


def _direct(tool, **arguments):
    """What the controller itself answers on a fresh session built from the same brief."""
    ctrl = CallController(load_brief(ROOT / "briefs" / "example.yaml"), reports_dir=Path("unused"), now=datetime(2026, 11, 23, 19, 30))
    return asyncio.run(ctrl.perform(tool, arguments))


def test_action_add_item_ok(client):
    sid = _new(client)
    r = _act(client, sid, "add_item", name="chicken biryani", quantity=2, unit_price_pkr=900)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["ended"] is False and body["message"]


def test_action_forbidden_item_is_a_200_refusal(client):
    sid = _new(client)
    r = _act(client, sid, "add_item", name="prawn karahi", quantity=1, unit_price_pkr=900)
    assert r.status_code == 200
    expected = _direct("add_item", name="prawn karahi", quantity=1, unit_price_pkr=900)
    assert r.json() == {"ok": False, "message": expected.message, "ended": False}
    assert expected.ok is False


def test_action_over_budget_is_a_200_refusal(client):
    sid = _new(client)
    r = _act(client, sid, "add_item", name="chicken biryani", quantity=5, unit_price_pkr=900)
    expected = _direct("add_item", name="chicken biryani", quantity=5, unit_price_pkr=900)
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["message"] == expected.message


def test_action_bad_arguments_refused(client):
    sid = _new(client)
    r = _act(client, sid, "add_item", name="chicken biryani", quantity="two")
    assert r.status_code == 200
    assert r.json()["ok"] is False and r.json()["message"].startswith("Refused: ")


def test_action_unknown_tool_422(client):
    sid = _new(client)
    r = _act(client, sid, "fly_to_moon")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_action_arguments_must_be_an_object(client):
    sid = _new(client)
    r = client.post(f"/sessions/{sid}/actions", json={"tool": "add_item", "arguments": [1]})
    assert r.status_code == 422


def test_action_unknown_session_404(client):
    r = _act(client, "f" * 32, "add_item", name="x", quantity=1)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "session_not_found"


def test_action_after_end_call_is_409(client):
    sid = _new(client)
    r = _act(client, sid, "end_call", outcome="not_ordered", reason="testing")
    assert r.status_code == 200
    assert r.json()["ok"] is True and r.json()["ended"] is True
    r2 = _act(client, sid, "add_item", name="chicken biryani", quantity=1, unit_price_pkr=900)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "session_closed"


# --- POST /sessions/{id}/transcript (T041)

def _line(client, sid, **body):
    return client.post(f"/sessions/{sid}/transcript", json=body)


def test_transcript_204_and_counts(client):
    sid = _new(client)
    r = _line(client, sid, role="restaurant", text="Hello, Karachi Kitchen")
    assert r.status_code == 204 and r.content == b""
    _line(client, sid, role="agent", text="Hi, a delivery order please")
    assert client.get(f"/sessions/{sid}").json()["transcript_lines"] == 2


@pytest.mark.parametrize("body", [{"role": "agent", "text": "  "}, {"role": "customer", "text": "hi"}, {"role": "agent"}])
def test_transcript_422(client, body):
    sid = _new(client)
    assert _line(client, sid, **body).status_code == 422


def test_transcript_unknown_404(client):
    assert _line(client, "a" * 32, role="agent", text="hi").status_code == 404


def test_transcript_closed_409(client):
    sid = _new(client)
    _act(client, sid, "end_call", outcome="not_ordered", reason="testing")
    r = _line(client, sid, role="agent", text="hi")
    assert r.status_code == 409 and r.json()["error"]["code"] == "session_closed"


# --- end, report, delete (T042)

def _order_and_end(client, sid):
    assert _act(client, sid, "add_item", name="chicken biryani", quantity=2, unit_price_pkr=900).json()["ok"]
    assert _act(client, sid, "set_fees", delivery_fee_pkr=150, tax_pkr=0).json()["ok"]
    assert _act(client, sid, "confirm_order", quoted_total_pkr=1950, delivery_minutes=45).json()["ok"]
    r = _act(client, sid, "end_call", outcome="ordered", reason="order placed")
    assert r.json()["ended"] is True


def test_end_live_session_writes_dropped_report(client, reports_dir):
    sid = _new(client)
    r = client.post(f"/sessions/{sid}/end", json={})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"report", "summary", "report_path"}
    assert body["report"]["outcome"] == "call_dropped"
    assert body["report"]["reason"] == "call ended without end_call"
    assert not Path(body["report_path"]).is_absolute()
    assert (reports_dir / body["report_path"]).is_file()
    assert body["summary"].startswith("The call dropped")
    assert client.get(f"/sessions/{sid}/report").json() == body
    assert client.get(f"/sessions/{sid}").json()["state"] == "ended"


def test_end_without_body_and_idempotent(client, reports_dir):
    sid = _new(client)
    first = client.post(f"/sessions/{sid}/end")
    second = client.post(f"/sessions/{sid}/end", json={})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(list(reports_dir.rglob("*.json"))) == 1


def test_end_after_end_call_returns_existing_report(client, reports_dir):
    sid = _new(client)
    _order_and_end(client, sid)
    r = client.post(f"/sessions/{sid}/end", json={})
    assert r.json()["report"]["outcome"] == "ordered"
    assert len(list(reports_dir.rglob("*.json"))) == 1


def test_report_not_ready_while_live(client):
    sid = _new(client)
    r = client.get(f"/sessions/{sid}/report")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "report_not_ready"


def test_report_after_end_call_is_ordered(client):
    sid = _new(client)
    _order_and_end(client, sid)
    r = client.get(f"/sessions/{sid}/report")
    assert r.status_code == 200
    assert r.json()["report"]["outcome"] == "ordered"
    assert r.json()["summary"].startswith("The call ended with the order placed")
    assert client.get(f"/sessions/{sid}").json()["report_ready"] is True


def test_delete_live_session_writes_report_first(client, reports_dir):
    sid = _new(client)
    r = client.delete(f"/sessions/{sid}")
    assert r.status_code == 204
    reports = list(reports_dir.rglob("*.json"))
    assert len(reports) == 1 and '"call_dropped"' in reports[0].read_text(encoding="utf-8")
    assert client.get(f"/sessions/{sid}").status_code == 404


def test_delete_ended_session_writes_no_second_report(client, reports_dir):
    sid = _new(client)
    _order_and_end(client, sid)
    assert client.delete(f"/sessions/{sid}").status_code == 204
    assert len(list(reports_dir.rglob("*.json"))) == 1


@pytest.mark.parametrize("method,path", [("post", "end"), ("get", "report"), ("delete", "")])
def test_end_report_delete_unknown_404(client, method, path):
    url = "/sessions/" + "9" * 32 + ("/" + path if path else "")
    r = getattr(client, method)(url)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "session_not_found"
