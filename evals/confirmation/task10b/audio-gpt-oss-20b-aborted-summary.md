# Eval suite run 20261123-211953

| scenario | result |
|---|---|
| happy_path | fail (0/2) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | fail | no | outcome is not_ordered (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 2 |
| happy_path | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 6 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
