"""One line per attempt: bot model, bot-side LLM errors, persona end reason, result.

    uv run python evals/diagnose.py evals/results/<run-id>
"""

import json
import re
import sys
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def main(run: Path) -> None:
    print("scenario/attempt | bot model | bot LLM errors (429/503/timeout) | nudges | persona end | persona turns | report outcome")
    for d in sorted(run.glob("*/attempt-*")):
        log = ANSI.sub("", (d / "bot.log").read_text(encoding="utf-8", errors="replace"))
        ev = (d / "eval.log").read_text(encoding="utf-8", errors="replace") if (d / "eval.log").exists() else ""
        err = [ln for ln in log.splitlines() if "| ERROR" in ln and "LLMService" in ln]
        n429 = sum(1 for ln in err if re.search(r"\b429\b", ln))
        n503 = sum(1 for ln in err if re.search(r"\b503\b", ln))
        ntmo = sum(1 for ln in err if "timeout" in ln.lower())
        model = re.search(r"Model probe (?:ok|failed) for ([\w.-]+)|model[=: ']+(gemini[\w.-]+)", log)
        used = re.search(r"GoogleLLMService#0.*?model[=: ']+(gemini[\w.-]+)", log) or re.search(r"model[=: ']+(gemini[\w.-]+)", log)
        probe_fail = "Model probe failed" in log
        end = re.search(r"persona: (ended by [^\n]*|hung up[^\n]*)", ev)
        turns = re.search(r"after (\d+) turn", ev)
        outcome = "?"
        for j in d.glob("2026*.json"):
            outcome = json.loads(j.read_text(encoding="utf-8")).get("outcome", "?")
        print(
            f"{d.parent.name}/{d.name} | {used.group(1) if used else '?'}{' (primary probe failed)' if probe_fail else ''}"
            f" | 429:{n429} 503:{n503} timeout:{ntmo} | {log.count('nudging the LLM')}"
            f" | {end.group(1) if end else '?'} | {turns.group(1) if turns else '?'} | {outcome}"
        )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
