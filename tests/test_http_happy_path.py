"""SC-003: the happy_path order, scripted through the HTTP head only (no Pipecat, no speech)."""
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from order_agent.controller import CallController
from order_agent.heads.http_api.app import create_app
from order_agent.model.brief import load_brief
from order_agent.model.report import CallReport, build_report

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = yaml.safe_load((ROOT / "evals" / "expected.yaml").read_text(encoding="utf-8"))["happy_path"]


def test_happy_path_through_http(tmp_path):
    reports_dir = tmp_path / "reports"
    client = TestClient(create_app(reports_dir, brief_dir=ROOT / "evals" / "briefs"))
    sid = client.post("/sessions", json={"brief_name": "happy_path"}).json()["session_id"]
    menu = {k: Decimal(str(v)) for k, v in EXPECTED["menu_pkr"].items()}
    fees = EXPECTED["fees_pkr"]

    def act(tool, **arguments):
        r = client.post(f"/sessions/{sid}/actions", json={"tool": tool, "arguments": arguments})
        assert r.status_code == 200
        return r.json()

    client.post(f"/sessions/{sid}/transcript", json={"role": "restaurant", "text": "Karachi Kitchen, Bilal speaking."})
    client.post(f"/sessions/{sid}/transcript", json={"role": "agent", "text": "Hi, I'd like to order for delivery."})
    assert act("add_item", name="chicken biryani", quantity=2, unit_price_pkr=float(menu["chicken biryani"]))["ok"]
    assert act("add_item", name="raita", quantity=1, unit_price_pkr=float(menu["raita"]))["ok"]
    assert act("set_fees", delivery_fee_pkr=fees["delivery"], tax_pkr=fees["tax"])["ok"]
    total = 2 * menu["chicken biryani"] + menu["raita"] + fees["delivery"] + fees["tax"]
    assert act("confirm_order", quoted_total_pkr=float(total), delivery_minutes=45)["ok"]
    end = act("end_call", outcome=EXPECTED["outcome"], reason="order placed")
    assert end["ok"] and end["ended"]

    r = client.get(f"/sessions/{sid}/report")
    assert r.status_code == 200
    body = r.json()["report"]
    assert body["outcome"] == "ordered" == EXPECTED["outcome"]
    assert Decimal(body["quoted_total_pkr"]) == total <= EXPECTED["max_total_pkr"]
    assert Decimal(body["cart_total_pkr"]) == total
    assert Decimal(body["delivery_fee_pkr"]) == fees["delivery"]
    assert any("chicken biryani" in i["name"] for i in body["items"])
    assert len(body["transcript"]) == 2

    probe = CallController(load_brief(ROOT / "evals" / "briefs" / "happy_path.yaml"), reports_dir=tmp_path / "x")
    expected_keys = set(build_report(probe.session, "ordered", "r", [], datetime.now(), datetime.now()).model_dump().keys())
    assert set(body.keys()) == expected_keys
    assert CallReport.model_validate(body).outcome == "ordered"
    assert (reports_dir / r.json()["report_path"]).is_file()
