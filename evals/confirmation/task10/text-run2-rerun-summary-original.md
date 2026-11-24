# Eval suite run 20261123-192810

| scenario | result |
|---|---|
| happy_path | pass (1/3) |
| price_drop_optional | pass (1/3) |
| minimum_reachable | fail (0/3) |
| staff_asks_details | fail (0/3) |
| terse_staff | fail (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | pass | yes | - | - | 11 |
| price_drop_optional | 1 | pass | yes | - | - | 10 |
| minimum_reachable | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; food subtotal 1950 is below the minimum 2200 | - | 13 |
| minimum_reachable | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; food subtotal 1950 is below the minimum 2200 | - | 10 |
| minimum_reachable | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order; must include 'raita' but it is not in the order; food subtotal 0 is below the minimum 2200 | - | 3 |
| staff_asks_details | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |
| staff_asks_details | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered | - | 10 |
| staff_asks_details | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |
| terse_staff | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |
| terse_staff | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |
| terse_staff | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
