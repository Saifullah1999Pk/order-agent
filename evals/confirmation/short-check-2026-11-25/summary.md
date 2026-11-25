# Eval suite run 20261125-145529

| scenario | result |
|---|---|
| happy_path | fail (0/1) |
| terse_staff | fail (0/1) |
| minimum_reachable | pass (1/1) |
| sold_out_no_substitute | pass (1/1) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | fail | no | outcome is not_ordered (no order was confirmed), expected ordered | - | 17 |
| terse_staff | 1 | fail | no | outcome is not_ordered (no order was confirmed), expected ordered | - | 24 |
| minimum_reachable | 1 | pass | yes | - | - | 15 |
| sold_out_no_substitute | 1 | pass | yes | - | - | 9 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
