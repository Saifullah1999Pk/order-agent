# Eval suite run 20261123-192810 (rescored)

| scenario | result |
|---|---|
| happy_path | pass (1/3) |
| price_drop_optional | pass (1/3) |
| minimum_reachable | quota_error (0/3) |
| staff_asks_details | quota_error (0/3) |
| terse_staff | quota_error (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | pass | yes | - | - | 11 |
| price_drop_optional | 1 | pass | yes | - | - | 10 |
| minimum_reachable | 1 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; food subtotal 1950 is below the minimum 2200 | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 13 |
| minimum_reachable | 2 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; food subtotal 1950 is below the minimum 2200 | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 10 |
| minimum_reachable | 3 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order; must include 'raita' but it is not in the order; food subtotal 0 is below the minimum 2200 | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 3 |
| staff_asks_details | 1 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 3 |
| staff_asks_details | 2 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 10 |
| staff_asks_details | 3 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 3 |
| terse_staff | 1 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 3 |
| terse_staff | 2 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 3 |
| terse_staff | 3 | quota_error | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | bot LLM hit 429/503 (see bot.log) and the call did not complete: recorded as quota_error | 3 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
