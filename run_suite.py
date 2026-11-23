"""Run the restaurant eval scenarios against a fresh bot per attempt.

    PYTHONIOENCODING=utf-8 uv run python run_suite.py [--only NAME[,NAME]] [--attempts 3] [--sleep 20] [--audio]

Uses Pipecat's Python API (EvalScenarioFile / EvalSession) rather than the `pipecat eval run` CLI:
the result object carries the judge verdict, harness errors and per-metric judge lines (needed to
spot quota errors hidden in a PASS/FAIL run) and the conversation, with no output parsing.
All decisions live in order_agent/suite.py; this file is orchestration only.

--audio only records conversation audio (EvalSessionParams.record_path); a scenario runs in audio
mode only if its YAML sets user/judge modality, and these scenarios are text mode.
"""

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from order_agent.report import CallReport
from order_agent.suite import (
    Expected,
    ScenarioResult,
    bot_log_quota_errors,
    check_report_full,
    classify_error,
    classify_result,
    count_requests,
    final_status,
    load_expected,
    render_summary,
    scenario_outcome,
)

ROOT = Path(__file__).parent.resolve()
READY_TIMEOUT_S = 150
REPORT_WAIT_S = 15


def port_free(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def pick_port() -> int:
    for port in (7860, 7861):
        if port_free(port):
            return port
    raise RuntimeError("ports 7860 and 7861 are both in use by other processes")


def wait_ready(port: int, proc: subprocess.Popen) -> bool:
    deadline = time.monotonic() + READY_TIMEOUT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/client/", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def start_bot(name: str, expected: Expected, attempt_dir: Path, port: int):
    env = dict(os.environ)
    env.update(
        ORDER_BRIEF=expected.brief,
        ORDER_CALL_TIME=expected.call_time,
        ORDER_REPORTS_DIR=str(attempt_dir),
        PYTHONIOENCODING="utf-8",
    )
    log = open(attempt_dir / "bot.log", "wb")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "bot.py"), "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return proc, log


def stop_bot(proc: subprocess.Popen, log) -> None:
    """Stop only the bot this run started."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    log.close()


def newest_report(attempt_dir: Path) -> Path | None:
    deadline = time.monotonic() + REPORT_WAIT_S
    while True:
        files = sorted(attempt_dir.glob("[0-9]*-[0-9]*.json"))
        if files or time.monotonic() >= deadline:
            return files[-1] if files else None
        time.sleep(0.5)


async def run_eval(name: str, port: int, attempt_dir: Path, audio: bool):
    from pipecat.evals.scenario import EvalScenarioFile
    from pipecat.evals.session import EvalSession, EvalSessionParams

    scenario = list(EvalScenarioFile.load(ROOT / "evals" / "scenarios" / f"{name}.yaml"))[0]
    record = str(attempt_dir / "audio.wav") if audio else None
    params = EvalSessionParams(record_path=record)
    session = EvalSession.from_scenario(scenario, f"ws://localhost:{port}/ws", params=params)
    result = await session.run()
    if getattr(result, "debug_log", None):
        (attempt_dir / "eval.log").write_text("\n".join(result.debug_log) + "\n", encoding="utf-8")
    (attempt_dir / "conversation.json").write_text(
        json.dumps(getattr(result, "conversation", []), indent=2) + "\n", encoding="utf-8"
    )
    return result


def judge_text(result) -> str:
    lines = [f"goal: {'met' if result.succeeded else 'not met'}: {result.reason}"]
    lines += [f"metric {m.name}: {m.score} passed={m.passed}" for m in result.metrics]
    if result.error:
        lines.append(f"error: {result.error}")
    return "\n".join(lines)


def run_attempt(name: str, attempt: int, expected: Expected, run_dir: Path, audio: bool) -> ScenarioResult:
    attempt_dir = run_dir / name / f"attempt-{attempt}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    proc = log = None
    try:
        port = pick_port()
        proc, log = start_bot(name, expected, attempt_dir, port)
        if not wait_ready(port, proc):
            return ScenarioResult(name, "error", None, ["bot did not become ready"], None, None, attempt, notes)
        try:
            result = asyncio.run(run_eval(name, port, attempt_dir, audio))
        except Exception as exc:  # noqa: BLE001
            (attempt_dir / "exception.txt").write_text(repr(exc), encoding="utf-8")
            return ScenarioResult(name, classify_error(exc), None, [f"{type(exc).__name__}: {exc}"][:1], None, None, attempt, notes)
        report_file = newest_report(attempt_dir)  # the bot writes it when the client disconnects
    finally:
        if proc is not None:
            stop_bot(proc, log)

    bot_log = (attempt_dir / "bot.log").read_text(encoding="utf-8", errors="replace")
    requests = count_requests(bot_log, result.conversation or [])
    (attempt_dir / "judge.txt").write_text(judge_text(result) + "\n", encoding="utf-8")

    harness = classify_result(result)
    if harness is not None:
        notes.append(f"harness: {result.error or 'quota string in judge/persona output'}"[:200])
        return ScenarioResult(name, harness, None, [], report_file, requests, attempt, notes)
    if report_file is None:
        return ScenarioResult(name, "error", result.passed, ["no call report was written"], None, requests, attempt, notes)

    report = CallReport.model_validate_json(report_file.read_text(encoding="utf-8"))
    checked = check_report_full(report, expected)
    notes += checked.notes
    status = final_status(result.passed, checked.violations)
    bot_quota = bot_log_quota_errors(bot_log)
    if bot_quota:
        notes.append(f"bot LLM quota/overload errors in bot.log: {bot_quota}")
        if status == "fail":
            status = "quota_error"  # the bot's own LLM was starved; not evidence about the bot's logic
    return ScenarioResult(name, status, result.passed, checked.violations, report_file, requests, attempt, notes)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="scenario name (comma-separated for several)")
    parser.add_argument("--audio", action="store_true", help="record conversation audio")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=20.0, help="seconds between attempts and scenarios")
    args = parser.parse_args()

    os.chdir(ROOT)
    load_dotenv()
    logger.remove()
    logger.add(sys.stderr, level="WARNING")  # keep the harness's DEBUG chatter out of the console
    expectations = load_expected(ROOT / "evals" / "expected.yaml")
    names = args.only.split(",") if args.only else list(expectations)
    unknown = [n for n in names if n not in expectations]
    if unknown:
        parser.error(f"unknown scenario(s): {unknown}")

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / "evals" / "results" / run_id
    run_dir.mkdir(parents=True)
    results: dict[str, list[ScenarioResult]] = {}

    for si, name in enumerate(names):
        results[name] = []
        for attempt in range(1, args.attempts + 1):
            print(f"[{name}] attempt {attempt}/{args.attempts}", flush=True)
            r = run_attempt(name, attempt, expectations[name], run_dir, args.audio)
            results[name].append(r)
            print(f"  -> {r.status} judge={r.judge_passed} violations={r.violations} notes={r.notes}", flush=True)
            (run_dir / "summary.md").write_text(render_summary(run_id, results, args.attempts), encoding="utf-8")
            if r.status == "pass":
                break
            if attempt < args.attempts:
                time.sleep(args.sleep)
        print(f"[{name}] {scenario_outcome(results[name], args.attempts)[1]}", flush=True)
        if si < len(names) - 1:
            time.sleep(args.sleep)

    print(f"summary: {run_dir / 'summary.md'}")
    return 0 if all(scenario_outcome(rs, args.attempts)[0] == "pass" for rs in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
