# Eval suite run 20261124-125906

| scenario | result |
|---|---|
| sold_out_substitute | fail (0/3) |
| pushes_forbidden | fail (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| sold_out_substitute | 1 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 8 |
| sold_out_substitute | 2 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 9 |
| sold_out_substitute | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered | - | 10 |
| pushes_forbidden | 1 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 14 |
| pushes_forbidden | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |
| pushes_forbidden | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 18 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
