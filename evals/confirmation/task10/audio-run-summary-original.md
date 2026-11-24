# Eval suite run 20261123-194523

| scenario | result |
|---|---|
| happy_path | fail (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |
| happy_path | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |
| happy_path | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.

Note (added by hand): this run was started as `--audio --only happy_path,sold_out_substitute,pushes_forbidden`
and stopped by the operator after happy_path because the Gemini free-tier daily quota was exhausted
(gemini-3.5-flash-lite: 500 requests/day; fallback gemini-2.5-flash: 20 requests/day; both returned 429, see
attempt-diagnostics.txt). The sold_out_substitute attempt that was running was killed and has no result;
pushes_forbidden was never started. The three happy_path attempts above are quota failures, not bot failures
(the bot spoke the greeting and then every LLM call returned 429; 0 persona turns).
