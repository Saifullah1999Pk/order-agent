# Eval suite run 20261125-161429

| scenario | result |
|---|---|
| terse_staff | fail (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| terse_staff | 1 | fail | no | delivery fee was 0, menu says 150 | - | 14 |
| terse_staff | 2 | fail | no | delivery fee was 0, menu says 150 | - | 17 |
| terse_staff | 3 | fail | yes | price for chicken biryani was 975, menu says 900; delivery fee was 0, menu says 150 | - | 17 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
