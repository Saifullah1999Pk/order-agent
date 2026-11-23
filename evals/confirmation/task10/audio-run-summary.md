# Eval suite run 20261123-194523 (rescored)

| scenario | result |
|---|---|
| happy_path | quota_error (0/3) |
| sold_out_substitute | quota_error (0/1) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 3 |
| happy_path | 2 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 3 |
| happy_path | 3 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 3 |
| sold_out_substitute | 1 | quota_error | no | no call report was written | - | 3 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
