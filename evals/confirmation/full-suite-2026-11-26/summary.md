# Eval suite run 20261126-162641

| scenario | result |
|---|---|
| happy_path | pass (on attempt 1 of 3) |
| sold_out_substitute | pass (on attempt 1 of 3) |
| sold_out_no_substitute | pass (on attempt 2 of 3) |
| price_drop_optional | pass (on attempt 2 of 3) |
| price_over_budget | fail (no pass in 3 attempts) |
| late_delivery | pass (on attempt 2 of 3) |
| minimum_reachable | fail (no pass in 3 attempts) |
| minimum_unreachable | pass (on attempt 1 of 3) |
| staff_asks_details | pass (on attempt 1 of 3) |
| pushes_forbidden | pass (on attempt 2 of 3) |
| terse_staff | pass (on attempt 1 of 3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | pass | yes | - | - | 12 |
| sold_out_substitute | 1 | pass | yes | - | - | 12 |
| sold_out_no_substitute | 1 | fail | no | - | - | 13 |
| sold_out_no_substitute | 2 | pass | yes | - | - | 12 |
| price_drop_optional | 1 | fail | no | - | - | 11 |
| price_drop_optional | 2 | pass | yes | - | - | 13 |
| price_over_budget | 1 | fail | no | price for chicken biryani was 1450, menu says 1300 | restaurant hung up first | 15 |
| price_over_budget | 2 | fail | no | - | - | 14 |
| price_over_budget | 3 | fail | no | - | - | 21 |
| late_delivery | 1 | fail | yes | price for chicken biryani was 975, menu says 900 | - | 11 |
| late_delivery | 2 | pass | yes | - | - | 11 |
| minimum_reachable | 1 | fail | no | - | - | 25 |
| minimum_reachable | 2 | fail | no | - | - | 23 |
| minimum_reachable | 3 | fail | no | - | - | 25 |
| minimum_unreachable | 1 | pass | yes | - | - | 18 |
| staff_asks_details | 1 | pass | yes | - | - | 15 |
| pushes_forbidden | 1 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 13 |
| pushes_forbidden | 2 | pass | yes | - | - | 12 |
| terse_staff | 1 | pass | yes | - | - | 22 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
