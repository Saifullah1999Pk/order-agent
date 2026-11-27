"""Experiment (not committed): re-judge saved attempts with a different judge model.

Usage: uv run python <this> <results_dir> <model> scenario/attempt ...
Run from the order-agent repo root.
"""

import asyncio
import dataclasses
import json
import sys
from pathlib import Path

from pipecat.evals.scenario import EvalScenarioFile
from pipecat.evals.simulation_judge import EvalSimulationJudge


async def main(results: Path, model: str, picks: list[str]) -> None:
    for pick in picks:
        name, attempt = pick.split("/")
        scenarios = EvalScenarioFile.load(Path("evals/scenarios") / f"{name}.yaml")
        scenario = scenarios[f"{name}/{name}"]
        judge_cfg = json.loads(json.dumps(scenario.judge))
        (judge_cfg["eval"] if "eval" in judge_cfg else judge_cfg)["model"] = model
        print(f"judge config keys: {list(judge_cfg)}", flush=True)
        try:
            scenario = dataclasses.replace(scenario, judge=judge_cfg)
        except TypeError:
            object.__setattr__(scenario, "judge", judge_cfg)
        messages = json.loads((results / name / attempt / "conversation.json").read_text(encoding="utf-8"))
        j = await EvalSimulationJudge(scenario).judge(messages)
        metrics = "; ".join(
            f"{m.name}={getattr(m, 'score', '?')} passed={getattr(m, 'passed', '?')}" for m in j.metrics
        )
        print(f"{pick} | goal={j.goal.outcome if hasattr(j.goal, 'outcome') else j.goal} | {metrics}", flush=True)
        for m in j.metrics:
            for r in getattr(m, "reasons", []) or []:
                print(f"    reason: {r}", flush=True)


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2], sys.argv[3:]))
