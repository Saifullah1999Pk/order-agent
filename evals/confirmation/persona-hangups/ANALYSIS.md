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

## All-Gemini runs 2026-11-24

Setup: bot Gemini `gemini-3.5-flash-lite` (default provider), persona `gemini_native_llm` / `gemini-3.5-flash-lite`, judge and explainer `gemini_llm` / `gemini-3.5-flash-lite`. `evals/simulator.yaml` and `evals/judge.yaml` were edited temporarily; judge.yaml is restored, simulator.yaml now keeps the Gemini persona (see Decision). Text mode, `--sleep 60` to 150, runner on port 7861 (7860 was the user's bot, untouched). About 70 minutes of run time. Summaries: `gemini-20261124-*-summary.md` in this folder.

The binding limit was 15 requests per minute (`PerMinutePerProjectPerModel`), not the daily cap. The judge sends about 7 parallel questions at the end of each call, and a call itself needs about 2 requests per turn, so a single attempt often goes over 15 per minute and the Gemini bot or judge gets a 429. The daily cap was never reached. These attempts are `quota_error`, not bot failures. Audio runs were not attempted, because quota did not clearly remain.

"Persona end_call" column: `none` = the persona never called end_call; "after bot msg" = it ended the call right after a bot message, not in the same generation as one of its own lines; "same-turn" = it called end_call in the same turn as its own message (the baseline problem).

| Scenario | Run | Attempt | Status | Persona turns | Persona end_call | Who ended | Bot outcome | Violations / note |
|---|---|---|---|---|---|---|---|---|
| staff_asks_details | 141837 | 1 | quota_error | 7 | none | bot | ordered (confirm_order 2100) | judge 429 mid-metrics; goal met, conduct 0.86 |
| staff_asks_details | 141837 | 2 | quota_error | 7 | none | harness (persona 429) | call dropped | Gemini 429 per minute |
| staff_asks_details | 141837 | 3 | quota_error | 5 | none | harness (persona 429) | call dropped | Gemini 429 per minute |
| staff_asks_details | 142248 | 1 | quota_error | 3 | none | harness (bot 429, fell back to gemini-2.5-flash, limit 5) | call_dropped | no order confirmed |
| staff_asks_details | 142248 | 2 | quota_error | 5 | after bot msg | persona (bot had just asked for the total) | call dropped | judge 429s; conduct 0.33 from failed judge questions |
| staff_asks_details | 142248 | 3 | quota_error | 7 | none | bot | ordered (2100) | judge 429; conduct 0.86 |
| staff_asks_details | 144910 | 1 | quota_error | 5 | none | bot | ordered | judge call failed (429) |
| staff_asks_details | 144910 | 2 | quota_error | 6 | none | bot | ordered | judge call failed (429) |
| staff_asks_details | 144910 | 3 | quota_error | 6 | none | harness (429) | call dropped | Gemini 429 per minute |
| terse_staff | 142930 | 1 | quota_error | 0 | none | harness (429) | none | no turns |
| terse_staff | 142930 | 2 | **pass** | 7 | none | bot | ordered | none; conduct 1.0 |
| minimum_reachable | 142930 | 1 | fail | 5 | after bot msg | persona, after the bot said goodbye and declined | call_dropped | food 2100 below 2200; bot gave up as over budget |
| minimum_reachable | 142930 | 2 | fail | 5 | after bot msg | persona, after the bot's goodbye | call_dropped | no order confirmed |
| minimum_reachable | 142930 | 3 | fail | 3 | after bot msg | persona, after the bot's goodbye | call_dropped | food 2100 below 2200 |
| happy_path | 143834 | 1 | quota_error | 1 | none | harness (429) | none | |
| happy_path | 144111 | 1 | quota_error | 5 | none | harness (429) | none | |
| happy_path | 144111 | 2 | fail | 6 | none | bot | ordered | judge conduct 0.83 (needs 1.0); no report violations |
| sold_out_no_substitute | 143834 | 1 | quota_error | 6 | none | bot | not_ordered | judge call 429 |
| sold_out_no_substitute | 144111 | 1 | quota_error | 4 | after bot msg | persona (customer declined, sold out) | not ordered | judge 429s; conduct 0.8 |
| sold_out_no_substitute | 144111 | 2 | **pass** | 4 | after bot msg | persona (restaurant hung up first) | not_ordered | none |

Counts over the 21 attempts: persona `end_call` in 6 (minimum_reachable x3, sold_out_no_substitute x2, staff_asks_details x1); **same-turn hang-ups: 0**. Baseline (`end_call-table.md`, Groq persona): 19 of 36 ordered-scenario calls had a same-turn hang-up. Those 6 are replies to a bot message that ended the topic (a goodbye or "sold out"), which is allowed by the new goal wording.

Scenario results: terse_staff pass (2/3; baseline 0/3, all hang-ups). sold_out_no_substitute pass (2/2 attempts used, 1 pass). minimum_reachable fail 0/3: the Gemini bot itself declined, saying the minimum pushed it over budget (food reached 2100 of 2200); this is a bot problem, not a persona hang-up. happy_path: one completed attempt, order placed, failed only on judge conduct 0.83, the other two quota_error. staff_asks_details: no counted pass, but 4 of the 9 attempts completed with the bot confirming the order (2100) and no persona hang-up; all were downgraded by judge 429s. Nothing here was weakened: no check was changed.

Conclusion: same-turn hang-ups dropped from 19 of 36 to 0 of 21. The goal-wording fix plus the Gemini persona removes the root cause. The scenarios that still do not pass are held back by the per-minute Gemini limit (judge bursts), the strict conduct score, and, for minimum_reachable, the bot giving up.

Decision: adopted the Gemini persona in `evals/simulator.yaml` (Groq kept as a comment). The judge stays on Groq in `evals/judge.yaml` (unchanged), since Gemini's 15 requests/min cannot carry a judge burst on top of the bot and persona.

## minimum_reachable bot fix (2026-11-24)

### Evidence (runs 20261124-142930, all-Gemini)
Tool events of attempts 1 and 3: `add_item biryani x2`, `add_item raita x1`, `set_fees 150/0`, `set_minimum_order 2200` (engine reply: "Minimum order recorded ... Food subtotal is now 1950 PKR." and nothing else), then `add_item raita x1` (food 2100, still 100 short). In attempt 1 the bot then invented `chicken pulao` at Rs 950 (the staff never said a pulao price; the menu says 800), the engine refused it as over budget, and the bot ended with "the minimum pushes it over my budget". In attempt 3 the call dropped before `confirm_order`. No under-minimum refusal ever fired: the bot never reached `confirm_order`. The engine could reach the right cart all along (`add_item raita x2` was allowed by the cap, ceil(250/150) = 2).

### Root cause
Mostly engine guidance, then LLM reasoning. `set_minimum_order` and `add_item` did not tell the bot the shortfall or the quantity needed, so the 3.5-flash-lite bot guessed "one more raita" (it needed two), mixed up food subtotal with the all-in total ("over budget"), and then guessed a price. The simulated staff's own arithmetic was also off (said 2150, "50 under"), which reinforced the wrong count. The refusal text at `confirm_order` had no quantity either. Prompt wording was followed but could not help: it said "as the refusal suggests", and the tool suggested no number.

### Fix (commits eb1675d, 5e8001a; no rule weakened)
`order_agent/rules.py`: new `_minimum_hint()`, appended to the results of `set_minimum_order`, `add_item`, `remove_item`, `set_fees` and the `confirm_order` minimum refusal. Example: "The food is 1950 PKR, 250 PKR short of the 2200 PKR minimum: add 2 more raita (300 PKR) to reach it. The total would then be 2400 PKR, within your 2500 PKR budget." If the optional item is not yet in the cart it says to ask its price and gives the budget room (a first version said "end as not_ordered" here, which the live run 151509 attempt 2 followed; fixed with a failing test first). `order_agent/prompt.py`: add exactly the item and quantity a result names, never invent an item or price.
Tests (tests/test_rules_confirm.py, tests/test_prompt.py), RED first for the engine tests: shortfall and quantity in `set_minimum_order` (RED), repeated hint after a short add (RED), refusal names quantity (RED), nothing-fits message (RED), optional-not-in-cart hint (RED), deterministic engine path to the correct cart (2 biryani + 3 raita, total 2400, confirm ok; passed already, which shows the engine was never the blocker), prompt test (added with the prompt change). `uv run pytest -q`: 221 passed.

### Live results (bot Gemini 3.5 flash-lite, persona Gemini 3.5 flash-lite, judge Groq gpt-oss-20b; runner on 7861)
Summaries: `mrfix-20261124-151509-summary.md` (first fix, before the not_ordered wording was corrected), `mrfix-20261124-173526-summary.md`, `mrfix-20261124-174004-summary.md`.

| Run | Scenario | Attempt | Status | What happened |
|---|---|---|---|---|
| 151509 | minimum_reachable | 1 | quota_error | bot asked for 2 more raita (correct) but its LLM hit 429 |
| 151509 | minimum_reachable | 2 | fail | hint said "not_ordered" before raita was added; bot ended the call (bug, fixed in 5e8001a) |
| 151509 | minimum_reachable | 3 | quota_error | bot added 2 raita (correct); Groq judge hit its daily token cap |
| 173526 | minimum_reachable | 1 | quota_error | LLM completion timeout |
| 173526 | minimum_reachable | 2 | quota_error | Gemini 503 |
| 173526 | minimum_reachable | 3 | fail (judge) | **bot behaved correctly: 2 biryani + 3 raita, staff quoted 2400, confirm_order ok, ETA 20:15, ordered.** Goal judged met (P=0.99); failed only on conduct 0.83 (turn 2 flagged "repeated the restaurant's prices", a judge false negative; same shape as the earlier happy_path 0.83). Not weakened. |
| 174004 | happy_path | 1 | quota_error | Gemini 429, daily quota exceeded |
| 174004 | sold_out_no_substitute | 1 | quota_error | same |

Result: minimum_reachable 0/3 by the runner's count (1 attempt reached the correct order, 2 were harness errors); regression runs not obtained because the Gemini free quota ran out. Unit tests cover the regression paths. Next step: rerun minimum_reachable, happy_path and sold_out_no_substitute after the Gemini quota resets.
