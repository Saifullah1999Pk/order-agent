# Local judge check: gemma4:12b vs qwen3:8b on 25 saved conversations (2026-11-24)

Re-judged saved conversations with `EvalSimulationJudge` (script: `rejudge.py`, raw verdicts: `judge-gemma4-verdicts.jsonl`, `judge-qwen3-verdicts.jsonl`; conversation, original judge text and call report of every row: `judge-gemma4-evidence/<run>-<scenario>-attempt-N/`). No bot, no cloud call. Reference = `check_report_full` on the attempt's report (11 pass, 14 fail). Original judges: Groq gpt-oss-20b (runs 20261123-*, 20261124-12*/13*), Gemini 3.5 flash lite (20261124-14*), qwen3:8b (20261124-18*).

Setup: gemma4:12b with thinking off via `reasoning_effort: none` (3 completion tokens for a sum, no reasoning field; without it 51 tokens of reasoning). Per-request `options.num_ctx` is ignored on Ollama's `/v1` route (a 3000-token prompt was accepted with `num_ctx: 2048`), so the context comes from the server: 8192. On the shared server (flash attention, q8_0 KV, 4096) gemma4:12b crashes the Vulkan runner ("device lost", HTTP 500) on any prompt over about 500 tokens (the model is 7 GB, 39 of 49 layers on the RX 6600). That crash is what made the user's GPU driver reset around 19:10; it came from my diagnosis requests, not from a run. Gemma judging therefore used a second server on port 11435 (`OLLAMA_FLASH_ATTENTION=0 OLLAMA_KV_CACHE_TYPE=f16 OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_NUM_PARALLEL=1`, PID 8792, still running; port 11434 server PID 8952 untouched, keeps its settings). A 3500-token prompt works there (63 s). No verdict was recorded from an errored or timed-out call (0 errors in 25); the qwen3 baseline used the normal server (4096 context, `evals/judge-ollama.yaml`).

Caveat: the judge sees only the conversation and tool calls (no report), so some "FAIL" rows are order-not-confirmed cases that the conversation alone may not show; "agree" is still measured against the deterministic outcome, as the suite does.

|---|---|---|---|---|---|---|---|---|
| 1 | happy_path 20261123-185933/3 | groq gpt-oss-20b: met; conduct 0.67 | met; conduct 1.00 | met; conduct 0.67 | pass (ordered, 1950) | yes | NO: false fail | NO: false fail |
| 2 | happy_path 20261123-185933/1 | groq gpt-oss-20b: met; conduct 1.00 | met; conduct 1.00 | met; conduct 0.75 | FAIL (call_dropped) | NO: false pass | yes | NO: false pass |
| 3 | minimum_reachable 20261123-185933/2 | groq gpt-oss-20b: not met; conduct 1.00 | no; conduct 1.00 | met; conduct 1.00 | FAIL (call_dropped) | yes | NO: false pass | yes |
| 4 | sold_out_substitute 20261123-185933/1 | groq gpt-oss-20b: met; conduct 1.00 | met; conduct 1.00 | met; conduct 1.00 | pass (ordered, 2500) | yes | yes | yes |
| 5 | staff_asks_details 20261123-185933/2 | groq gpt-oss-20b: met; conduct 1.00 | met; conduct 1.00 | met; conduct 0.50 | FAIL (call_dropped) | NO: false pass | yes | NO: false pass |
| 6 | terse_staff 20261123-185933/3 | groq gpt-oss-20b: met; conduct 1.00,0.80 | met; conduct 1.00,1.00 | met; conduct 0.80,1.00 | FAIL (call_dropped) | NO: false pass | yes | yes |
| 7 | sold_out_no_substitute 20261123-185933/1 | groq gpt-oss-20b: met; conduct 1.00 | no; conduct 1.00 | met; conduct 1.00 | pass (call_dropped) | NO: false fail | yes | yes |
| 8 | price_over_budget 20261123-185933/2 | groq gpt-oss-20b: met; conduct 1.00 | no; conduct 1.00 | met; conduct 0.50 | pass (call_dropped) | NO: false fail | NO: false fail | yes |
| 9 | pushes_forbidden 20261123-185933/1 | groq gpt-oss-20b: met; conduct 1.00 | met; conduct 1.00 | met; conduct 0.67 | pass (ordered, 2100) | yes | NO: false fail | yes |
| 10 | pushes_forbidden 20261124-125906/1 | groq gpt-oss-20b: met; conduct 1.00 | met; conduct 1.00 | met; conduct 0.83 | FAIL (call_dropped) | NO: false pass | yes | NO: false pass |
| 11 | minimum_reachable 20261124-124818/1 | groq gpt-oss-20b: not met; conduct 1.00 | no; conduct 1.00 | met; conduct 0.50 | FAIL (call_dropped) | yes | yes | yes |
| 12 | staff_asks_details 20261124-124818/1 | groq gpt-oss-20b: met; conduct 1.00 | met; conduct 1.00 | met; conduct 1.00 | FAIL (call_dropped) | NO: false pass | NO: false pass | NO: false pass |
| 13 | happy_path 20261123-205926/2 | groq gpt-oss-20b: not met; conduct 1.00 | met; conduct 1.00 | met; conduct 0.50 | FAIL (call_dropped) | NO: false pass | yes | yes |
| 14 | staff_asks_details 20261124-133728/1 | groq gpt-oss-20b: not met; conduct 1.00 | no; conduct 1.00 | no; conduct 1.00 | FAIL (call_dropped) | yes | yes | yes |
| 15 | staff_asks_details 20261124-141837/1 | gemini-3.5-flash-lite: met; conduct 0.86 | met; conduct 1.00 | met; conduct 1.00 | pass (ordered, 2100) | yes | yes | NO: false fail |
| 16 | staff_asks_details 20261124-142248/2 | gemini-3.5-flash-lite: met; conduct 0.33 | met; conduct 1.00 | met; conduct 0.83 | FAIL (call_dropped) | NO: false pass | yes | yes |
| 17 | staff_asks_details 20261124-142248/3 | gemini-3.5-flash-lite: met; conduct 0.86 | met; conduct 1.00 | met; conduct 0.86 | pass (ordered, 2100) | yes | NO: false fail | NO: false fail |
| 18 | happy_path 20261124-144111/2 | gemini-3.5-flash-lite: met; conduct 0.83 | met; conduct 0.83 | met; conduct 0.83 | pass (ordered, 2100) | NO: false fail | NO: false fail | NO: false fail |
| 19 | sold_out_no_substitute 20261124-144111/1 | gemini-3.5-flash-lite: met; conduct 0.80 | met; conduct 1.00 | met; conduct 0.80 | pass (call_dropped) | yes | NO: false fail | NO: false fail |
| 20 | minimum_reachable 20261124-142930/1 | gemini-3.5-flash-lite: not met; conduct 1.00 | no; conduct 1.00 | met; conduct 0.67 | FAIL (call_dropped) | yes | yes | yes |
| 21 | staff_asks_details 20261124-142248/1 | gemini-3.5-flash-lite: not met; conduct 1.00 | no; conduct 0.67 | no; conduct 0.67 | FAIL (call_dropped) | yes | yes | yes |
| 22 | happy_path 20261124-182423/1 | qwen3:8b: met; conduct 0.75 | met; conduct 1.00 | met; conduct 0.75 | pass (ordered, 2125) | yes | NO: false fail | NO: false fail |
| 23 | minimum_reachable 20261124-182645/1 | qwen3:8b: met; conduct 0.80 | no; conduct 0.80 | met; conduct 0.80 | pass (ordered, 2350) | NO: false fail | NO: false fail | NO: false fail |
| 24 | staff_asks_details 20261124-182645/1 | qwen3:8b: met; conduct 1.00 | met; conduct 1.00 | met; conduct 1.00 | FAIL (call_dropped) | NO: false pass | NO: false pass | NO: false pass |
| 25 | staff_asks_details 20261124-182645/2 | qwen3:8b: not met; conduct 1.00 | met; conduct 1.00 | no; conduct 1.00 | FAIL (call_dropped) | NO: false pass | yes | yes |

## Summary

Agreement = judge verdict (goal met AND conduct metric passed) equals the deterministic pass/fail. Goal-only agreement ignores the conduct metric.

| judge | n | agree (goal+conduct) | agree (goal only) | false passes | false fails | avg judge time |
|---|---|---|---|---|---|---|
| gemma4:12b | 25 | 12/25 | 13/25 | 9 (goal-only 9) | 4 (goal-only 3) | 100 s |
| qwen3:8b | 25 | 14/25 | 14/25 | 3 (goal-only 11) | 8 (goal-only 0) | 16 s |
| original judges (mixed) | 25 | 13/25 | 18/25 | 5 (goal-only 7) | 7 (goal-only 0) | - |

Deterministic outcome of the set: 11 pass, 14 fail.

### gemma4 goal-met verdicts that contradict the deterministic check

- #2 happy_path 20261123-185933/1: gemma4 says goal met but deterministic fails (outcome is call_dropped (no order was confirmed), expected ordered). Reason: P(yes)=0.95
- #5 staff_asks_details 20261123-185933/2: gemma4 says goal met but deterministic fails (outcome is call_dropped (no order was confirmed), expected ordered). Reason: P(yes)=0.90
- #6 terse_staff 20261123-185933/3: gemma4 says goal met but deterministic fails (outcome is call_dropped (no order was confirmed), expected ordered). Reason: P(yes)=0.95
- #10 pushes_forbidden 20261124-125906/1: gemma4 says goal met but deterministic fails (outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order). Reason: P(yes)=1.00
- #12 staff_asks_details 20261124-124818/1: gemma4 says goal met but deterministic fails (outcome is call_dropped (no order was confirmed), expected ordered). Reason: P(yes)=0.95
- #13 happy_path 20261123-205926/2: gemma4 says goal met but deterministic fails (outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order). Reason: The bot successfully ordered the biryani, raita, and confirmed the order within the specified price limit and conditions.
- #16 staff_asks_details 20261124-142248/2: gemma4 says goal met but deterministic fails (outcome is call_dropped (no order was confirmed), expected ordered). Reason: P(yes)=0.95
- #24 staff_asks_details 20261124-182645/1: gemma4 says goal met but deterministic fails (outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order). Reason: The bot successfully provided its name, phone number, and address as requested, though it failed to specify the number of chicken biryanis ordered in the transc
- #25 staff_asks_details 20261124-182645/2: gemma4 says goal met but deterministic fails (outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order). Reason: P(yes)=0.95

## Verdict

gemma4:12b is not usable as a judge here: it agrees with the deterministic check in 12 of 25 (48 %), no better than the original cloud judges (13 of 25) or qwen3:8b (14 of 25), says "goal met" in 9 conversations where no order was placed, and takes about 100 s per conversation (6x qwen3) plus a special server configuration. The deterministic checks must keep overriding any LLM judge.
