# Eval suite run 20261125-162659

| scenario | result |
|---|---|
| terse_staff | pass (3/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| terse_staff | 1 | fail | no | - | - | 14 |
| terse_staff | 2 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 10 |
| terse_staff | 3 | pass | yes | - | - | 12 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
