from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from order_agent.report import CallReport
from order_agent.suite import (
    Expected,
    ScenarioResult,
    check_report,
    check_report_full,
    classify_error,
    bot_log_quota_errors,
    downgrade_for_bot_quota,
    classify_result,
    count_requests,
    final_status,
    load_expected,
    render_summary,
    scenario_outcome,
    stop_process,
)

NOW = datetime(2026, 11, 23, 19, 30)
END = datetime(2026, 11, 23, 19, 36)


def make_report(outcome="ordered", total="1950", quoted="1950", items=None, **extra) -> CallReport:
    if items is None:
        items = [
            {
                "name": "chicken biryani",
                "line_item": "chicken biryani",
                "quantity": "2",
                "unit_price_pkr": "900",
            }
        ]
    data = dict(
        outcome=outcome,
        reason="x",
        items=items,
        delivery_fee_pkr=Decimal("150"),
        tax_pkr=Decimal("0"),
        cart_total_pkr=Decimal(total),
        quoted_total_pkr=None if quoted is None else Decimal(quoted),
        delivery_eta=None,
        tool_events=[],
        transcript=[],
        started_at=NOW,
        ended_at=END,
    )
    data.update(extra)
    return CallReport(**data)


def item(name, qty="1", price="900", line="chicken biryani"):
    return {"name": name, "line_item": line, "quantity": qty, "unit_price_pkr": price}


def happy(**over) -> Expected:
    data = dict(
        brief="evals/briefs/happy_path.yaml",
        call_time="2026-11-23T19:30:00",
        outcome="ordered",
        max_total_pkr=2500,
        must_include=["chicken biryani"],
        must_exclude=["seafood", "fish", "prawn", "jhinga", "beef"],
    )
    data.update(over)
    return Expected(**data)


def test_check_report_pass(brief):
    assert check_report(make_report(), happy(), brief) == []


def test_check_report_over_budget(brief):
    # max_total is looser than the brief budget (2500): the budget is still enforced.
    v = check_report(make_report(total="2600", quoted="2600"), happy(max_total_pkr=3000), brief)
    assert any("2600" in x for x in v)


def test_check_report_over_max_total(brief):
    v = check_report(make_report(total="2600", quoted="2600"), happy(), brief)
    assert any("2600" in x for x in v)


def test_check_report_wrong_outcome(brief):
    v = check_report(make_report(), happy(outcome="not_ordered", must_include=[]), brief)
    assert any("outcome" in x for x in v)


def test_check_report_missing_must_include(brief):
    r = make_report(items=[item("chicken karahi", "1", "1400")], total="1550", quoted="1550")
    v = check_report(r, happy(must_include=["chicken biryani", "raita"]), brief)
    assert any("raita" in x for x in v)
    assert not any("must include 'chicken biryani'" in x for x in v)


def test_check_report_forbidden_word(brief):
    r = make_report(items=[item("fish special")], total="1050", quoted="1050")
    v = check_report(r, happy(must_include=[]), brief)
    assert any("fish" in x for x in v)


def test_check_report_never_keyword_from_brief(brief):
    r = make_report(items=[item("jhinga masala")], total="1050", quoted="1050")
    v = check_report(r, happy(must_include=[], must_exclude=[]), brief)
    assert any("jhinga" in x for x in v)


def test_check_report_min_food_subtotal(brief):
    exp = happy(min_food_subtotal_pkr=2200)
    v = check_report(make_report(), exp, brief)  # 2 x 900 = 1800
    assert any("1800" in x and "2200" in x for x in v)
    items = [item("chicken biryani", "2", "900"), item("raita", "3", "150", line="raita")]
    ok = make_report(items=items, total="2400", quoted="2400")
    assert check_report(ok, exp, brief) == []


@pytest.mark.parametrize(
    "expected_outcome, outcome, quoted, ok, note",
    [
        ("not_ordered", "not_ordered", None, True, False),
        ("not_ordered", "call_dropped", None, True, True),
        ("not_ordered", "call_dropped", "1950", False, False),
        ("not_ordered", "ordered", "1950", False, False),
        ("ordered", "ordered", "1950", True, False),
        ("ordered", "call_dropped", "1950", True, True),
        ("ordered", "call_dropped", None, False, False),
        ("ordered", "not_ordered", None, False, False),
    ],
)
def test_outcome_with_call_dropped(brief, expected_outcome, outcome, quoted, ok, note):
    exp = happy(outcome=expected_outcome, must_include=[])
    out = check_report_full(make_report(outcome=outcome, quoted=quoted), exp, brief)
    if ok:
        assert out.violations == []
    else:
        assert any("outcome" in v for v in out.violations)
    assert any("hung up first" in n for n in out.notes) is note


def test_classify_error_quota():
    assert classify_error(Exception("503 UNAVAILABLE: model overloaded")) == "quota_error"
    try:
        try:
            raise RuntimeError("Error code: 429 - rate")
        except RuntimeError as inner:
            raise ValueError("wrapped") from inner
    except ValueError as outer:
        assert classify_error(outer) == "quota_error"
    assert classify_error(RuntimeError("RESOURCE_EXHAUSTED")) == "quota_error"
    assert classify_error(RuntimeError("Rate limit reached")) == "quota_error"
    assert classify_error(TimeoutError("judge call failed: did not answer within 10.0 s")) == "quota_error"
    assert classify_error(ValueError("boom")) == "error"


def _result(**kw):
    base = dict(error=None, reason="", metrics=[], succeeded=True, failure_kind=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_classify_result_finds_429_in_metric_lines_even_when_pass():
    verdict = SimpleNamespace(reason="OpenAILLMService#0 failed to answer: Error code: 429 - rate limited")
    metric = SimpleNamespace(reason="", verdicts=[verdict])
    assert classify_result(_result(metrics=[metric])) == "quota_error"


def test_classify_result_error_string_and_clean():
    assert classify_result(_result(error="persona call failed: Error code: 429")) == "quota_error"
    assert classify_result(_result(error="judge call failed: did not answer within 10.0 s")) == "quota_error"
    assert classify_result(_result(error="connect failed")) == "error"
    metric = SimpleNamespace(reason="polite", verdicts=[SimpleNamespace(reason="fine")])
    assert classify_result(_result(metrics=[metric])) is None


def test_final_status_violation_overrides_judge():
    assert final_status(True, ["total too high"]) == "fail"
    assert final_status(True, []) == "pass"
    assert final_status(False, []) == "fail"
    assert final_status(None, []) == "fail"


def test_count_requests():
    log = "x\nprompt tokens: 10\nnoise\nprompt tokens: 20\nprompt tokens: 30\n"
    conv = [
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "a"},
        {"role": "tool_call", "name": "n", "arguments": {}, "cancelled": False},
        {"role": "user", "content": "b"},
    ]
    assert count_requests(log, conv) == 5


def res(name, attempt, status, judge=None, violations=None, requests=None, notes=None):
    return ScenarioResult(
        name=name,
        attempt=attempt,
        status=status,
        judge_passed=judge,
        violations=violations or [],
        report_path=None,
        llm_requests=requests,
        notes=notes or [],
    )


def test_scenario_outcome():
    assert scenario_outcome([res("a", 1, "fail"), res("a", 2, "pass")], 3) == ("pass", "pass (2/3)")
    assert scenario_outcome([res("a", 1, "quota_error")] * 3, 3)[0] == "quota_error"
    assert scenario_outcome([res("a", 1, "quota_error"), res("a", 2, "fail")], 3)[0] == "fail"
    assert scenario_outcome([res("a", 1, "error")], 1)[0] == "error"


def test_render_summary_lists_every_attempt():
    text = render_summary(
        "run1",
        {
            "a": [
                res("a", 1, "fail", True, ["total 2600 too high"], 7, ["restaurant hung up first"]),
                res("a", 2, "pass", True, [], 9),
            ]
        },
        attempts=3,
    )
    assert "pass (2/3)" in text
    assert "total 2600 too high" in text
    assert "hung up first" in text
    assert "judge requests are not counted" in text.lower()


def test_load_expected_reads_real_file():
    exp = load_expected("evals/expected.yaml")
    assert exp["minimum_reachable"].min_food_subtotal_pkr == 2200
    assert exp["happy_path"].max_total_pkr == 2500
    assert len(exp) == 11


LLM_429 = (
    "2026-11-23 18:06:50.738 | ERROR    | pipecat.processors.frame_processor:push_error_frame:1032 - "
    "GoogleLLMService#0 exception (errors.py:301): Unknown error occurred: 429 Too Many Requests."
)


def test_bot_log_quota_errors_needs_llm_service_signature():
    assert bot_log_quota_errors(LLM_429) == 1
    assert bot_log_quota_errors("INFO | GoogleLLMService#0 got UNAVAILABLE") == 0  # not an ERROR line
    assert bot_log_quota_errors("2026 | ERROR    | x - total was Rs 503 quoted by the restaurant") == 0
    assert bot_log_quota_errors("prompt tokens: 429, completion tokens: 503") == 0


def test_downgrade_only_when_no_violations_and_call_did_not_complete():
    assert downgrade_for_bot_quota("fail", [], "call_dropped", LLM_429)
    assert downgrade_for_bot_quota("fail", [], None, LLM_429)
    # hard violations are real evidence
    assert not downgrade_for_bot_quota("fail", ["outcome is ordered, expected not_ordered"], "call_dropped", LLM_429)
    # a 429 that recovered: the call finished normally, the fail stays a fail
    assert not downgrade_for_bot_quota("fail", [], "ordered", LLM_429)
    assert not downgrade_for_bot_quota("fail", [], "not_ordered", LLM_429)
    # no LLM-service error in the log
    assert not downgrade_for_bot_quota("fail", [], "call_dropped", "ERROR | x - Rs 503")
    assert not downgrade_for_bot_quota("pass", [], "call_dropped", LLM_429)


def test_classify_result_excludes_bot_connection_failures():
    r = _result(error="could not connect: timed out", failure_kind="connect_failed")
    assert classify_result(r) == "error"
    r = _result(error="bot did not send bot-ready within 60s (timeout)", failure_kind="handshake_timeout")
    assert classify_result(r) == "error"
    assert classify_error(TimeoutError("connect timed out waiting for the bot")) == "error"


def test_classify_result_judge_failure_line_is_quota():
    r = _result(error="judge call failed: did not answer within 10.0 s")
    assert classify_result(r) == "quota_error"
    verdict = SimpleNamespace(reason="judge call failed: OpenAILLMService#0 failed to answer: Error code: 429")
    assert classify_result(_result(metrics=[SimpleNamespace(reason="", verdicts=[verdict])])) == "quota_error"


def test_classify_result_ignores_price_in_explainer_text():
    verdict = SimpleNamespace(reason="The restaurant quoted Rs 429 for the raita and the bot repeated it.")
    metric = SimpleNamespace(reason="Bot said Rs 503 total, which matches", verdicts=[verdict])
    assert classify_result(_result(metrics=[metric], reason="goal met: total Rs 429")) is None


class FakeProc:
    pid = 4242

    def __init__(self, alive=True):
        self.alive = alive
        self.calls = []

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.calls.append("terminate")
        self.alive = False

    def kill(self):
        self.calls.append("kill")
        self.alive = False

    def wait(self, timeout=None):
        self.calls.append("wait")


def test_stop_process_kills_tree_on_windows_and_checks_port():
    ran = []
    proc = FakeProc()
    err = stop_process(proc, 7860, lambda port: True, runner=lambda cmd, **kw: ran.append(cmd), windows=True)
    assert err is None
    assert proc.calls[0] == "terminate"
    assert ran == [["taskkill", "/T", "/F", "/PID", "4242"]]


def test_stop_process_no_taskkill_off_windows():
    ran = []
    stop_process(FakeProc(), 7860, lambda port: True, runner=lambda cmd, **kw: ran.append(cmd), windows=False)
    assert ran == []


def test_stop_process_reports_port_still_held():
    t = iter(range(0, 100))
    err = stop_process(
        FakeProc(alive=False), 7860, lambda port: False, runner=lambda *a, **k: None, windows=True,
        wait_s=3, sleep=lambda s: None, clock=lambda: next(t),
    )
    assert err and "7860" in err


def test_stop_process_waits_for_port_to_free():
    states = iter([False, False, True])
    err = stop_process(
        FakeProc(), 7860, lambda port: next(states), runner=lambda *a, **k: None, windows=False,
        sleep=lambda s: None,
    )
    assert err is None
