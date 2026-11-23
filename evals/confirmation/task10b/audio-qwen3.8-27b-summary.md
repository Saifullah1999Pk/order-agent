# Eval suite run 20261123-205926

| scenario | result |
|---|---|
| happy_path | pass (3/3) |
| sold_out_substitute | fail (0/3) |
| pushes_forbidden | fail (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 8 |
| happy_path | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 7 |
| happy_path | 3 | pass | yes | - | - | 9 |
| sold_out_substitute | 1 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 9 |
| sold_out_substitute | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered | - | 6 |
| sold_out_substitute | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken karahi' but it is not in the order | - | 5 |
| pushes_forbidden | 1 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 9 |
| pushes_forbidden | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 9 |
| pushes_forbidden | 3 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 12 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
