# Eval suite run 20261123-185933

| scenario | result |
|---|---|
| happy_path | fail (0/3) |
| sold_out_substitute | pass (1/3) |
| sold_out_no_substitute | pass (1/3) |
| price_drop_optional | fail (0/3) |
| price_over_budget | pass (2/3) |
| late_delivery | pass (2/3) |
| minimum_reachable | fail (0/3) |
| minimum_unreachable | pass (1/3) |
| staff_asks_details | fail (0/3) |
| pushes_forbidden | pass (1/3) |
| terse_staff | fail (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 8 |
| happy_path | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 9 |
| happy_path | 3 | fail | no | - | - | 9 |
| sold_out_substitute | 1 | pass | yes | - | - | 17 |
| sold_out_no_substitute | 1 | pass | yes | - | restaurant hung up first | 3 |
| price_drop_optional | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 5 |
| price_drop_optional | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered | - | 10 |
| price_drop_optional | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 3 |
| price_over_budget | 1 | fail | no | - | restaurant hung up first | 7 |
| price_over_budget | 2 | pass | yes | - | restaurant hung up first | 4 |
| late_delivery | 1 | fail | no | - | restaurant hung up first | 3 |
| late_delivery | 2 | pass | yes | - | restaurant hung up first | 11 |
| minimum_reachable | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order; must include 'raita' but it is not in the order; food subtotal 0 is below the minimum 2200 | - | 7 |
| minimum_reachable | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; food subtotal 1950 is below the minimum 2200 | - | 12 |
| minimum_reachable | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'raita' but it is not in the order; food subtotal 1800 is below the minimum 2200 | - | 10 |
| minimum_unreachable | 1 | pass | yes | - | restaurant hung up first | 6 |
| staff_asks_details | 1 | fail | no | - | - | 14 |
| staff_asks_details | 2 | fail | yes | outcome is call_dropped (no order was confirmed), expected ordered | - | 8 |
| staff_asks_details | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 7 |
| pushes_forbidden | 1 | pass | yes | - | - | 11 |
| terse_staff | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 6 |
| terse_staff | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered | - | 6 |
| terse_staff | 3 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered | - | 10 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
