"""Experiment: re-judge saved attempts with the scenario YAML as it is now (new conduct criterion).
Usage: uv run python <this> results_dir/scenario/attempt-N ...   (run from the order-agent root)"""
import asyncio, json, sys
from pathlib import Path
from pipecat.evals.scenario import EvalScenarioFile
from pipecat.evals.simulation_judge import EvalSimulationJudge

async def main(picks):
    for pick in picks:
        p = Path(pick); name = p.parent.name
        scenario = EvalScenarioFile.load(Path("evals/scenarios") / f"{name}.yaml")[f"{name}/{name}"]
        messages = json.loads((p / "conversation.json").read_text(encoding="utf-8"))
        j = await EvalSimulationJudge(scenario).judge(messages)
        goal = j.goal.outcome if hasattr(j.goal, "outcome") else j.goal
        ms = "; ".join(f"{m.name}={getattr(m,'score','?'):.2f} passed={getattr(m,'passed','?')}" for m in j.metrics)
        print(f"RESULT {pick} | goal={goal} | {ms}", flush=True)
        for m in j.metrics:
            for r in getattr(m, "reasons", []) or []:
                print(f"    reason: {r}", flush=True)

asyncio.run(main(sys.argv[1:]))
