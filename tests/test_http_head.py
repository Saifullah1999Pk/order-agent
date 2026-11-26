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
