# All-Ollama run (bot, simulated restaurant and judge all `qwen3:8b`), 2026-11-24

No cloud API was used. Setup: Ollama 0.40.18 on an AMD RX 6600 (8 GB, Vulkan), `qwen3:8b` (Q4_K_M), server started with
`OLLAMA_NUM_PARALLEL=3 OLLAMA_CONTEXT_LENGTH=4096 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_FLASH_ATTENTION=1`.
`ollama ps`: 5.9 GB, `100% GPU`. (With the default f16 KV cache the same three slots needed 7.2 GB and 8% ran on the CPU, so
q8_0 KV was added; that is the only deviation from the plain settings.) Thinking is off through `reasoning_effort: none`
(verified: no reasoning field and 4 completion tokens for a sum; `think: false` was ignored on `/v1` and produced 735 tokens of thinking).
Text mode, runner on port 7861 (the user's bot on 7860 untouched), `--sleep 10`.
Largest prompt in Ollama's log: 3405 tokens of 4096, and `truncated = 1` never occurred, so 4096 was enough (about 700 tokens spare).

Files: `run-*-summary.md` (runner summaries), `evidence/<run>-<scenario>-attempt-N/` (conversation, judge verdict, eval log,
call report, bot TTFB lines).

## First run was a harness problem, not a result (run 181905)

Pipecat's judge classifier waits 10 s per question and asks about 7 at once, but 3 slots answer them a few at a time. All 3
happy_path attempts ended as `quota_error` ("did not answer within 10.0s"). Fixed by `order_agent.eval_llm.ollama_classifier`
(300 s timeout; `evals/judge-ollama.yaml`). Not counted below.

## Results (bot, persona and judge on qwen3:8b)

Persona column: stayed in role as staff / same-turn hang-up / wrote the customer's lines. Det = deterministic report check.
Times: bot first token per turn (median), whole call, judge.

| Scenario | # | Status | Persona (staff / same-turn hangup / wrote customer) | Bot tool calls correct? | Bot outcome | Violations | Judge vs Det | TTFT med | Call | Judge |
|---|---|---|---|---|---|---|---|---|---|---|
| happy_path | 1 | fail (judge conduct 0.75) | y / n / n | n: invented unit prices 925 and 125, set_fees 0 then 150 | ordered, Rs 2125 | none | judge FAIL, det OK: disagree | 2.1 s | 37 s | 23 s |
| happy_path | 2 | **pass** | y / n (ended after bot goodbye) / n | n: invented prices 1050 and 50 (back-solved from the quoted total) | ordered, Rs 2300 | none | agree (both pass) | 1.9 s | 34 s | 20 s |
| minimum_reachable | 1 | fail (judge conduct 0.8) | y / n / n | partly: price 800 for biryani (menu 900), then 4 raita to reach 2200 | ordered, Rs 2350, food 2200 | none | judge FAIL, det OK: disagree | 2.3 s | 45 s | 23 s |
| minimum_reachable | 2 | fail | y but repeated one line 6 times / n / n | n: invented 1075 and 100; 4 `confirm_order` retries on a mismatched total | call_dropped (max_turns) | no order confirmed | agree (both fail) | 2.2 s | 108 s | 108 s |
| minimum_reachable | 3 | fail (judge: goal not met) | y / n (ended after bot msg) / n | n: invented 1000 and 200, a Rs 300 fee and Rs 500 tax; wrote `end_call {...}` as plain text | call_dropped after confirm at Rs 2350 | none | judge FAIL, det OK: disagree | 2.1 s | 41 s | 31 s |
| staff_asks_details | 1 | fail | y / n / n | n: no tool calls at all, never named an item | call_dropped, no order | not ordered; no chicken biryani | judge PASS (0.95), det FAIL: disagree | 0.7 s | 28 s | 23 s |
| staff_asks_details | 2 | fail | y but repeated a question / n / n | n: no tool calls | call_dropped | same | agree (both fail) | 0.7 s | 26 s | 140 s |
| staff_asks_details | 3 | fail | y / n, but ended right after the customer's "yes" (after a bot msg) / n | n: no tool calls | call_dropped | same | judge PASS, det FAIL: disagree | 0.7 s | 21 s | 14 s |

Scenario results: happy_path pass (2 attempts used, 1 pass); minimum_reachable fail 0/3; staff_asks_details fail 0/3.
Over 74 bot turns: first token median 1.4 s, 90th percentile 3.3 s, max 5.6 s (turns with tool calls and the full tool schema
in the prompt are about 2 s; the first turn is 0.4 s because its prefix is cached). Calls take 20 to 45 s except looping ones.
The judge takes 14 to 31 s, and 108 to 140 s on the long conversations.

## Compared with the all-Gemini runs (evals/confirmation/persona-hangups/ANALYSIS.md, All-Gemini section)

- Same-turn persona hang-ups: 0 of 8 here, 0 of 21 with Gemini. The persona is not the weak point, but it sometimes loops (repeats one
  line) and announces "your order is confirmed" before any order exists.
- Quota: none here. With Gemini most attempts were `quota_error` (15 requests/min). This is the one clear advantage of local.
- Bot quality is clearly worse. qwen3:8b invented unit prices the staff never said in every call where it priced items (5 of 5; it
  back-solves them from the quoted total), set wrong fees, looped on `confirm_order` with a mismatched total, in staff_asks_details
  never placed an order (3 of 3), and once wrote a tool call as spoken text. The Gemini bot's recorded failures were milder (one invented
  price, giving up under the minimum). Neither setup has a clean pass count: Gemini was held back by quota, qwen3 by quality.
- The deterministic checks passed some calls with invented prices (the report checks outcome, budget and item names, and invented
  prices can even satisfy the food minimum). Nothing was weakened; this is a gap worth a separate check.
- Judge: qwen3:8b disagreed with the deterministic check in 5 of 8 attempts: 3 times stricter (conduct 0.75, 0.8, and goal-not-met on a
  confirmed order) and 2 times it said "goal met" (P 0.95) when no order was placed. It cannot replace the deterministic checks.
  The Groq judge was not run on these calls, so a like-for-like judge comparison is not available.

Verdict: all-local is feasible (20 to 45 s per call, no limits, no keys) and good enough to exercise the harness, but qwen3:8b is not
a reliable bot or judge for this task. Small sample: 8 attempts, one model.
