# Eval suite run 20261125-152516

| scenario | result |
|---|---|
| happy_path | pass (1/2) |
| terse_staff | fail (0/2) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | pass | yes | - | - | 19 |
| terse_staff | 1 | fail | no | outcome is not_ordered (no order was confirmed), expected ordered; price for chicken biryani was 975, menu says 900 | - | 26 |
| terse_staff | 2 | fail | yes | price for raita was 300, menu says 150; delivery fee was 0, menu says 150 | - | 17 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
