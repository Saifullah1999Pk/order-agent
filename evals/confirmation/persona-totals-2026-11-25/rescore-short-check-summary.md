# Eval suite run 20261125-145529 (rescored)

| scenario | result |
|---|---|
| happy_path | restaurant_error (0/1) |
| sold_out_no_substitute | pass (1/3) |
| minimum_reachable | pass (1/3) |
| terse_staff | restaurant_error (0/1) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | restaurant_error | no | outcome is not_ordered (no order was confirmed), expected ordered | restaurant quoted a wrong total (1250 vs 2100); bot correctly declined | 17 |
| sold_out_no_substitute | 1 | pass | yes | - | - | 9 |
| minimum_reachable | 1 | pass | yes | - | - | 15 |
| terse_staff | 1 | restaurant_error | no | outcome is not_ordered (no order was confirmed), expected ordered | restaurant quoted a wrong total (1950 vs 2100); bot correctly declined | 24 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
