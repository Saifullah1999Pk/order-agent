# Why the simulated restaurant hangs up early (2026-11-24)

Evidence: `end_call-table.md` in this folder, built from 40 persona `end_call`s. 36 of them were in the 7 ordered scenarios. The local run logs it was built from are gitignored.

## Root causes (ordered scenarios, n = 36)

| Cause | Count | Detail |
|---|---|---|
| A. The persona treats "quoted the total" as its goal being achieved | 35 | The goal text said "quote the total, then end the call". Pipecat's base persona prompt says to call `end_call` once the goal is achieved. In 19 of the 36, the persona called `end_call` in the same generation as its quote. The bot reached `confirm_order` in only 3 of the 36. |
| B. The persona hangs up straight after the customer says "yes, place it" | ~6 | This happens before the bot's `confirm_order` runs. It overlaps with A. |
| C. The persona writes the customer's lines itself | several | This is the model's own behaviour (gpt-oss-120b); no wording stopped it. |
| Bot side (contributing only) | — | The qwen bot was slow: 17 of 62 LLM calls took over 8 s, the longest 19.5 s. It re-asked about fees, and once offered a third biryani that would have put the food at Rs 2850, over budget. The engine refuses an over-budget add. terse_staff shows the same hang-ups without any slow calls. |

## Change made (commit b672496)
All 11 scenario `goal:` lines changed: "then end the call" was removed.
- Ordered scenarios: do not call `end_call` until the customer has said goodbye, and never in the same turn as your own message.
- Not-ordered scenarios: the same, until the customer says goodbye or declines.

`tests/test_scenarios.py` asserts this wording; it was written first and failed first.

## Result: not verified
All three free Groq models hit their daily token caps during verification.
- In the runs that were possible, 6 of the 7 persona `end_call`s after the change were still same-turn hang-ups.
- One minimum_reachable attempt ran without a persona hang-up. In it, the bot removed an item and ended the call after the restaurant quoted Rs 3000.

The summaries are in this folder.

## Next options (free only)
1. Set `reasoning_effort: high` for the persona model (gpt-oss-120b) in `evals/simulator.yaml`, and try it on 3 attempts of one scenario.
2. Try a different free persona model, if one follows the goal text better.
3. Tune the bot: faster replies, no re-asking about fees, never propose extra items over budget.
4. Out of scope for now: a runner rule that ignores an `end_call` made in the same turn as the persona's own message. This would change how Pipecat's harness works, so it needs a decision first.

## Experiments 2026-11-24 afternoon (inconclusive: free quota exhausted)

Scenario staff_asks_details, text mode, --attempts 3, --sleep 30. `evals/simulator.yaml` was edited temporarily for each run and restored (it is unchanged). Runner used port 7861 (7860 was in use by the user's bot, untouched).

| Exp | Persona | Bot | Attempt | Status | Persona turns | Persona same-turn end_call | Who ended | Bot outcome | Violations |
|---|---|---|---|---|---|---|---|---|---|
| E1 | groq gpt-oss-120b, reasoning_effort high | Gemini 3.5 flash-lite | 1-3 | quota_error | 0 | n/a | harness | none (no call) | none: Groq 429, tokens per day 199426/200000 used on gpt-oss-120b |
| E2 | gemini_native 3.5 flash-lite | Groq qwen3.8-27b | 1 | quota_error | not recorded | no (no persona end_call) | call dropped | call_dropped | bot 429 on qwen tokens per day (about 198.9k/200k used) |
| E2 | same | same | 2 | quota_error | not recorded | no | call dropped | call_dropped | same 429 |
| E2 | same | same | 3 | quota_error | n/a | n/a | n/a | n/a | judge (Groq gpt-oss-20b) also 429 |

Summaries: `exp-E1-20261124-140612-summary.md`, `exp-E2-20261124-140814-summary.md`.

Conclusion: neither setup could be evaluated. Every Groq free model was at its daily token cap, which blocked E1's persona at once and E2's bot and judge. These are quota errors, not evidence about the persona. The baseline (`end_call-table.md`) stands, and no setup was adopted. `evals/simulator.yaml` is unchanged. To retry, wait for the Groq rolling window to clear (the 429s said about 2 to 5 minutes for single-request headroom, but the 24 h total is nearly full), or run E2 with the Gemini bot (default provider) and a Gemini judge so Groq is not needed.
