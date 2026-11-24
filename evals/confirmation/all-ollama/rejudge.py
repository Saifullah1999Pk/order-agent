import asyncio, json, sys, time
from pathlib import Path
from pipecat.evals.scenario import EvalScenarioFile
from pipecat.evals.simulation_judge import EvalSimulationJudge
from order_agent.eval_config import apply_eval_configs

judge_cfg, listfile, out = sys.argv[1:4]
done = set()
if Path(out).exists():
    for l in Path(out).read_text().splitlines():
        d = json.loads(l); done.add(d["id"])
async def main():
    for line in Path(listfile).read_text().splitlines():
        if not line.strip(): continue
        run, sc, at = line.split()
        id_ = f"{run}/{sc}/{at}"
        if id_ in done: continue
        scen = list(EvalScenarioFile.load(f"evals/scenarios/{sc}.yaml"))[0]
        scen = apply_eval_configs(scen, None, judge_cfg)
        conv = json.loads(Path(f"evals/results/{id_}/conversation.json").read_text(encoding="utf-8"))
        t = time.monotonic()
        try:
            j = await EvalSimulationJudge(scen).judge(conv)
            rec = dict(id=id_, goal=str(j.goal.verdict), goal_reason=j.goal.reason,
                       metrics=[dict(name=m.name, score=m.score, passed=m.passed, reason=m.reason) for m in j.metrics])
        except Exception as e:
            rec = dict(id=id_, goal="error", goal_reason=repr(e)[:300], metrics=[])
        rec["secs"] = round(time.monotonic() - t, 1)
        with open(out, "a") as f: f.write(json.dumps(rec) + "\n")
        print(id_, rec["goal"], [(m["score"], m["passed"]) for m in rec["metrics"]], rec["secs"], flush=True)
asyncio.run(main())
