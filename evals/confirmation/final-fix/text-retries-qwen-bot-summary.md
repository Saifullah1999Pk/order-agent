# Eval suite run 20261124-124818

| scenario | result |
|---|---|
| minimum_reachable | fail (0/3) |
| staff_asks_details | fail (0/3) |
| terse_staff | fail (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| minimum_reachable | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; food subtotal 1950 is below the minimum 2200 | - | 8 |
| minimum_reachable | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; food subtotal 1950 is below the minimum 2200 | - | 8 |
| minimum_reachable | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; food subtotal 1950 is below the minimum 2200 | - | 9 |
| staff_asks_details | 1 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 11 |
| staff_asks_details | 2 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 12 |
| staff_asks_details | 3 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 8 |
| terse_staff | 1 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 7 |
| terse_staff | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 7 |
| terse_staff | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 5 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
