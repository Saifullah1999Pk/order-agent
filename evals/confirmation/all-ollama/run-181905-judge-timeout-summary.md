# Eval suite run 20261124-181905

| scenario | result |
|---|---|
| happy_path | quota_error (0/3) |

## Attempts

| scenario | attempt | status | judge | violations | notes | requests |
|---|---|---|---|---|---|---|
| happy_path | 1 | quota_error | n/a | - | harness: judge call failed: OLLamaLLMService#1 did not answer within 10.0s | 14 |
| happy_path | 2 | quota_error | n/a | - | harness: judge call failed: OLLamaLLMService#3 did not answer within 10.0s | 16 |
| happy_path | 3 | quota_error | n/a | - | harness: judge call failed: OLLamaLLMService#5 did not answer within 10.0s | 34 |

Requests = bot LLM calls + simulated-restaurant turns. Judge requests are not counted.
