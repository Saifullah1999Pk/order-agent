"""Eval suite logic: deterministic report checks, error classification, attempts and summary.

No Pipecat imports here, so everything is unit-testable. run_suite.py does the orchestration.
"""

import re
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
    r"\b(?:429|503)\b|RESOURCE_EXHAUSTED|UNAVAILABLE|(?i:rate[ _-]?limit)"
    r"|(?i:did not answer within)|(?i:timed out)|(?i:timeout)"
)


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
    return bool(_QUOTA_PATTERN.search(text))


def classify_error(exc: BaseException) -> Literal["quota_error", "error"]:
    """quota_error if the exception or any chained cause shows a rate limit / overload / timeout."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, TimeoutError) or _is_quota_text(f"{type(current).__name__}: {current}"):
            return "quota_error"
        current = current.__cause__ or current.__context__
    return "error"


def _result_strings(result) -> list[str]:
    texts = [getattr(result, "error", None), getattr(result, "reason", None)]
    for metric in getattr(result, "metrics", []) or []:
        texts.append(getattr(metric, "reason", None))
        for verdict in getattr(metric, "verdicts", []) or []:
            texts.append(getattr(verdict, "reason", None))
    return [t for t in texts if isinstance(t, str) and t]


def classify_result(result) -> Literal["quota_error", "error"] | None:
    """Classify a harness result. Quota strings anywhere (even in per-metric judge lines of a
    run that still says PASS/FAIL) win; else a harness error is "error"; else None."""
    texts = _result_strings(result)
    if any(_is_quota_text(t) for t in texts):
        return "quota_error"
    if getattr(result, "error", None):
        return "error"
    return None


_BOT_QUOTA = re.compile(r"\b(?:429|503)\b|RESOURCE_EXHAUSTED|UNAVAILABLE|(?i:rate[ _-]?limit)")


def bot_log_quota_errors(bot_log: str) -> int:
    """How many error lines in the bot's own log show its LLM being rate limited or overloaded."""
    return sum(
        1
        for line in bot_log.splitlines()
        if re.search(r"(?i)error|exception|fail", line) and _BOT_QUOTA.search(line)
    )


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
