# Judge model check: gpt-oss-20b vs gpt-oss-120b (2026-11-26)

These are saved calls from the full run `evals/results/20261126-162641`. That run's `summary.md` and its judge reasons were read from the local results. The calls were re-judged offline with `rejudge_experiment.py`. It uses Pipecat's `EvalSimulationJudge` with the same throttled Groq config, changing only the model. This makes no new calls and uses no Gemini.

Of the 8 attempts the 20b judge failed, I read every transcript:

- 4 were 20b judge errors, and the bot behaved correctly: price_over_budget 2 and 3, price_drop_optional 1, sold_out_no_substitute 1.
- 3 were real bot issues: minimum_reachable 1 to 3, where the bot stated its own total or confirmed while the read-back quantities differed. These were fixed in spec 002.
- 1 was a simulator price error, which by rule counts against the bot: late_delivery 1.

| Attempt | 20b verdict | 120b verdict | Correct (from transcript) |
|---|---|---|---|
| price_over_budget/2 | fail (conduct) | fail (conduct 0.8) | pass |
| price_over_budget/3 | fail (conduct) | **pass** | pass |
| price_drop_optional/1 | fail (conduct) | **pass** | pass |
| sold_out_no_substitute/1 | fail (conduct) | fail (conduct 0.8) | pass |
| happy_path/1 (control) | pass | pass | pass |
| terse_staff/1 (control) | pass | pass | pass |
| minimum_reachable/3 | fail (conduct, turn 7) | fail (conduct, turn 7) | fail (the bot stated its own total) |

Result: 120b fixed 2 of the 4 judge errors and changed no correct verdict. The sample is small. The default judge was switched to 120b, and the next full live run is its real test, including Groq's daily free token limit. An older note in `evals/CONFIRMATION.md` says 120b timed out as judge. That was Pipecat's fixed 10 s classifier timeout, before `groq_classifier`'s `timeout_s` and the throttle existed. In this check 120b finished every call, with one 400 JSON error that was retried successfully.

`rejudge-120b.txt` is the raw output. The minimum_reachable/3 line comes from an earlier single trial run of the same script.
