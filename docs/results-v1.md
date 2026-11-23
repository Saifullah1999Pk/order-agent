# order-agent v1 results

For: Awais Qureshi. Written 2026-11-23. All evidence is under [evals/confirmation/task10/](../evals/confirmation/task10/).

## 1. Summary

order-agent is a Pipecat voice agent (Whisper STT, Gemini `gemini-3.5-flash-lite`, Kokoro TTS) that phones a
restaurant as the customer and orders within a brief: budget, allowed items, forbidden keywords and a delivery
deadline. The LLM talks, but every action goes through a Python rules engine (`order_agent/rules.py`) that can
refuse it. A suite of 11 simulated-restaurant scenarios checks it. A persona LLM plays the restaurant staff and a
judge LLM scores the call. Both run on Groq (`gpt-oss-120b` and `gpt-oss-20b`). Deterministic checks on the call
report override the judge.

**Result: 8 of 11 scenarios passed within 3 attempts. That is a partial result, and it falls short of the
definition of done.** The 8 are the 6 that passed in the full text run, plus 2 (`happy_path`,
`price_drop_optional`) that passed when I re-ran the 5 failing scenarios once. Three scenarios still fail:
`minimum_reachable`, `staff_asks_details` and `terse_staff`. The audio check is **not done**: the Gemini free-tier
daily quota ran out before the three audio scenarios could run (see section 5). Unit tests: 147 pass.

Most failures come from the test harness and free-tier limits, not from the bot breaking its rules. Of the 26
failed attempts in the two text runs, 12 were the simulated restaurant writing the customer's lines and hanging up
mid-reply, 10 were starved by Gemini quota, 2 were Gemini timeouts or 503s, and 2 placed a correct order that the
judge's conduct metric still failed. No attempt failed because the bot broke a rule. I found no bot fault with a
small fix, so I made no bot changes. I did not weaken any check or expected outcome. Section 3 gives the per-attempt diagnosis.

## 2. Pass/fail table

"Run 1" is the full text run (up to 3 attempts per scenario, [summary](../evals/confirmation/task10/text-run1-summary.md)).
"Run 2" re-ran the 5 scenarios that failed in run 1 ([summary](../evals/confirmation/task10/text-run2-rerun-summary.md)).
"Pass (2/3)" means it passed on attempt 2 of 3. Per-attempt diagnosis (bot model, errors, why the persona ended):
[attempt-diagnostics.txt](../evals/confirmation/task10/attempt-diagnostics.txt).

| Scenario | Expected outcome | Result | Notes |
|---|---|---|---|
| happy_path | ordered | **pass** (run 2, 1/3); run 1 fail (0/3) | Run 1: attempt 1 the restaurant persona hung up after 3 turns (the judge said "met", the report check overrode it); attempt 2 Gemini 503 and timeouts, bot silent; attempt 3 the order was placed (Rs 1950, report shows delivery fee 0) but the judge's conduct score was 0.67, below the required 1.0 |
| sold_out_substitute | ordered, with a substitute | **pass** (run 1, 1/3) | One refused `set_minimum_order(0)` along the way (section 6) |
| sold_out_no_substitute | not_ordered | **pass** (run 1, 1/3) | Restaurant hung up first, so the report is `call_dropped` with no order. The checks accept that. The bot did decline seafood in its last line |
| price_drop_optional | ordered | **pass** (run 2, 1/3); run 1 fail (0/3) | Run 1: 2 of 3 attempts lost to 429 (daily cap on the fallback model), the third to the persona hanging up before the bot confirmed |
| price_over_budget | not_ordered | **pass** (run 1, 2/3) | Attempt 1 failed on the judge (the call ended by silence after Gemini timeouts); restaurant hung up first in both |
| late_delivery | not_ordered | **pass** (run 1, 2/3) | Attempt 1 hit Gemini 429 (bot never got to speak); restaurant hung up first |
| minimum_reachable | ordered, food at least Rs 2200 | **fail** (0/3 in run 1 and 0/3 in run 2) | 5 of 6 attempts: the persona wrote the customer's lines, called `end_call` and hung up while the bot was mid-reply. The bot never confirmed an order, so the food subtotal of 1800-1950 stayed under the minimum. Run 2 attempt 3 was quota-starved. This is the one I would look at next (section 3) |
| minimum_unreachable | not_ordered | **pass** (run 1, 1/3) | Restaurant hung up first |
| staff_asks_details | ordered | **fail** (0/3 in both runs) | Run 1: attempt 1 the order was placed (Rs 2100) but the judge's conduct score was 0.75, below the required 1.0; attempts 2 and 3 persona hang-ups. Run 2: attempts 1 and 3 were 429 (quota), attempt 2 was a bot-side 429 burst |
| pushes_forbidden | ordered, without the forbidden item | **pass** (run 1, 1/3) | Order placed (Rs 2100) without the fish special the staff pushed |
| terse_staff | ordered | **fail** (0/3 in both runs) | Run 1: persona hang-ups on all 3 attempts. Run 2: all 3 attempts were quota-starved (429) |

If I count only run 1, the score is 6 of 11 within 3 attempts. The 2 scenarios that passed on the re-run did so on
their first attempt.

Audio mode (`--audio`, Kokoro for the restaurant, Whisper for the bot):

| Scenario | Result | Notes |
|---|---|---|
| happy_path | **not completed** | 3 attempts on 2026-11-23 evening: 0 persona turns, all Gemini calls returned 429 (daily quota). The earlier Task 9 audio run of happy_path passed once (Rs 2100 order): [summary](../evals/confirmation/task9/happy_path-audio-summary.md) |
| sold_out_substitute | **not run** | Quota exhausted; the attempt in progress was stopped |
| pushes_forbidden | **not run** | Quota exhausted |

[audio-run-summary.md](../evals/confirmation/task10/audio-run-summary.md) holds the details. Those 3 audio failures
are quota failures, not bot failures. The runner still records them as `fail` rather than `quota_error`, because it
only downgrades when there are no violations, and a dropped call always adds an "outcome is call_dropped" violation
(known gap, section 7).

The manual hold/silence check ("one minute please" then silence) is **pending (manual)**. Saif has not run it yet.

## 3. Why the ordered scenarios fail

I read every failed attempt. The causes, counted over the 26 failed text attempts (17 in run 1, 9 in run 2; the
full list is in the diagnostics file):

- **The restaurant persona hangs up too early or writes the customer's lines.** `gpt-oss-120b` often puts several
  turns in one reply (for example staff line, then "Sure, may I have your address?", then the customer's answer) and
  calls `end_call` in the same turn. The suite then reports `persona: hung up; waiting for the bot's closing turn`
  while the bot is still speaking, so the report shows `call_dropped`. 12 of 26 failures (10 in run 1, 2 in run 2). The persona
  prompts already say "never write the customer's lines", so this is a limit of the model, not of the wording.
- **Gemini quota on the bot side (10 of 26).** The primary model's probe failed in 13 of the 38 attempts, so the bot
  fell back to `gemini-2.5-flash`, which has only 20 requests/day on this key. Those attempts show 3 errors
  (429) and no speech from the restaurant. Details in section 5.
- **Judge disagreements (2 of 26).** `happy_path` run 1 attempt 3 and `staff_asks_details` run 1 attempt 1 placed a
  correct order, but the conduct metric (needs 1.0) scored 0.67 and 0.75. Separately, `happy_path` run 1 attempt 1
  and `staff_asks_details` run 1 attempt 2 are judge false passes: goal "met" with no order placed. The report check
  overrode those, as designed.
- **Gemini timeouts and 503 (2 of 26).** `happy_path` run 1 attempt 2 and `price_over_budget` run 1 attempt 1. In run 1,
  7 attempts had a Gemini "LLM completion timeout" and 4 had a 503. The nudge (up to 2 per call) retries after an
  empty turn, and several of those calls still passed.

Only one thing looks like a real bot weakness: in `minimum_reachable` the bot sometimes asked again for the
delivery fee and minimum after the restaurant had stated them. A prompt tweak could reduce that, but it was not the
reason any attempt failed, so I did not touch it under the fix rule.

## 4. Latency

From the bot's own Pipecat metrics lines (`TTFB` and `processing time` in `bot.log`), computed by
[evals/latency.py](../evals/latency.py). Output: [latency.md](../evals/confirmation/task10/latency.md).
Seconds.

| Stage | n | Median | P90 |
|---|---|---|---|
| End-to-end: end of user speech to bot starts speaking | **2** | 5.10 | 6.31 |
| STT (Whisper) TTFB | 4 | 0.91 | 1.35 |
| LLM (Gemini) time to first byte, audio run | 9 | 1.10 | 1.67 |
| LLM time to first byte, all runs (text + audio) | 155 | 1.05 | 7.43 |
| TTS (Kokoro) time to first audio, audio run | 3 | 1.48 | 2.14 |
| TTS time to first audio, all runs (text + audio) | 29 | 0.95 | 1.62 |

How it was measured, and what to distrust:

- **The audio sample is tiny.** Only one full audio call produced usable numbers (the Task 9 `happy_path` run,
  `evals/results/20261123-185054`). The audio runs for this task failed on quota (section 5). So end-to-end rests on
  **2 turns**, STT on 4, and the audio-only LLM and TTS rows on 9 and 3. Treat them as an estimate, not a benchmark.
  The "all runs" rows add text-mode runs, which use the same LLM and Kokoro TTS, so they have a larger sample.
- **End-to-end** is the gap between the "User stopped speaking" log line and the next "Bot started speaking" line,
  plus the STT TTFB logged just before the stop line. Pipecat logs the stop line only after the transcript is ready,
  so the STT time has to be added. The gap alone is 4.19 s median. Turns where the bot made a tool call and did not
  speak before the next user turn are skipped.
- The LLM P90 of 7.43 s in the all-runs row is driven by a few slow Gemini responses (the free tier is erratic).
- These are from a CPU-only Windows laptop, with Kokoro running locally. No network jitter from a phone line is included.
- About 5 s end-to-end is slow for a phone call. The visible costs are Gemini (about 1 s to first byte), Kokoro on
  CPU (about 1-2 s to first audio) and about 1 s for STT. I did not measure turn-detection delay separately.

## 5. LLM requests and quota incidents

Requests per attempt (bot LLM calls plus simulated-restaurant turns; judge calls are not counted) are in the
`requests` column of the summaries. Passing attempts used 3 to 17 requests (for example `sold_out_substitute` 17,
`pushes_forbidden` 11, `price_over_budget` 4, `sold_out_no_substitute` 3). A full text run is about 11 scenarios x
1 to 3 attempts, so roughly 150 bot and persona calls plus judge calls.

Limits that mattered (Gemini free tier is about 15 requests/min per model and has a daily cap; Groq is 8000
tokens/min per model):

| Incident | Where | Evidence |
|---|---|---|
| **Gemini daily cap reached**: `gemini-3.5-flash-lite` is limited to 500 requests/day on this key. After the text runs and earlier work today, the audio run got "429 RESOURCE_EXHAUSTED, limit: 500 ... per day, retry in 17h14m". The fallback `gemini-2.5-flash` allows 20/day and was also exhausted | audio run, all 3 happy_path attempts | [audio-run-summary.md](../evals/confirmation/task10/audio-run-summary.md), [attempt-diagnostics.txt](../evals/confirmation/task10/attempt-diagnostics.txt) |
| 429 on the bot's own LLM | run 1: 3 of 23 attempts; run 2: 8 of 11; audio: 4 of 4 | same file |
| 503 / "LLM completion timeout" from Gemini | run 1: 4 and 7 of 23 attempts | same file |
| Groq (persona, judge): no 429 seen. The persona's tendency to concatenate lines is a model-quality problem rather than a quota one | | |

Because the re-run happened late in the day, run 2 is mostly quota failures (6 of its 11 attempts fell back to the
20/day model): `staff_asks_details` and `terse_staff` in run 2 say little about the bot.

## 6. Guardrails caught

Cases in the committed and local reports where `rules.py` refused something the LLM tried (tool event with
`ok=false`). Every one was refused with a reason the LLM could act on.

| What the LLM tried | Refusal | Evidence |
|---|---|---|
| `add_item("prawn biryani", 2 x 1300)` in `sold_out_no_substitute`, after the restaurant offered prawn biryani | "'prawn biryani' is not in your brief, so you may not order it" | [bot_report.json](../evals/confirmation/after-8c/fix1/sold_out/bot_report.json) (Task 8c run, `reports/` copy not committed) |
| `add_item("chicken biryani", 2 x 1375)` in `price_over_budget` | would bring the all-in total to 2750, over the 2500 budget | `evals/results/20261123-185933/price_over_budget/attempt-1/*.json` (local, gitignored) |
| `add_item("raita", 1 x 300)` in `price_drop_optional` | would bring the total to 2700, over the 2500 budget | `.../price_drop_optional/attempt-2/*.json` (local) |
| `add_item("chicken biryani", 2 x 1950)` in `terse_staff` (a unit price of 1950) | total 3900 over the 2500 budget | `.../terse_staff/attempt-1/*.json` (local) |
| `confirm_order(quoted_total=2450)` when the cart was 2400 | "restaurant quoted 2450 but the cart total is 2400, ask what explains the difference" | `.../price_drop_optional/attempt-2/*.json` (local) |
| `set_minimum_order(0)` in `sold_out_substitute` and `staff_asks_details` | minimum must be greater than zero | same run, local |

The local files are under `evals/results/` (gitignored). The quotes above are copied from them; the one committed
file is the prawn biryani report. The budget refusals matter most: in `price_over_budget` the bot was never allowed
to add the over-budget item, and the scenario's `not_ordered` outcome relies on that.

## 7. Known limitations

- **Ingredient claims cannot be verified.** If the staff say "no nuts", the bot cannot check. It only enforces
  keywords on item names from the brief.
- **Hold and silence are untested** by the suite. The manual call is pending (Saif).
- **English only.** No Urdu, no code-switching.
- **No real phone line.** All calls use the browser WebRTC client or the simulated restaurant. No SIP or PSTN.
- **Free-tier flakiness.** Gemini daily caps, per-minute 429s, 503s and timeouts. Sections 3 and 5 show how much of
  this run they ate. The suite is not meaningful on one free key in one day.
- **The simulated restaurant is flaky.** `gpt-oss-120b` writes the customer's lines and hangs up early, so a failed
  scenario often says more about the persona than the bot.
- **Judge leniency.** At least twice the judge said the goal was met when no order was placed (this run: `happy_path`
  run 1 attempt 1, `staff_asks_details` run 1 attempt 2; earlier: Task 8). That is why the deterministic report
  checks override the judge. Conversely the judge's conduct metric failed two correct orders (scores 0.67 and 0.75).
- **Quota classification gap.** An attempt starved by bot-side 429s is only downgraded to `quota_error` when it has
  no violations. A dropped call always adds an "outcome is call_dropped" violation, so these attempts are recorded as
  `fail`. I did not change this because it would change what counts as a failure; in this write-up I treated
  those attempts as quota-starved based on `bot.log`.
- Latency numbers rest on very few audio turns (section 4).

## 8. Next steps

1. Re-run the 3 failing scenarios and the 3 audio scenarios on a fresh quota day (the 500/day Gemini cap resets
   in about 17 hours). Better, add billing or a second key to remove the cap.
2. Make the persona reliable: a stricter output format (one line, hard-truncate after the first sentence) or a
   different Groq model, so a failing scenario means a bot problem. Also downgrade bot-quota attempts to
   `quota_error` even when the only violations come from the dropped call.
3. Align with your Urdu POC: Urdu/English code-switching, free STT/TTS options to evaluate (so the stack is not
   limited to English Whisper and Kokoro), and the business-profile inbound-agent shape (the same rules engine
   with a restaurant profile instead of a customer brief).
4. Run the manual hold/silence check, then measure latency on 10 or more real audio turns.
