# Short live check, 2026-11-25 (branch evals/2026-11-25-short-check, from main 26400dc)

Command: `run_suite.py --only happy_path,terse_staff,minimum_reachable,sold_out_no_substitute --attempts 1 --sleep 30`. Run dir `evals/results/20261125-145529`, 14:55-15:12 (about 17 min). Defaults only: bot Gemini gemini-3.5-flash-lite, persona Ollama qwen3:8b, judge throttled Groq gpt-oss-20b. 1 attempt each, so this is a smoke check, not a rate.

| scenario | status | judge goal / conduct | deterministic | bot outcome | lock refusals | judge time | bot LLM calls |
|---|---|---|---|---|---|---|---|
| happy_path | fail | not met / 0.67 | outcome not_ordered, expected ordered; no PRICE violation | not_ordered | 1 (confirm_order, quoted 1250 vs cart 2100) | 241 s | 11 |
| terse_staff | fail | not met / 1.00 (no_repeat_loop 1.00) | outcome not_ordered, expected ordered; no PRICE violation | not_ordered | 2 (confirm_order, quoted 1950 vs cart 2100) | 301 s | 15 |
| minimum_reachable | pass | met 0.92 / 1.00 | clean | ordered, 2400 | 0 | 121 s | 11 |
| sold_out_no_substitute | pass | met 0.98 / 1.00 | clean | not_ordered (item sold out) | 0 | 121 s | 5 |

Judge time = eval.log time from end of call to verdict. Bot LLM calls counted from bot.log "Generating LLM response" lines (the summary "requests" column, 17/24/15/9, also includes persona turns).

Persona: in role in all 4; 0 same-turn hang-ups; 0 lines written for the customer.
Quota: no Gemini 429, no Groq 429, no judge question timeout. One Groq 400 ("Failed to validate JSON") on the judge explainer in happy_path; the judge retried and finished (the verdict was produced; the failure reasons for happy_path are slightly less detailed).

## Special attention
- terse_staff: the new behaviour worked. The persona gave 1950 (items only, no delivery fee), the engine refused confirm_order (cart 2100) with the itemise message, the bot asked "Could you please itemise the total for me?", got "Biryani 900, raita 150, delivery 150, total 1950", read the correct prices back and asked the restaurant to check, got 1950 again, was refused again and ended not_ordered. It never edited the cart or fees; price_corrected and corrected were false in every event. The scenario still counts as fail only because it expects `ordered` and the simulated restaurant never fixed its sum.
- happy_path: no false refusal. The one refusal was correct: the persona quoted 1250 for 2 biryani + raita + delivery (really 2100) and repeated "Rs 1250 is correct". The bot challenged ("I have it coming to twenty..." cut off), called confirm_order(1250), was refused, and ended not_ordered without a further itemise request (it was already told twice). Prices and fees matched the menu. Failure cause: qwen3:8b arithmetic. The judge also marked turn 2 (asking prices) as a conduct fail, which looks harsh.

## Verdict
Setup is healthy for a full unattended run. Bot, locks, price check, preflight, throttled judge (2-5 min, no timeouts) all behaved; no blocker. Caveats: (1) qwen3:8b wrongly quotes totals in happy_path and terse_staff, which will cost pass-rate regardless of the bot (consider a persona total check or retries); (2) the judge explainer can hit a Groq 400 (it recovered); (3) expect about 2-5 min of judge time per call, so budget time for a long run.
