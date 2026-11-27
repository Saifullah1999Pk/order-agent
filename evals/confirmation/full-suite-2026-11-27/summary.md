# Eval suite run 20261127-130223

| scenario | result |
|---|---|
| happy_path | pass (on attempt 1 of 3) |
| sold_out_substitute | pass (on attempt 1 of 3) |
| sold_out_no_substitute | pass (on attempt 3 of 3) |
| price_drop_optional | pass (on attempt 2 of 3) |
| price_over_budget | fail (no pass in 3 attempts) |
| late_delivery | pass (on attempt 1 of 3) |
| minimum_reachable | pass (on attempt 2 of 3) |
| minimum_unreachable | pass (on attempt 2 of 3) |
| staff_asks_details | pass (on attempt 1 of 3) |
| pushes_forbidden | pass (on attempt 3 of 3) |
| terse_staff | pass (on attempt 1 of 3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | pass | yes | - | - | 15 |
| sold_out_substitute | 1 | pass | yes | - | - | 13 |
| sold_out_no_substitute | 1 | fail | no | - | - | 21 |
| sold_out_no_substitute | 2 | fail | no | - | - | 10 |
| sold_out_no_substitute | 3 | pass | yes | - | - | 13 |
| price_drop_optional | 1 | fail | no | - | - | 12 |
| price_drop_optional | 2 | pass | yes | - | - | 11 |
| price_over_budget | 1 | fail | no | - | - | 20 |
| price_over_budget | 2 | fail | no | - | - | 18 |
| price_over_budget | 3 | fail | no | - | - | 15 |
| late_delivery | 1 | pass | yes | - | - | 16 |
| minimum_reachable | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; food subtotal 1950 is below the minimum 2200 | - | 12 |
| minimum_reachable | 2 | pass | yes | - | - | 23 |
| minimum_unreachable | 1 | fail | no | - | - | 13 |
| minimum_unreachable | 2 | pass | yes | - | - | 12 |
| staff_asks_details | 1 | pass | yes | - | - | 12 |
| pushes_forbidden | 1 | fail | no | delivery fee was 0, menu says 150 | - | 9 |
| pushes_forbidden | 2 | fail | no | - | - | 12 |
| pushes_forbidden | 3 | pass | yes | - | - | 18 |
| terse_staff | 1 | pass | yes | - | - | 14 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
