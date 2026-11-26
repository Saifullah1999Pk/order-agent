import re
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from order_agent.controller import CallController
from order_agent.heads.http_api.schemas import ActionRequest, StartSession, TranscriptRequest
from order_agent.heads.http_api.store import NotFound, SessionStore, TooManySessions
from order_agent.model.brief import load_brief

BRIEF_PATH = Path(__file__).resolve().parent.parent / "briefs" / "example.yaml"
NOW = datetime(2026, 11, 23, 19, 30)


@pytest.fixture
def brief():
    return load_brief(BRIEF_PATH)


def test_create_returns_hex_id_and_controller(brief, tmp_path):
    store = SessionStore()
    sid, ctrl = store.create(brief, reports_dir=tmp_path, now=NOW)
    assert re.fullmatch(r"[0-9a-f]{32}", sid)
    assert isinstance(ctrl, CallController)
    assert store.get(sid) is ctrl
    assert store.count() == 1


def test_get_unknown_raises_not_found():
    with pytest.raises(NotFound):
        SessionStore().get("nope")


def test_delete_removes(brief, tmp_path):
    store = SessionStore()
    sid, _ = store.create(brief, reports_dir=tmp_path, now=NOW)
    store.delete(sid)
    assert store.count() == 0
    with pytest.raises(NotFound):
        store.get(sid)
    with pytest.raises(NotFound):
        store.delete(sid)


def test_two_creates_are_independent(brief, tmp_path):
    store = SessionStore()
    a_id, a = store.create(brief, reports_dir=tmp_path, now=NOW)
    b_id, b = store.create(brief, reports_dir=tmp_path, now=NOW)
    assert a_id != b_id
    assert a is not b
    assert a.session is not b.session
    assert store.lock(a_id) is not store.lock(b_id)


def test_cap_raises_too_many_sessions(brief, tmp_path):
    store = SessionStore(max_sessions=2)
    store.create(brief, reports_dir=tmp_path, now=NOW)
    sid, _ = store.create(brief, reports_dir=tmp_path, now=NOW)
    with pytest.raises(TooManySessions):
        store.create(brief, reports_dir=tmp_path, now=NOW)
    store.delete(sid)
    store.create(brief, reports_dir=tmp_path, now=NOW)  # room again


def test_default_cap_is_100():
    assert SessionStore().max_sessions == 100


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_blank_transcript_text_rejected(text):
    with pytest.raises(ValidationError):
        TranscriptRequest(role="agent", text=text)


def test_bad_transcript_role_rejected():
    with pytest.raises(ValidationError):
        TranscriptRequest(role="customer", text="hi")
    assert TranscriptRequest(role="restaurant", text="hi").role == "restaurant"


def test_start_session_needs_exactly_one_brief_field():
    with pytest.raises(ValidationError):
        StartSession()
    with pytest.raises(ValidationError):
        StartSession(brief_name="example", brief={"customer_name": "x"})
    assert StartSession(brief_name="example").brief_name == "example"


def test_start_session_brief_name_pattern():
    for bad in ("../x", "a/b", "a.b", ""):
        with pytest.raises(ValidationError):
            StartSession(brief_name=bad)


def test_start_session_validates_inline_brief():
    with pytest.raises(ValidationError):
        StartSession(brief={"customer_name": "x"})


def test_action_request_requires_object_arguments():
    assert ActionRequest(tool="add_item", arguments={"name": "x"}).arguments == {"name": "x"}
    with pytest.raises(ValidationError):
        ActionRequest(tool="add_item", arguments=[1])
