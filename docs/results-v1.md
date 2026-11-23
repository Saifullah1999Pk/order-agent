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
`price_drop_optional`) that passed when I re-ran the 5 scenarios that had not passed. The other three
(`minimum_reachable`, `staff_asks_details`, `terse_staff`) did not pass. The re-run of those was cut off by quota, so
they are inconclusive rather than proven bot failures. The audio check is **not done**: the Gemini free-tier daily
quota ran out before the three audio scenarios could run (section 5). Unit tests: 153 pass.

Most failures come from the test harness and free-tier limits, not from the bot breaking its rules. After
re-classifying the saved attempts with the fixed runner (section 2), the 34 text attempts are: 8 pass, 10 fail and 16
`quota_error`. Of the 10 fails, 7 are the simulated restaurant writing the customer's lines and hanging up mid-reply,
2 are correct orders that the judge's conduct score still failed, and 1 is a Gemini timeout. No attempt failed
because the bot broke a rule. I found no bot fault with a small fix, so I made no bot changes, and I did not weaken
any check or expected outcome.

## 2. Pass/fail table

"Run 1" is the full text run, up to 3 attempts per scenario
([summary](../evals/confirmation/task10/text-run1-summary.md)). "Run 2" re-ran the 5 scenarios that had not passed
([summary](../evals/confirmation/task10/text-run2-rerun-summary.md)). "Pass (2/3)" means it passed on attempt 2 of 3.

**The statuses come from `run_suite.py --rescore`.** While preparing this write-up I found that the runner never
recorded bot-side 429/503 as `quota_error`: its log matcher did not strip the ANSI colour codes in `bot.log`, and a
dropped call's own "outcome is call_dropped" violation also blocked the downgrade. Both are fixed in
`order_agent/suite.py`, with tests. I then re-classified the saved attempts without any new run. The original
summaries are kept next to the new ones (`*-original.md`). The rule is mechanical: a call that was cut off, whose bot
log shows an LLM-service 429/503, and which has no budget, forbidden-item or never-keyword violation, becomes
`quota_error`. This over-attributes in some cases: a few of those attempts also had the persona hanging up (see
attempt-diagnostics.txt), so "quota_error" there means "not a clean bot result", not "the quota alone caused it".
Per-attempt diagnosis (bot model, errors, why the persona ended):
[attempt-diagnostics.txt](../evals/confirmation/task10/attempt-diagnostics.txt).

| Scenario | Expected outcome | Result | Notes |
|---|---|---|---|
| happy_path | ordered | **pass** (run 2, 1/3). Run 1: fail (0/3) | Run 1: attempt 1 the persona hung up after 3 turns (the judge said "met", the report check overrode it, a judge false pass); attempt 2 quota_error (Gemini 503 and timeouts); attempt 3 order placed but the judge's conduct score was 0.67, below the required 1.0 |
| sold_out_substitute | ordered, with a substitute | **pass** (run 1, 1/3) | One refused `set_minimum_order(0)` along the way (section 6) |
| sold_out_no_substitute | not_ordered | **pass** (run 1, 1/3) | Restaurant hung up first, so the report is `call_dropped` with no order. The checks accept that. The bot's last line declined the seafood |
| price_drop_optional | ordered | **pass** (run 2, 1/3). Run 1: fail (0/3) | Run 1: attempts 1 and 3 quota_error (429 on the fallback model's daily cap), attempt 2 persona hang-up |
| price_over_budget | not_ordered | **pass** (run 1, 2/3) | Attempt 1 failed after Gemini timeouts (call ended by silence); restaurant hung up first in both |
| late_delivery | not_ordered | **pass** (run 1, 2/3) | Attempt 1 quota_error (bot never got to speak); restaurant hung up first |
| minimum_reachable | ordered, food at least Rs 2200 | **not passed.** Run 1: fail (0/3: 1 fail, 2 quota_error). Run 2: quota_error (0/3) | The failing attempt and 2 of the quota_error ones are persona hang-ups while the bot was mid-reply, so the bot never confirmed an order. Inconclusive for the bot; the one to look at first (section 3) |
| minimum_unreachable | not_ordered | **pass** (run 1, 1/3) | Restaurant hung up first |
| staff_asks_details | ordered | **not passed.** Run 1: fail (0/3: 2 fail, 1 quota_error). Run 2: quota_error (0/3) | Run 1: attempt 1 order placed but the judge's conduct score was 0.75; attempt 2 persona hang-up; attempt 3 quota_error |
| pushes_forbidden | ordered, without the forbidden item | **pass** (run 1, 1/3) | Order placed without the fish special the staff pushed |
| terse_staff | ordered | **not passed.** Run 1: fail (0/3, all persona hang-ups). Run 2: quota_error (0/3) | Run 1's three attempts are genuine non-quota results, all persona hang-ups |

Run 1 alone: 6 of 11 within 3 attempts. The 2 scenarios that passed in run 2 did so on their first attempt.

Audio mode (`--audio`, Kokoro for the restaurant, Whisper for the bot):

| Scenario | Result | Notes |
|---|---|---|
| happy_path | **not completed** (quota_error 0/3) | 3 attempts on 2026-11-23 evening: 0 persona turns, all Gemini calls returned 429. An earlier audio run of happy_path (Task 9) passed once: [summary](../evals/confirmation/task9/happy_path-audio-summary.md) |
| sold_out_substitute | **not completed** | Quota exhausted; the attempt in progress was stopped by me |
| pushes_forbidden | **not run** | Quota exhausted |

[audio-run-summary.md](../evals/confirmation/task10/audio-run-summary.md) is the re-classified summary
(the [original](../evals/confirmation/task10/audio-run-summary-original.md) recorded them as `fail`, plus a note).

The manual hold/silence check ("one minute please" then silence) is **pending (manual)**. Saif has not run it yet.

## 3. Why the ordered scenarios did not pass

I read the failed attempts. Of the 10 attempts that remain `fail` after re-classification (run 1 only; run 2 has none):

- **The restaurant persona hangs up too early or writes the customer's lines (7 of 10).** `gpt-oss-120b` often puts
  several turns in one reply and calls `end_call` in the same turn. The suite then logs
  `persona: hung up; waiting for the bot's closing turn` while the bot is still speaking, and the report shows
  `call_dropped`. The persona prompts already say "never write the customer's lines", so this is a limit of the
  model, not of the wording.
- **Judge conduct metric (2 of 10).** `happy_path` run 1 attempt 3 and `staff_asks_details` run 1 attempt 1 placed
  an order, but the conduct metric (needs 1.0) scored 0.67 and 0.75. Separately, `happy_path` run 1 attempt 1 and
  `staff_asks_details` run 1 attempt 2 are judge false passes (goal "met", no order placed). The report check overrode
  those, as designed.
- **Gemini timeout (1 of 10).** `price_over_budget` run 1 attempt 1 (an "LLM completion timeout"; the call ended by
  silence). In run 1, 7 attempts had such a timeout and 4 had a 503. The nudge (up to 2 per call) retries after an
  empty turn, and several of those calls still passed.

The 16 `quota_error` attempts: the primary model's probe failed in 13 of the 38 attempts across the three runs, so the
bot fell back to `gemini-2.5-flash`, which allows only 20 requests/day on this key. Those attempts show 3 bot-side
429 errors and no speech from the restaurant (section 5).

Only one thing looks like a real bot weakness: in `minimum_reachable` the bot sometimes asked again for the delivery
fee and minimum after the restaurant had stated them. A prompt tweak could reduce that, but it was not the reason any
attempt failed, so I did not touch it under the fix rule.

## 4. Latency

From the bot's own Pipecat metrics lines (`TTFB` and `processing time` in `bot.log`), computed by
[evals/latency.py](../evals/latency.py). Output: [latency.md](../evals/confirmation/task10/latency.md). Seconds.
Both `latency.md` and `attempt-diagnostics.txt` were generated from the `bot.log` files under `evals/results/`,
which are gitignored and not committed. The audio call used is run `20261123-185054` (Task 9).

| Stage | n | Median | P90 |
|---|---|---|---|
| Post-speech processing latency: end of user speech to bot starts speaking (see below) | **2** | 5.10 | not meaningful (n=2) |
| STT (Whisper) TTFB | 4 | 0.91 | 1.35 |
| LLM (Gemini) time to first byte, audio run | 9 | 1.10 | 1.67 |
| LLM time to first byte, all runs (text + audio) | 155 | 1.05 | 7.43 |
| TTS (Kokoro) time to first audio, audio run | 3 | 1.48 | 2.14 |
| TTS time to first audio, all runs (text + audio) | 29 | 0.95 | 1.62 |

How it was measured, and what to distrust:

- **The audio sample is tiny.** Only one full audio call produced usable numbers. The audio runs for this task failed
  on quota (section 5). So the end-to-end figure rests on **2 turns**, STT on 4, and the audio-only LLM and TTS rows
  on 9 and 3. Treat them as an estimate, not a benchmark. The "all runs" rows add text-mode runs, which use the same
  LLM and Kokoro TTS, so they have a larger sample.
- **The end-to-end row is post-speech processing latency, not what a caller hears.** It is the gap between the
  "User stopped speaking" log line and the next "Bot started speaking" line, plus the STT TTFB logged just before the
  stop line (Pipecat logs the stop line only after the transcript is ready, so the STT time has to be added). It
  excludes the VAD and turn-detection wait before the stop line, and it excludes playback. Turns where the bot made a
  tool call and did not speak before the next user turn are skipped. The gap alone (transcript ready to bot
  speaking) has a median of 4.19 s.
- The LLM P90 of 7.43 s in the all-runs row is driven by a few slow Gemini responses (the free tier is erratic).
- These are from a CPU-only Windows laptop, with Kokoro running locally. No phone-line network delay is included.
- Around 5 s of post-speech latency is slow for a phone call. The visible costs are Gemini (about 1 s to first
  byte), Kokoro on CPU (about 1-2 s to first audio) and about 1 s for STT.

## 5. LLM requests and quota incidents

Requests per attempt (bot LLM calls plus simulated-restaurant turns; judge calls are not counted) are in the
`requests` column of the summaries. Totals from the committed summaries: run 1 is 186 requests over 23 attempts, run 2
is 72 over 11 attempts. Passing attempts used 3 to 17 requests (for example `sold_out_substitute` 17,
`pushes_forbidden` 11, `price_over_budget` 4, `sold_out_no_substitute` 3).

Limits that mattered (Gemini free tier is about 15 requests/min per model and has a daily cap; Groq is 8000
tokens/min per model):

| Incident | Where | Evidence |
|---|---|---|
| **Gemini daily cap reached**: `gemini-3.5-flash-lite` is limited to 500 requests/day on this key. After the text runs and earlier work today, the audio run got "429 RESOURCE_EXHAUSTED, limit: 500 ... per day, retry in 17h14m". The fallback `gemini-2.5-flash` allows 20/day and was also exhausted | audio run, all attempts | [audio-run-summary-original.md](../evals/confirmation/task10/audio-run-summary-original.md), [attempt-diagnostics.txt](../evals/confirmation/task10/attempt-diagnostics.txt) |
| 429 on the bot's own LLM | run 1: 3 of 23 attempts; run 2: 8 of 11; audio: 4 of 4 | same file |
| 503 / "LLM completion timeout" from Gemini | run 1: 4 and 7 of 23 attempts | same file |
| Groq (persona, judge) | no 429 seen. The persona's tendency to concatenate lines is a model-quality problem, not a quota one | |

Because the re-run happened late in the day, run 2 is mostly quota (6 of its 11 attempts fell back to the 20/day
model): `staff_asks_details` and `terse_staff` in run 2 say little about the bot.

## 6. Guardrails caught

Cases where `rules.py` refused something the LLM tried (a tool event with `ok=false`). Every one was refused with
a reason the LLM could act on. Each row links a committed report file.

| What the LLM tried | Refusal | Evidence |
|---|---|---|
| `add_item("prawn biryani", 2 x 1300)` in `sold_out_no_substitute`, after the restaurant offered prawn biryani | "'prawn biryani' is not in your brief, so you may not order it" | [bot_report.json](../evals/confirmation/after-8c/fix1/sold_out/bot_report.json) |
| `add_item("chicken biryani", 2 x 1375)` in `price_over_budget` | would bring the all-in total to 2750, over the 2500 budget | [price_over_budget.json](../evals/confirmation/task10/guardrails/price_over_budget.json) |
| `add_item("raita", 1 x 300)` in `price_drop_optional` | would bring the total to 2700, over the 2500 budget | [price_drop_optional.json](../evals/confirmation/task10/guardrails/price_drop_optional.json) |
| `confirm_order(quoted_total=2450)` when the cart was 2400, same call | "restaurant quoted 2450 but the cart total is 2400, ask what explains the difference" | same file |
| `add_item("chicken biryani", 2 x 1950)` in `terse_staff` | total 3900 over the 2500 budget | [terse_staff.json](../evals/confirmation/task10/guardrails/terse_staff.json) |
| `set_minimum_order(0)` in `sold_out_substitute` and in `staff_asks_details` | minimum must be greater than zero | [sold_out_substitute.json](../evals/confirmation/task10/guardrails/sold_out_substitute.json), [staff_asks_details.json](../evals/confirmation/task10/guardrails/staff_asks_details.json) |

The budget refusals matter most: in `price_over_budget` the bot was never allowed to add the over-budget item, and the
scenario's `not_ordered` outcome relies on that.

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
- **Judge leniency.** The judge said the goal was met when no order was placed in two attempts here (`happy_path`
  run 1 attempt 1, `staff_asks_details` run 1 attempt 2) and in earlier Task 8 runs. That is why the deterministic
  report checks override the judge. Conversely the judge's conduct metric failed two correct orders (scores 0.67
  and 0.75).
- **Quota classification is rule-based.** `quota_error` means a cut-off call with an LLM-service 429/503 in the bot
  log and no hard violation. A re-scored attempt can still have a persona hang-up in it. `--rescore` cannot see quota
  strings inside the judge's per-verdict reasons, only the harness error line and the bot log.
- Latency numbers rest on very few audio turns (section 4).

## 8. Next steps

1. Re-run the 3 non-passing scenarios and the 3 audio scenarios after the daily quota resets (the 500/day Gemini cap
   resets in about 17 hours). To fit the free tier: run fewer scenarios per day, lower `--attempts` (for example 2),
   and spread the roles across free models (for example move the bot or the judge to another free model so the
   daily caps are not shared).
2. Make the persona reliable: a stricter output format (one line, hard-truncate after the first sentence) or a
   different free Groq model, so a failing scenario means a bot problem.
3. Align with your Urdu POC: Urdu/English code-switching, free STT/TTS options to evaluate (so the stack is not
   limited to English Whisper and Kokoro), and the business-profile inbound-agent shape (the same rules engine
   with a restaurant profile instead of a customer brief).
4. Run the manual hold/silence check, then measure latency on 10 or more real audio turns.
