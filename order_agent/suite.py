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

Status = Literal["pass", "fail", "quota_error", "restaurant_error", "error"]

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
    # What the restaurant's persona says: unit price per orderable item, and the delivery fee / tax.
    # Optional so older expected files still load; when absent the price check is skipped.
    menu_pkr: dict[str, Decimal] | None = None
    fees_pkr: dict[str, Decimal] | None = None


def load_expected(path: str | Path = "evals/expected.yaml") -> dict[str, Expected]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {name: Expected(**entry) for name, entry in data.items()}


@dataclass
class CheckOutcome:
    violations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _has_unpriced(report: CallReport) -> bool:
    return any(i.get("unit_price_pkr") is None for i in report.items)


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


def _check_prices(report: CallReport, expected: Expected, out: CheckOutcome) -> None:
    """Prices and fees in the report must be what the restaurant's menu says (fail-safe: any
    unreadable value or unknown item is a violation)."""
    if expected.menu_pkr is not None:
        menu = {normalise(k): (k, v) for k, v in expected.menu_pkr.items()}
        for entry in report.items:
            if entry.get("unit_price_pkr") is None:
                continue  # the restaurant gave no price for this item: nothing to compare
            name = str(entry.get("name", ""))
            hit = menu.get(normalise(name))
            if hit is None:
                out.violations.append(f"item '{name}' is not on the menu")
                continue
            try:
                got = Decimal(str(entry["unit_price_pkr"]))
            except Exception:  # noqa: BLE001 - missing or unreadable price
                out.violations.append(f"price for {name} could not be read")
                continue
            if got != hit[1]:
                out.violations.append(f"price for {name} was {got:f}, menu says {hit[1]:f}")
    if expected.fees_pkr is not None and report.fees_set:
        confirmed = report.quoted_total_pkr is not None
        for key, label, got in (("delivery", "delivery fee", report.delivery_fee_pkr), ("tax", "tax", report.tax_pkr)):
            want = expected.fees_pkr.get(key)
            if want is None or got == want:
                continue
            # A call that never recorded fees leaves them at 0; only a confirmed order must have them right.
            if got == 0 and not confirmed:
                continue
            out.violations.append(f"{label} was {got:f}, menu says {want:f}")


def check_report_full(report: CallReport, expected: Expected, brief: OrderBrief | None = None) -> CheckOutcome:
    """Apply every deterministic rule; violations and notes (non-failing remarks)."""
    if brief is None:
        brief = load_brief(Path(expected.brief))
    out = CheckOutcome()
    _check_outcome(report, expected, out)

    # When the cart total is unknown (unpriced items or fees never set) the restaurant's quoted total
    # is the only honest figure; with no quote either there is nothing to compare.
    total = report.cart_total_pkr if report.cart_total_pkr is not None else report.quoted_total_pkr
    label = "cart total" if report.cart_total_pkr is not None else "quoted total"
    if total is not None and total > expected.max_total_pkr:
        out.violations.append(f"{label} {total:f} exceeds max {expected.max_total_pkr:f}")
    if total is not None and total > brief.budget_pkr:
        out.violations.append(f"{label} {total:f} exceeds brief budget {brief.budget_pkr:f}")

    names = [str(i["name"]) for i in report.items]
    for wanted in expected.must_include:
        target = normalise(wanted)
        if not any(normalise(str(i["name"])) == target or normalise(str(i.get("line_item", ""))) == target for i in report.items):
            out.violations.append(f"must include '{wanted}' but it is not in the order")
    for word in expected.must_exclude:
        word_set = normalise(word)
        for name in names:
            if word_set and word_set <= normalise(name):
                out.violations.append(f"item '{name}' contains forbidden word '{word}'")
    for group, keywords in brief.never.items():
        for keyword in keywords:
            kw_set = normalise(keyword)
            for name in names:
                if kw_set and kw_set <= normalise(name):
                    out.violations.append(f"item '{name}' hits never-keyword '{keyword}' ({group})")

    if expected.min_food_subtotal_pkr is not None and not _has_unpriced(report):
        subtotal = _food_subtotal(report)
        if subtotal < expected.min_food_subtotal_pkr:
            out.violations.append(
                f"food subtotal {subtotal:f} is below the minimum {expected.min_food_subtotal_pkr:f}"
            )
    _check_prices(report, expected, out)
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


def harness_status_with_report(harness: Status, report: CallReport | None, expected: Expected) -> Status:
    """A harness-classified quota_error stays quota_error only if the call report, when there is
    one, shows no real violation. Drop consequences are ignored when no order was confirmed;
    anything else (budget, forbidden item, ...) makes it a fail whatever the quota state."""
    if harness != "quota_error" or report is None:
        return harness
    violations = check_report_full(report, expected).violations
    if report.quoted_total_pkr is None:
        violations = [v for v in violations if not _DROP_CONSEQUENCE.match(v)]
    return "fail" if violations else harness


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


_QUOTE_MISMATCH = re.compile(r"the restaurant quoted (\d+(?:\.\d+)?) PKR but the cart total is (\d+(?:\.\d+)?) PKR")
# Violations that mean the bot's cart does not match the menu (prices, fees, unknown items).
_PRICE_VIOLATION = re.compile(r"^(?:price for |item '.*' is not on the menu|delivery fee was |tax was )")


_TOTALS_LINE = re.compile(
    r"Totals \(Rs, delivery included\): (?P<body>.+?)\. When you quote a total, use these exact figures; never add it up yourself\."
)
SCENARIO_DIR = Path(__file__).resolve().parent.parent / "evals" / "scenarios"


def persona_totals(name: str, scenario_dir: Path = SCENARIO_DIR) -> set[Decimal]:
    """Every figure on the scenario persona's Totals line (the totals of the valid orders)."""
    text = (scenario_dir / f"{name}.yaml").read_text(encoding="utf-8")
    text = text.replace("!include ../simulator.yaml", "x").replace("!include ../judge.yaml", "x")
    persona = " ".join(yaml.safe_load(text)["scenarios"][0]["persona"].split())
    match = _TOTALS_LINE.search(persona)
    return {Decimal(m) for m in re.findall(r"= (\d+)", match["body"])} if match else set()


def _wrong_quotes(report: CallReport) -> list[Decimal]:
    """Quoted totals of every refused confirm_order whose quote differed from the cart total."""
    quotes = []
    for event in report.tool_events:
        if event.get("tool") == "confirm_order" and event.get("ok") is False:
            m = _QUOTE_MISMATCH.search(str(event.get("message", "")))
            if m and Decimal(m.group(1)) != Decimal(m.group(2)):
                quotes.append(Decimal(m.group(1)))
    return quotes


def _bent_cart(report: CallReport) -> bool:
    return any(
        e.get("tool") in ("add_item", "set_fees") and (e.get("args") or {}).get("price_corrected" if e["tool"] == "add_item" else "corrected")
        for e in report.tool_events
    )


def _menu_total(report: CallReport, expected: Expected) -> Decimal | None:
    """The bot's cart priced from the menu plus the menu fees; None if the cart does not match the
    menu exactly (unknown item, wrong unit price, wrong fee or tax; no zero-fee exemption)."""
    if expected.menu_pkr is None or expected.fees_pkr is None or _has_unpriced(report) or not report.fees_set:
        return None
    menu = {normalise(k): v for k, v in expected.menu_pkr.items()}
    total = Decimal(0)
    for entry in report.items:
        price = menu.get(normalise(str(entry.get("name", ""))))
        try:
            if price is None or Decimal(str(entry["unit_price_pkr"])) != price:
                return None
            total += Decimal(str(entry["quantity"])) * price
        except Exception:  # noqa: BLE001 - unreadable value
            return None
    if report.delivery_fee_pkr != expected.fees_pkr.get("delivery", Decimal(0)) or report.tax_pkr != expected.fees_pkr.get("tax", Decimal(0)):
        return None
    return total + report.delivery_fee_pkr + report.tax_pkr


def conduct_passed(metrics) -> bool:
    """True only if a metric named "conduct" is present and every such metric passed (a missing one
    is not a pass). `metrics` is an iterable of (name, passed)."""
    results = [passed for name, passed in metrics if name == "conduct"]
    return bool(results) and all(results)


def settle_status(
    status: Status,
    report: CallReport,
    checked: CheckOutcome,
    expected: Expected,
    valid_totals: set[Decimal],
    conduct_ok: bool = False,
) -> tuple[Status, list[str]]:
    """Relabel a would-be fail as restaurant_error ONLY when every condition holds:
    a) the cart matches the menu exactly (unit prices, delivery fee and tax; no zero-fee exemption)
       and the bot never used a correction flag;
    b) every refused confirm_order quote differs from the menu-correct total of that cart;
    c) no such quote is a figure on the scenario's persona Totals line (a quote matching a valid
       order may be right about a different order: ambiguous, stays fail);
    d) the judge's conduct metric is present and passed (missing counts as not passed);
    e) no order was confirmed and the only violations are consequences of there being no order.
    Anything else, and every ambiguous case, stays whatever it was (a bot failure)."""
    notes = list(checked.notes)
    if status != "fail" or not conduct_ok or report.quoted_total_pkr is not None or report.total_only or _has_unpriced(report) or _bent_cart(report):
        return status, notes
    quotes = _wrong_quotes(report)
    correct = _menu_total(report, expected)
    if not quotes or correct is None:
        return status, notes
    if any(q == correct or q in valid_totals for q in quotes):
        return status, notes
    if not any(v.startswith("outcome is ") for v in checked.violations):
        return status, notes
    if any(not _DROP_CONSEQUENCE.match(v) for v in checked.violations):  # budget, forbidden item, price violations, ...
        return status, notes
    notes.append(f"restaurant quoted Rs {quotes[0]:f}, which matches no valid order (correct for this cart: Rs {correct:f}); bot declined")
    return "restaurant_error", notes


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
    elif statuses <= {"quota_error", "restaurant_error"} and "restaurant_error" in statuses:
        status = "restaurant_error"
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
        harness_reports = sorted(attempt_dir.glob("[0-9]*-[0-9]*.json"))
        if status == "quota_error" and harness_reports:
            rep = CallReport.model_validate_json(harness_reports[-1].read_text(encoding="utf-8"))
            if harness_status_with_report(status, rep, expected) == "fail":
                return ScenarioResult(name, "fail", None, check_report_full(rep, expected).violations, harness_reports[-1], requests, attempt, [f"harness: {text}"[:200]])
        return ScenarioResult(name, status, None, [], None, requests, attempt, [f"harness: {text}"[:200]])
    reports = sorted(attempt_dir.glob("[0-9]*-[0-9]*.json"))
    if not reports:
        status = "quota_error" if downgrade_for_bot_quota("error", [], None, bot_log) else "error"
        return ScenarioResult(name, status, judge_passed, ["no call report was written"], None, requests, attempt, [])
    report = CallReport.model_validate_json(reports[-1].read_text(encoding="utf-8"))
    checked = check_report_full(report, expected)
    status = final_status(judge_passed, checked.violations)
    conduct = conduct_passed(
        (ln.split()[1].rstrip(":"), "passed=True" in ln) for ln in judge.splitlines() if ln.startswith("metric ")
    )
    status, notes = settle_status(status, report, checked, expected, persona_totals(name), conduct)
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
