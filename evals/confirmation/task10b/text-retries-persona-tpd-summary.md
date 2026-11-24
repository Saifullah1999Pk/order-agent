# Eval suite run 20261123-212620

| scenario | result |
|---|---|
| minimum_reachable | quota_error (0/3) |
| staff_asks_details | fail (0/3) |
| terse_staff | quota_error (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| minimum_reachable | 1 | quota_error | n/a | - | harness: Error during completion: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in organization `org_REDACTED` service tier `on_demand` on tokens per day (TPD) | 1 |
| minimum_reachable | 2 | quota_error | n/a | - | harness: Error during completion: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in organization `org_REDACTED` service tier `on_demand` on tokens per day (TPD) | 1 |
| minimum_reachable | 3 | quota_error | n/a | - | harness: Error during completion: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in organization `org_REDACTED` service tier `on_demand` on tokens per day (TPD) | 1 |
| staff_asks_details | 1 | quota_error | n/a | - | harness: Error during completion: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in organization `org_REDACTED` service tier `on_demand` on tokens per day (TPD) | 1 |
| staff_asks_details | 2 | fail | no | outcome is call_dropped (no order was confirmed), expected ordered; must include 'chicken biryani' but it is not in the order | - | 1 |
| staff_asks_details | 3 | quota_error | n/a | - | harness: Error during completion: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in organization `org_REDACTED` service tier `on_demand` on tokens per day (TPD) | 1 |
| terse_staff | 1 | quota_error | n/a | - | harness: Error during completion: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in organization `org_REDACTED` service tier `on_demand` on tokens per day (TPD) | 1 |
| terse_staff | 2 | quota_error | n/a | - | harness: Error during completion: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in organization `org_REDACTED` service tier `on_demand` on tokens per day (TPD) | 1 |
| terse_staff | 3 | quota_error | n/a | - | harness: Error during completion: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in organization `org_REDACTED` service tier `on_demand` on tokens per day (TPD) | 1 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
