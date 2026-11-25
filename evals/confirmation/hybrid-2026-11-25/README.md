# Hybrid test setup, 2026-11-25

Setup: bot Gemini `gemini-3.5-flash-lite` (default provider), simulated restaurant local Ollama `qwen3:8b` (`evals/simulator.yaml`),
judge and explainer throttled Gemini (`evals/judge-gemini-throttled.yaml`). Text mode, `--sleep 30`, runner on port 7861.
Judge: the first try with the Groq `openai/gpt-oss-20b` judge (`evals/judge.yaml`) answered a 1-request probe (HTTP 200) but
the run's judge questions failed with "GroqLLMService#0 did not answer within 10.0s". The probe showed a limit of 8000 tokens per
minute, and the judge sends about 7 parallel questions. That run was stopped and discarded, and the throttled Gemini judge was used.
No quota 429 reached the bot or the persona; no Gemini daily cap was hit. Two judge calls got a Gemini HTTP 503.

"Gemini req" = Gemini bot LLM calls (usage lines in `bot.log`). "Persona turns" = restaurant replies, which the all-Gemini setup
sent to Gemini too, so bot + persona = what one call used before. Summaries: `*-summary.md` here (its "requests" column = bot + persona).

| Scenario | Run | Att | Status | Judge | Deterministic check | Persona in role | Persona same-turn hang-up | Persona wrote customer lines | Bot outcome | Violations | Gemini req (bot) | Persona turns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| minimum_reachable | 135701 | 1 | pass | yes | ok | y | n | n | ordered 2400 (2 biryani, 3 raita) | none | 11 | 4 |
| staff_asks_details | 135825 | 1 | pass | yes | ok | y | n | n | ordered 1950 | none | 8 | 4 |
| happy_path | 135956 | 1 | fail | no (conduct 0.875, needs 1.0) | ok | y | n | n | ordered 2100 | none (the bot asked about the minimum order 3 times, then re-checked the total) | 16 | 8 |
| sold_out_no_substitute | 140244 | 1 | pass | yes | ok | y | n | n | not_ordered | none | 4 | 3 |
| terse_staff | 140348 | 1 | quota_error | n/a | n/a | y | n | n | ordered | none | 15 | 9 |
| terse_staff (retry) | 140659 | 1 | fail | no | outcome not_ordered, expected ordered | partly: quoted a wrong total (1350 for Rs 2100 of food and fees) and repeated it | n | n | not_ordered | none | 26 | 8 |
| terse_staff (retry) | 140659 | 2 | quota_error | n/a | n/a | y | n | n | call completed | none | 14 | 7 |

terse_staff attempt 140348/1 is a quota_error because the judge got an HTTP 503 from Gemini. Its call itself ended with `ordered` and no violation.
pass@k stops at the first pass, so minimum_reachable and staff_asks_details ran 1 of the 3 attempts.

## Gemini requests per call

- Hybrid, bot only (7 attempts): 94 requests, **13.4 per call** (range 4 to 26).
- Same 7 calls if the persona had also used Gemini (bot + persona): 137, **19.6 per call**. Hybrid is 69% of that, so **about 31% fewer, not half**.
- Earlier all-Gemini calls that ran to the end (`../persona-hangups/gemini-*-summary.md`: sold_out 11, terse_staff 20, minimum_reachable 18/20/10, happy_path 17) average 16 per call (n=6; those calls were shorter because the bot often gave up early).
- Reason it is not half: the bot makes more than one LLM call per restaurant turn (every tool call round trip), so the persona is only about 30% of the requests.
- The judge on Gemini adds about 8 more requests per call (not counted above, and the old all-Gemini runs had it too). With the Groq judge those would not be Gemini requests, but Groq's 8000 tokens/min cap currently makes it time out.

## Persona quality (qwen3:8b, thinking off)

Over 7 calls it never hung up, never wrote the customer's lines, and stayed in role. Flaws: in minimum_reachable it quoted food Rs 1950
then agreed adding raitas met the minimum; in terse_staff attempt 140659/1 it kept answering "1350. 45 minutes." with a wrong total.
That wrong total is what the terse persona is for; the bot's reaction is the bug candidate below.

## Bot issues seen (not fixed here)

- terse_staff 140659/1: after the restaurant insisted on 1350, the bot edited its own order to match the quote (removed items, set the delivery fee to 0, added a chicken biryani at Rs 1350), called `confirm_order` many times, then ended `not_ordered` with a wrong reason ("exceeds the budget of 2500"). It did not violate a rule, but it fabricated an item price to match a quote.
- happy_path 135956: the bot asked about the minimum order 3 times after "no minimum" and called `set_minimum_order` 3 times; the judge's conduct metric fell to 0.875.
