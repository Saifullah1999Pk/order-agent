# Eval suite run 20261124-182645

| scenario | result |
|---|---|
| minimum_reachable | fail (0/3) |
| staff_asks_details | fail (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| minimum_reachable | 1 | fail | no | - | - | 16 |
| minimum_reachable | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered | - | 31 |
| minimum_reachable | 3 | fail | no | - | restaurant hung up first | 13 |
| staff_asks_details | 1 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 13 |
| staff_asks_details | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 15 |
| staff_asks_details | 3 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 11 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
