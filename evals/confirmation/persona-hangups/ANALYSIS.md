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
