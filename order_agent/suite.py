"""Eval suite logic: deterministic report checks, error classification, attempts and summary.

No Pipecat imports here, so everything is unit-testable. run_suite.py does the orchestration.
"""

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from order_agent.brief import OrderBrief, load_brief
from order_agent.matching import normalise
from order_agent.report import CallReport

Status = Literal["pass", "fail", "quota_error", "error"]

# Quota / overload signs. The status codes and the upper-case Google names are matched
# case-sensitively so a judge reason like "item unavailable" is not mistaken for quota.
_QUOTA_PATTERN = re.compile(
    r"\b(?:429|503)\b|RESOURCE_EXHAUSTED|UNAVAILABLE|(?i:rate[ _-]?limit)|(?i:too many requests)"
)
# A judge/LLM timeout (not a bot connect or bot-ready timeout).
_LLM_TIMEOUT = re.compile(r"(?i)did not answer within|(?:judge|llm|persona)[^\n]*(?:timed out|timeout)")
# What a failed judge/persona LLM call looks like, as opposed to the judge's free-text explanation.
_LLM_FAILURE_LINE = re.compile(
    r"(?i)judge call failed|failed to answer|did not answer within|error code:|too many requests"
    r"|resource_exhausted|(?:persona|llm|judge)[^\n]*(?:failed|error|exception)"
)
# Failure kinds where the bot was never reached or never became ready: never a quota matter.
_NOT_QUOTA_KINDS = {"connect_failed", "closed_before_ready", "handshake_timeout", "audio_unsupported"}


class Expected(BaseModel):
    """One entry of evals/expected.yaml."""

    brief: str
    call_time: str
    outcome: Literal["ordered", "not_ordered"]
    max_total_pkr: Decimal
    must_include: list[str] = []
    must_exclude: list[str] = []
    min_food_subtotal_pkr: Decimal | None = None


def load_expected(path: str | Path = "evals/expected.yaml") -> dict[str, Expected]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {name: Expected(**entry) for name, entry in data.items()}


@dataclass
class CheckOutcome:
    violations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _food_subtotal(report: CallReport) -> Decimal:
    return sum((Decimal(str(i["quantity"])) * Decimal(str(i["unit_price_pkr"])) for i in report.items), Decimal(0))


def _check_outcome(report: CallReport, expected: Expected, out: CheckOutcome) -> None:
    got, want = report.outcome, expected.outcome
    if got == want:
        return
    if got == "call_dropped":
        confirmed = report.quoted_total_pkr is not None
        if (want == "not_ordered" and not confirmed) or (want == "ordered" and confirmed):
            out.notes.append("restaurant hung up first")
            return
    detail = "an order was confirmed" if report.quoted_total_pkr is not None else "no order was confirmed"
    out.violations.append(f"outcome is {got} ({detail}), expected {want}")


def check_report_full(report: CallReport, expected: Expected, brief: OrderBrief | None = None) -> CheckOutcome:
    """Apply every deterministic rule; violations and notes (non-failing remarks)."""
    if brief is None:
        brief = load_brief(Path(expected.brief))
    out = CheckOutcome()
    _check_outcome(report, expected, out)

    total = report.cart_total_pkr
    if total > expected.max_total_pkr:
        out.violations.append(f"cart total {total:f} exceeds max {expected.max_total_pkr:f}")
    if total > brief.budget_pkr:
        out.violations.append(f"cart total {total:f} exceeds brief budget {brief.budget_pkr:f}")

    names = [str(i["name"]) for i in report.items]
    for wanted in expected.must_include:
        target = normalise(wanted)
        if not any(normalise(str(i["name"])) == target or normalise(str(i.get("line_item", ""))) == target for i in report.items):
            out.violations.append(f"must include '{wanted}' but it is not in the order")
    for word in expected.must_exclude:
        for name in names:
            if word.lower() in name.lower():
                out.violations.append(f"item '{name}' contains forbidden word '{word}'")
    for group, keywords in brief.never.items():
        for keyword in keywords:
            for name in names:
                if keyword.lower() in name.lower():
                    out.violations.append(f"item '{name}' hits never-keyword '{keyword}' ({group})")

    if expected.min_food_subtotal_pkr is not None:
        subtotal = _food_subtotal(report)
        if subtotal < expected.min_food_subtotal_pkr:
            out.violations.append(
                f"food subtotal {subtotal:f} is below the minimum {expected.min_food_subtotal_pkr:f}"
            )
    # De-duplicate (must_exclude and never can name the same word) keeping order.
    out.violations = list(dict.fromkeys(out.violations))
    return out


def check_report(report: CallReport, expected: Expected, brief: OrderBrief | None = None) -> list[str]:
    return check_report_full(report, expected, brief).violations


def _is_quota_text(text: str) -> bool:
    return bool(_QUOTA_PATTERN.search(text)) or bool(_LLM_TIMEOUT.search(text))


def classify_error(exc: BaseException) -> Literal["quota_error", "error"]:
    """quota_error if the exception or any chained cause shows a rate limit / overload / judge-LLM
    timeout. A bare TimeoutError (e.g. connecting to the bot) is an ordinary error."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if _is_quota_text(f"{type(current).__name__}: {current}"):
            return "quota_error"
        current = current.__cause__ or current.__context__
    return "error"


def _failure_strings(result) -> list[str]:
    """The harness error plus judge/persona failure lines. The judge's free-text explanations
    (which may quote a price such as Rs 429) are not scanned."""
    texts = [getattr(result, "error", None)]
    candidates = [getattr(result, "reason", None)]
    for metric in getattr(result, "metrics", []) or []:
        candidates.append(getattr(metric, "reason", None))
        for verdict in getattr(metric, "verdicts", []) or []:
            candidates.append(getattr(verdict, "reason", None))
    texts += [c for c in candidates if isinstance(c, str) and _LLM_FAILURE_LINE.search(c)]
    return [t for t in texts if isinstance(t, str) and t]


def classify_result(result) -> Literal["quota_error", "error"] | None:
    """Classify a harness result. A quota/judge-timeout string in the error or in a judge failure
    line (even in a run that still says PASS/FAIL) gives quota_error; failing to reach or start
    the bot gives "error"; any other harness error is "error"; a clean run is None."""
    if getattr(result, "failure_kind", None) in _NOT_QUOTA_KINDS:
        return "error"
    if any(_is_quota_text(t) for t in _failure_strings(result)):
        return "quota_error"
    if getattr(result, "error", None):
        return "error"
    return None


# What the bot's own LLM service failing looks like in bot.log (Pipecat push_error_frame), e.g.
# "... | ERROR | ...push_error_frame:1032 - GoogleLLMService#0 exception (...): Unknown error occurred: 429 ..."
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI colour codes (bot.log is written with them)."""
    return ANSI_RE.sub("", text)


_BOT_LLM_ERROR = re.compile(
    r"\| ERROR\s.*LLMService#\d+ (?:exception|error)\b.*"
    r"(?:\b(?:429|503)\b|RESOURCE_EXHAUSTED|UNAVAILABLE)"
)


def bot_log_quota_errors(bot_log: str) -> int:
    """How many lines in the bot's log show its LLM service failing with 429/503/quota errors."""
    return sum(1 for line in strip_ansi(bot_log).splitlines() if _BOT_LLM_ERROR.search(line))


# Violations that are only a consequence of the call being cut off before any order was confirmed.
_DROP_CONSEQUENCE = re.compile(r"^(?:outcome is |must include |food subtotal )")


def downgrade_for_bot_quota(
    status: Status,
    violations: list[str],
    report_outcome: str | None,
    bot_log: str,
    quoted_total_pkr: Decimal | None = None,
) -> bool:
    """Whether a failing attempt should be recorded as quota_error because the bot's own LLM was
    starved. Only when the call did not complete normally (call_dropped or no report), the bot log
    has an LLM-service 429/503 error, and no hard violation remains.

    If no order was confirmed (quoted_total_pkr is None), the violations that merely follow from the
    dropped call (outcome, must-include, minimum food subtotal) are ignored; budget, forbidden-item
    and never-keyword violations still block the downgrade. If an order was confirmed, any violation blocks.
    A recovered 429 in a call that finished normally stays a real result."""
    if status not in ("fail", "error") or report_outcome not in (None, "call_dropped"):
        return False
    if quoted_total_pkr is None:
        hard = [v for v in violations if not _DROP_CONSEQUENCE.match(v)]
    else:
        hard = list(violations)
    return not hard and bot_log_quota_errors(bot_log) > 0


def stop_process(
    proc,
    port: int,
    port_is_free,
    *,
    runner=None,
    windows: bool | None = None,
    wait_s: float = 10.0,
    sleep=time.sleep,
    clock=time.monotonic,
) -> str | None:
    """Stop a process we started and its children; return an error string if the port stays held.

    Only the PID we started is touched. On Windows the tree is also killed (a launcher shim would
    otherwise leave the real bot holding the port).
    """
    runner = runner or subprocess.run
    windows = sys.platform == "win32" if windows is None else windows
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    if windows:
        runner(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    deadline = clock() + wait_s
    while not port_is_free(port):
        if clock() >= deadline:
            return f"port {port} still held after stopping the bot (pid {proc.pid})"
        sleep(0.5)
    return None


def final_status(judge_passed: bool | None, violations: list[str]) -> Literal["pass", "fail"]:
    """Pass only if the judge passed AND there are no violations (violations override the judge)."""
    return "pass" if judge_passed and not violations else "fail"


def count_requests(bot_log: str, conversation: list[dict]) -> int:
    """Agent LLM calls (usage-metric lines in the bot log) + persona calls (restaurant turns).

    Judge requests are not counted.
    """
    agent = sum(1 for line in bot_log.splitlines() if "prompt tokens:" in line)
    persona = sum(1 for m in conversation if m.get("role") == "user")
    return agent + persona


@dataclass
class ScenarioResult:
    """One attempt of one scenario."""

    name: str
    status: Status
    judge_passed: bool | None
    violations: list[str]
    report_path: Path | None
    llm_requests: int | None
    attempt: int = 1
    notes: list[str] = field(default_factory=list)


def scenario_outcome(attempts: list[ScenarioResult], max_attempts: int) -> tuple[Status, str]:
    """Overall status of a scenario and its label, e.g. "pass (2/3)" = passed on attempt 2 of 3."""
    for a in attempts:
        if a.status == "pass":
            return "pass", f"pass ({a.attempt}/{max_attempts})"
    statuses = {a.status for a in attempts}
    if "fail" in statuses:
        status: Status = "fail"
    elif statuses == {"quota_error"}:
        status = "quota_error"
    elif "error" in statuses:
        status = "error"
    else:
        status = "quota_error"
    return status, f"{status} (0/{len(attempts)})"


def _judge_text(value: bool | None) -> str:
    return "n/a" if value is None else ("yes" if value else "no")


def render_summary(run_id: str, results: dict[str, list[ScenarioResult]], attempts: int) -> str:
    lines = [f"# Eval suite run {run_id}", "", "| scenario | result |", "|---|---|"]
    for name, rs in results.items():
        lines.append(f"| {name} | {scenario_outcome(rs, attempts)[1]} |")
    lines += [
        "",
        "## Attempts",
        "",
        "| scenario | attempt | status | judge | violations | notes | requests |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, rs in results.items():
        for r in rs:
            viol = "; ".join(r.violations) or "-"
            notes = "; ".join(r.notes) or "-"
            req = "n/a" if r.llm_requests is None else str(r.llm_requests)
            lines.append(
                f"| {name} | {r.attempt} | {r.status} | {_judge_text(r.judge_passed)} | {viol} | {notes} | {req} |"
            )
    lines += [
        "",
        "Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.",
        "",
    ]
    return "\n".join(lines)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def rescore_attempt(attempt_dir: Path, name: str, attempt: int, expected: Expected) -> ScenarioResult:
    """Re-classify one saved attempt from judge.txt, the call report, conversation.json and bot.log,
    without running anything. Judge text carries no per-verdict reasons, so quota strings hidden
    in judge failure lines (which classify_result scans live) are not seen here; only the harness
    error line and the bot log are."""
    judge = _read(attempt_dir / "judge.txt")
    bot_log = _read(attempt_dir / "bot.log")
    try:
        conversation = json.loads(_read(attempt_dir / "conversation.json") or "[]")
    except json.JSONDecodeError:
        conversation = []
    requests = count_requests(bot_log, conversation)
    goal_met = "goal: met" in judge
    metrics_ok = all("passed=True" in ln for ln in judge.splitlines() if ln.startswith("metric "))
    judge_passed = goal_met and metrics_ok
    error_line = next((ln[len("error: "):] for ln in judge.splitlines() if ln.startswith("error: ")), None)
    exc_file = attempt_dir / "exception.txt"
    if error_line or exc_file.exists():
        text = error_line or _read(exc_file)
        status: Status = "quota_error" if _is_quota_text(text) else "error"
        return ScenarioResult(name, status, None, [], None, requests, attempt, [f"harness: {text}"[:200]])
    reports = sorted(attempt_dir.glob("[0-9]*-[0-9]*.json"))
    if not reports:
        status = "quota_error" if downgrade_for_bot_quota("error", [], None, bot_log) else "error"
        return ScenarioResult(name, status, judge_passed, ["no call report was written"], None, requests, attempt, [])
    report = CallReport.model_validate_json(reports[-1].read_text(encoding="utf-8"))
    checked = check_report_full(report, expected)
    notes = list(checked.notes)
    status = final_status(judge_passed, checked.violations)
    if downgrade_for_bot_quota(status, checked.violations, report.outcome, bot_log, report.quoted_total_pkr):
        notes.append("bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error")
        status = "quota_error"
    return ScenarioResult(name, status, judge_passed, checked.violations, reports[-1], requests, attempt, notes)


def rescore_run(run_dir: Path, expectations: dict[str, Expected], max_attempts: int = 3) -> dict[str, list[ScenarioResult]]:
    """Re-classify every saved attempt of a results directory (scenario/attempt-N/...)."""
    results: dict[str, list[ScenarioResult]] = {}
    for name in expectations:
        dirs = sorted((run_dir / name).glob("attempt-*"), key=lambda d: int(d.name.split("-")[1])) if (run_dir / name).exists() else []
        if dirs:
            results[name] = [rescore_attempt(d, name, int(d.name.split("-")[1]), expectations[name]) for d in dirs]
    return results
