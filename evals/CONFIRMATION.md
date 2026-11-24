# Task 8 confirmation runs: happy_path, text mode, real bot.py

Command per attempt (fresh bot each time, about 60-75 s apart):
`ORDER_BRIEF=evals/briefs/happy_path.yaml ORDER_CALL_TIME=2026-11-23T19:30:00 ORDER_REPORTS_DIR=reports/confirm uv run python bot.py --port 7860`, then
`uv run pipecat eval run evals/scenarios/happy_path.yaml --bot-url ws://localhost:7860/ws -v --logs-dir <dir>`.
4 attempts used (the whole budget). Port 7860 was free. Bot stopped after each.

**Result: confirmation NOT met: 1 clean pass out of 4 attempts (attempt 4).** Two runs completed
without harness errors (3 and 4); only 4 is a true pass.

| # | Harness | Judge | Persona as staff? | Bot report | Files |
|---|---|---|---|---|---|
| 1 | FAIL: judge call 429 (free tier, 15 req/min/model) after a bot-side 429 mid-call; ended by silence | not scored | yes | call_dropped, no order (bot's own LLM got 429 after confirming; total Rs 2100) | attempt1_quota/ |
| 2 | FAIL on goal: judge verdicts for 4 of 6 metric turns failed with 429; persona gave up | P(yes)=0.00 | yes | call_dropped, no order | attempt2/ |
| 3 | no harness error, "PASS" | P(yes)=1.00 (false pass) | yes | call_dropped, no order: bot's LLM returned an empty reply after `set_fees`, bot went silent, run ended by silence after 4 persona turns | attempt3/ |
| 4 | PASS, ended by bot (`end_call`), 21.8 s | P(yes)=1.00, politeness 1.00, no_invention 1.00 | yes | ordered; 2 x chicken biryani @900, 1 x raita @150, delivery 150, cart total Rs 2100, delivery by 20:15 | attempt4/ |

Each directory holds the conversation JSON (`eval/happy_path__happy_path.conversation.json`), the
eval log and the bot's report (`<timestamp>.json/.txt`).

## Findings
1. **Persona acts as restaurant staff** in all 4 runs (welcomes, quotes menu, fee, 45 min). It never acted as an assistant.
2. **Quota is the main harness hazard.** The 15 requests/min limit on gemini-3.5-flash-lite is shared by bot, persona and judge. The judge alone sends 1 request per metric per bot turn plus 1 for the goal, so a single run bursts past the limit (runs 1 and 2). Task 9 must map these to `quota_error`; the harness reports them as "judge call failed ... Error code: 429" or as a failed goal, so the message has to be inspected, including in the per-metric lines.
3. **Judge false pass (run 3):** P(yes)=1.00 although the bot never ordered. The deterministic report check (outcome ordered, total) must override the judge, as the spec says.
4. **Bot defect, run 3:** an empty assistant turn after a tool call (the root cause is a swallowed bot-LLM 429: Pipecat pushes an error frame and the turn ends with empty content, see After Task 8b; it is not an empty completion) leaves the bot silent for the rest of the call (no retry or nudge). Run 1 shows the same shape from a 429.
5. **Bot defect, run 4:** staff said "nineteen hundred fifty" but the bot called `confirm_order(quoted_total_pkr=2100)`, so it passed its own cart total rather than the quote, defeating the mismatch guard (Review Focus 3). The persona's 1950 was partly the persona's own arithmetic (the bot never stated quantities of raita), but the bot should have confirmed or corrected it. The judge did not catch it.
6. Bot style: it asks odd questions instead of stating the order up front ("make it less spicy?" before ordering). Prompt tuning, not an eval problem.

## After Task 8b
Same command as above (`ORDER_REPORTS_DIR=reports/confirm8b`, logs in `evals/confirmation/after-8b/`), 2 attempts, bot restarted between them, ~75 s apart. Port 7860 was free.

| # | Harness | Judge | Bot report | Quoted vs cart | Nudges |
|---|---|---|---|---|---|
| 1 | error: persona/judge call got 429 (quota_error) after 5 persona turns | not scored | call_dropped (run cut off by the harness error) | none reached | none |
| 2 | "PASS", ended by silence after 5 persona turns (55 s) | P(yes)=1.00 (false pass), `conduct` 1.00 over 5/5 turns | call_dropped, no order | staff quoted Rs 2150; the bot cart was 2 x 900 + 150 raita + 150 fee = 2100, so the persona misadded by 50 and the bot never reached confirm_order (it stalled first) | 2 (both failed with 429, then stopped as designed) |

Findings:
- The opening is fixed: in both runs the bot stated its order (2 chicken biryani, raita, delivery) right after the greeting and then asked about availability and prices.
- Attempt 2 stalled because the bot's own Gemini call returned **429** right after `set_fees`; Pipecat pushed an error frame and the assistant turn ended with empty content. This is the same shape as attempt 3 of Task 8 (empty turn after `set_fees`), so the "empty reply" is most likely a swallowed LLM error (429) rather than an empty completion. The bot logs of Task 8 were not kept, so that is not proven for attempt 3.
- The nudge fired twice and stopped at 2, as designed. Both nudges were also rejected with 429, so the nudge cannot fix quota exhaustion; it only covers a one-off empty reply.
- Not confirmed: no run reached `confirm_order`, so the quote-fidelity prompt fix is only covered by prompt unit tests. The judge again passed a run with no order; the deterministic report check must override it (Task 9).
- Free-tier quota (15 requests/min shared by bot, persona and judge) is still the limiting factor for live confirmation.

## After Task 8b fix round 1
Changes under test: nudge flag tracked per LLM run (`NudgeTracker`), 3 s pause before a nudge, bot-side retry on 429/503 (3 attempts, 2 s start, via `http_options`), persona and judge moved to `gemini-2.5-flash` (bot stays on `gemini-3.5-flash-lite`). 2 attempts, 70 s apart, port 7860 free, bot stopped after each. Evidence: `evals/confirmation/after-8b-fix1/`.

| # | Harness | Judge | Bot report | Quoted vs cart | Nudges / bot 429s |
|---|---|---|---|---|---|
| 1 | FAIL "end_call": persona ended the call after 4 turns, before the order was confirmed | P(yes)=0.05; `conduct` 3 of 5 turns failed with "judge call failed: did not answer within 10.0 s" (judge timeouts on 2.5-flash, harness errors, not bot failures) | call_dropped, no order | none reached (staff never quoted a total) | 0 / 0 |
| 2 | error: persona call got 429 on gemini-2.5-flash after 2 persona turns (quota_error) | not scored | call_dropped | none | 0 / 0 |

Findings: the bot side was clean this round (no 429s, no empty turns, no nudges needed). The bot still asks fee/tax/minimum repeatedly and never asks for the total (attempt 1), so the persona gave up; prompt tuning candidate. gemini-2.5-flash on this key is slow for the judge (10 s timeout) and rate limited for the persona, so the model split did not by itself produce a clean confirmation. Not confirmed live: nudge-in-anger and the retry path (no 429 hit the bot).

## After Task 8c (Groq)
Changes under test: persona and judge moved to Groq free tier (persona `openai/gpt-oss-120b`; judge and explainer `openai/gpt-oss-20b`, reasoning_effort low) via `order_agent.eval_llm.groq_llm`; bot stays on `gemini-3.5-flash-lite`; prompt asks fees/minimum once, no re-asking, asks total and time once items agreed, and only calls add_item after a stated price. Evidence: `evals/confirmation/after-8c/`. Port 7860 was free; bot restarted per attempt, stopped after each.

Model selection (attempts 1-7, not counted as confirmation): gpt-oss-120b as judge timed out at Pipecat's fixed 10 s (attempts 2, 7); qwen/qwen3.8-27b as persona broke role ("can't order food from the customer", attempt 3); gpt-oss-20b as persona ended the call at once (attempt 5). gpt-oss-120b as persona sometimes writes the next customer lines inside its own reply (attempts 2, 4, 6, 8) or ends the call early (1, 6, 9).

| # | Harness | Judge | Bot report | Quoted / cart / persona total | Clean? |
|---|---|---|---|---|---|
| 8 (weaker pass) | PASS, ended by bot | P(yes)=0.99, conduct 1.00 | ordered | 2100 / 2100 / 2100 | yes |
| 9 | FAIL: persona ended call before any total; bot had invented biryani price 950 | not met | call_dropped | none / 2200 / none | no |
| 10 | PASS, ended by bot (after prompt rule on add_item price and persona wording) | P(yes)=1.00, conduct 1.00 | ordered | 2100 / 2100 / 2100 | yes |
| sold_out_no_substitute | PASS, ended by persona end_call | P(yes)=0.95 | call_dropped (bot never called end_call; persona ended first) | n/a | judge pass, but report is not `not_ordered` |

2 clean passes of happy_path (attempts 8 and 10). Caveat: the persona still sometimes concatenates later turns into one message; the totals in 8 and 10 were nevertheless stated by the persona in separate messages too.

Attempt 8 is a weaker pass: it ran on an earlier configuration than the committed one (no persona wording, no add_item price rule), and the customer's "yes"/placing of the order was written by the persona inside its own concatenated message rather than as a separate reply. Attempt 10 has the same caveat about the concatenated tail but ran on the prompt rules (bot side) and the happy_path persona wording.

### Fix round 1 (persona wording in all 11 scenarios, committed state)
Every persona now has "Reply with only your own next line ... Never write the customer's lines." and a per-scenario "Do not end the call until ..." (ordered scenarios: total and delivery time stated and order confirmed by the customer; not-ordered scenarios late_delivery, minimum_unreachable, price_over_budget, sold_out_no_substitute: customer said goodbye or clearly will not order). tests/test_scenarios.py asserts both for all 11. Evidence: `evals/confirmation/after-8c/fix1/`.

| # | Harness | Judge | Bot report | Quoted / cart / persona total | Clean? |
|---|---|---|---|---|---|
| hp1 | FAIL: conduct 0.75, judge claimed the bot "quoted a price" it did not say (judge error) | goal P(yes)=0.99 | ordered | 2100 / 2100 / 2100 (concatenated message) | no |
| hp2 | FAIL on end_call by persona before bot confirmed | goal not met | call_dropped | none / 2100 / none | no |
| hp3 | PASS, ended by bot | P(yes)=1.00, conduct 1.00 4/4 | ordered | 2100 / 2100 / 2100, said by persona in separate messages | yes |
| sold_out_no_substitute | PASS, ended by persona end_call after 1 turn | P(yes)=0.98 | call_dropped (bot did not call end_call itself; persona hung up right after the bot declined seafood) | n/a | judge pass only |

Clean passes on the committed state: 1 (hp3); with attempt 10, 2 total. The persona still concatenates lines sometimes despite the new wording.
