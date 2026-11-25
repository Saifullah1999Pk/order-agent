# order-agent v1 results

For: Awais Qureshi. Written 2026-11-23. All evidence is under [evals/confirmation/task10/](../evals/confirmation/task10/) and, for the bot on Groq, [evals/confirmation/task10b/](../evals/confirmation/task10b/).

## 1. Summary

order-agent is a Pipecat voice agent (Whisper STT, Gemini `gemini-3.5-flash-lite`, Kokoro TTS) that phones a
restaurant as the customer and orders within a brief: budget, allowed items, forbidden keywords and a delivery
deadline. The LLM talks, but every action goes through a Python rules engine (`order_agent/rules.py`) that can
refuse it. A suite of 11 simulated-restaurant scenarios checks it. A persona LLM plays the restaurant staff and a
judge LLM scores the call. Both run on Groq (`gpt-oss-120b` and `gpt-oss-20b`). Deterministic checks on the call
report override the judge.

(Later sections, 9 to 15, use different setups: other bot, restaurant and judge models. This 8 of 11 is the Gemini-bot, Groq-persona v1 run only.)

**Result: 8 of 11 scenarios passed within 3 attempts. That is a partial result, and it falls short of the
definition of done.** The 8 are the 6 that passed in the full text run, plus 2 (`happy_path`,
`price_drop_optional`) that passed when I re-ran the 5 scenarios that had not passed. The other three
(`minimum_reachable`, `staff_asks_details`, `terse_staff`) did not pass. The re-run of those was cut off by quota, so
they are inconclusive rather than proven bot failures. The audio check was **not done on Gemini**: the Gemini free-tier daily
quota ran out before the three audio scenarios could run (section 5). Later the same evening I re-ran them with the
bot on Groq (`qwen/qwen3.8-27b`): `happy_path` passed in audio, the other two did not, and the three text
retries could not run because Groq's daily token cap on the persona model was reached. That is kept apart from the
Gemini results in section 9. Unit tests: 198 pass.

Most failures come from the test harness and free-tier limits, not from the bot breaking its rules. After
re-classifying the saved attempts with the fixed runner (section 2), the 34 text attempts are: 8 pass, 10 fail and 16
`quota_error`. Of the 10 fails, 7 are the simulated restaurant writing the customer's lines and hanging up mid-reply,
2 are correct orders that the judge's conduct score still failed, and 1 is a Gemini timeout. No attempt failed
because the bot broke a rule. Also read the 4 `not_ordered` passes (`sold_out_no_substitute`, `price_over_budget`,
`minimum_unreachable`, `late_delivery`) with care: in all four the restaurant persona hung up first, after 1 to 3
persona turns. No order was placed, so no rule was broken and the check passes, but the bot did not itself end the call
with `not_ordered` and a reason, so these passes show "no bad order" more than "clean refusal". They are tagged
"hung up first" in the table. I found no bot fault with a small fix, so I made no bot changes, and I did not weaken
any check or expected outcome.

See section 10 for the spec definition-of-done table and for the re-runs on 2026-11-24.

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
| sold_out_no_substitute | not_ordered | **pass** (run 1, 1/3), **restaurant hung up first** (after 1 persona turn; no order placed) | Restaurant hung up first, so the report is `call_dropped` with no order. The checks accept that. The bot's last line declined the seafood |
| price_drop_optional | ordered | **pass** (run 2, 1/3). Run 1: fail (0/3) | Run 1: attempts 1 and 3 quota_error (429 on the fallback model's daily cap), attempt 2 persona hang-up |
| price_over_budget | not_ordered | **pass** (run 1, 2/3), **restaurant hung up first** (after 1 persona turn; no order placed) | Attempt 1 failed after Gemini timeouts (call ended by silence); restaurant hung up first in both |
| late_delivery | not_ordered | **pass** (run 1, 2/3), **restaurant hung up first** (after 3 persona turns; no order placed) | Attempt 1 quota_error (bot never got to speak); restaurant hung up first |
| minimum_reachable | ordered, food at least Rs 2200 | **not passed.** Run 1: fail (0/3: 1 fail, 2 quota_error). Run 2: quota_error (0/3) | The failing attempt and 2 of the quota_error ones are persona hang-ups while the bot was mid-reply, so the bot never confirmed an order. Inconclusive for the bot; the one to look at first (section 3) |
| minimum_unreachable | not_ordered | **pass** (run 1, 1/3), **restaurant hung up first** (after 2 persona turns; no order placed) | Restaurant hung up first |
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

Section 9 has a second audio run with the bot on Groq: `happy_path` passed (bot: qwen/qwen3.8-27b), the other two did not.

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

The 16 `quota_error` attempts (7 in run 1, 9 in run 2; from
[attempt-diagnostics.txt](../evals/confirmation/task10/attempt-diagnostics.txt)): 9 ran on the 20/day fallback model
`gemini-2.5-flash` after the primary's probe failed (8 of them with 0 persona turns, so the bot never heard the
restaurant, and 1 with 1 turn); each shows 3 bot-side 429 errors. The other 7 ran on `gemini-3.5-flash-lite` and did have
persona turns (1 to 4): 5 of them had 503s (and some timeouts) alongside a persona hang-up or silence, and 2 had 429s
(`minimum_reachable` run 2 attempt 2, `staff_asks_details` run 2 attempt 2). 4 of the 5 `minimum_reachable` `quota_error` attempts are among
these 7 (all with 2 to 4 persona turns and a persona hang-up; the 5th, run 2 attempt 3, was on the fallback model), so for those 4 "quota_error" means "not a clean bot result",
not "the quota alone caused it".

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
| Groq (persona, judge) | no 429 seen (in the Task 10 runs; Groq's daily token cap later blocked the Task 10b retries, see section 9). The persona's tendency to concatenate lines is a model-quality problem, not a quota one | |

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
- **The delivery ETA is measured from the call start**, not from when the order was confirmed, so a long call makes the
  deadline check more lenient. `deliver_by` also has no midnight crossing (a deadline just after midnight is not
  handled).
- **`ToolEvent.at` is the session time**, so every tool event in a report carries the same timestamp; the order of events
  is right, the timing is not.

## 8. Next steps

1. (Section 9 re-ran the audio scenarios on a Groq bot; the 3 text retries are still open.) Re-run the 3 non-passing scenarios, and the 2 failed audio scenarios, after the daily quotas reset (the 500/day Gemini cap
   resets in about 17 hours). To fit the free tier: run fewer scenarios per day, lower `--attempts` (for example 2),
   and spread the roles across free models (for example move the bot or the judge to another free model so the
   daily caps are not shared).
2. Make the persona reliable: a stricter output format (one line, hard-truncate after the first sentence) or a
   different free Groq model, so a failing scenario means a bot problem.
3. Urdu and Urdu–English (code-switched) conversation: free STT/TTS options to evaluate (so the stack is not
   limited to English Whisper and Kokoro), and the business-profile inbound-agent shape (the same rules engine
   with a restaurant profile instead of a customer brief).
4. Run the manual hold/silence check, then measure latency on 10 or more real audio turns.

## 9. Bot on Groq (2026-11-23 evening)

**Why it was run.** The Gemini free daily caps were used up for the day (a probe at about 20:00 found
`gemini-3.5-flash-lite` and `gemini-2.5-flash` returning 429, every other Gemini model 503). Saif approved Groq's free
tier for the bot as well, so the remaining runs used `ORDER_AGENT_LLM_PROVIDER=groq` (code:
`order_agent/llm_factory.py`; the Gemini path is the unchanged default). Every number below is from the Groq-bot
runs only and is **not merged** with the Gemini results above. A scenario that passed with either bot is labelled
"pass (bot: <model>)".

**Bot model: `qwen/qwen3.8-27b`** (the one free Groq chat model not used by the persona or judge, so it has its own
per-minute bucket). Its text smoke test (`happy_path`, 1 attempt) passed with correct tool calls
([summary](../evals/confirmation/task10b/smoke-happy_path-text-summary.md)). I also tried `openai/gpt-oss-20b` as the
bot in audio mode and stopped it after 2 failed attempts of `happy_path`, because it called a tool that does not
exist (`open_call`, rejected by Groq's tool validation) and one call ended `not_ordered` with "No response from
restaurant" ([partial summary](../evals/confirmation/task10b/audio-gpt-oss-20b-aborted-summary.md)). I did not try
`gpt-oss-120b` as the bot because it is the persona's model and shares its token bucket.

Setting up the Groq bot: reasoning is switched off for Qwen (`reasoning_effort=none`, so no `<think>` text is
spoken) and the "developer"-role opening and nudge messages are sent as "user" messages. On a 429 the Groq service
has no Gemini-style retry setting; the OpenAI client underneath retries 2 times with its default back-off. No bot-side
429 was seen in these runs.

Per-attempt turn counts and tool-call lists in this section come from the local (uncommitted, gitignored) `eval.log` and `conversation.json` files; the committed summaries do not contain them.

**Audio runs** (`--audio`, up to 3 attempts, `--sleep 20`;
[summary](../evals/confirmation/task10b/audio-qwen3.8-27b-summary.md)):

| Scenario | Result | Attempts |
|---|---|---|
| happy_path | **pass (bot: qwen/qwen3.8-27b)**, attempt 3/3 | 1: fail, call_dropped (the persona ended the call after 3 turns; the bot had made add_item x2 and set_fees but not confirm_order). 2: fail, no tool call at all, persona ended after 3 turns. 3: pass, add_item x2, set_fees, confirm_order, end_call |
| sold_out_substitute | **fail** (0/3) | All three `call_dropped`. The persona ended the call after 2 to 3 turns; the bot made no tool calls in attempt 3 and no `confirm_order` in any |
| pushes_forbidden | **fail** (0/3) | All three `call_dropped`; the persona ended the call after 4 to 5 turns. The bot made no tool call in attempts 1 and 2, and never `confirm_order` |

No attempt broke a budget, forbidden-item or never-keyword rule (the only violations in the summary table are outcome
and must-include). Reading the logs, two things together explain the fails. The same persona behaviour as in section
3 (it calls `end_call` after a few turns, so the call is cut off). And in 4 of 9 attempts qwen made no `add_item`
call even after the restaurant had stated prices, so the order was never built. The second is a weakness of this bot
model in audio mode, though Whisper's mis-hearings (for example "Each and Radar") may also play a part. I did not
change the prompt for it. The earlier Gemini audio pass of `happy_path` remains in
[task9](../evals/confirmation/task9/happy_path-audio-summary.md).

**Text retries (`minimum_reachable`, `staff_asks_details`, `terse_staff`): not run to a result.** Groq returned
"429 ... tokens per day (TPD)" for the persona model `openai/gpt-oss-120b`, which is a daily cap and cannot be
waited out with `--sleep`. 8 of the 9 attempts are `quota_error`; the 9th (`staff_asks_details` attempt 2) is recorded
as `fail`, but its `eval.log` shows the persona said nothing ("ended by silence after 0 turn(s)"), so it is the same
quota failure that the harness did not report as an error, not a bot result
([summary](../evals/confirmation/task10b/text-retries-persona-tpd-summary.md)). These three remain **not passed**.

**Latency on the Groq-bot audio runs** (bot `qwen/qwen3.8-27b`; 9 attempts; seconds; from
[latency-audio-qwen3.8-27b.md](../evals/confirmation/task10b/latency-audio-qwen3.8-27b.md), computed by
[evals/latency.py](../evals/latency.py), which now also reads `GroqLLMService` lines), next to the Gemini figures
from section 4:

| Stage | Groq bot: n | median | P90 | Gemini bot (section 4): n | median | P90 |
|---|---|---|---|---|---|---|
| End of user speech to bot speaking | 28 | 2.73 | 3.64 | 2 | 5.10 | n/m |
| Transcript ready to bot speaking (LLM + TTS) | 28 | 1.87 | 2.65 | 2 | 4.19 | n/m |
| STT (Whisper) TTFB | 31 | 0.86 | 1.13 | 4 | 0.91 | 1.35 |
| LLM TTFB | 51 | 0.55 | 0.84 | 9 | 1.10 | 1.67 |
| TTS (Kokoro) TTFB | 43 | 0.95 | 1.84 | 3 | 1.48 | 2.14 |

The Groq sample is larger (28 speaking turns), but it comes from 3 scenarios and 9 calls, many of them cut short, and
the measurement caveats of section 4 still apply (it excludes VAD/turn-detection wait and playback). The Gemini
column is the 2-turn sample. The gpt-oss-20b partial run is in
[latency-audio-gpt-oss-20b-aborted.md](../evals/confirmation/task10b/latency-audio-gpt-oss-20b-aborted.md) (2 turns; not
used).

**Updated scenario status** (overall, bot model in brackets):

| Scenario | Status |
|---|---|
| happy_path | pass in text (bot: Gemini, section 2); pass in text smoke and in audio (bot: qwen/qwen3.8-27b) |
| sold_out_substitute, pushes_forbidden | pass in text (bot: Gemini, section 2); audio **not passed** (bot: qwen/qwen3.8-27b, 0/3 each) |
| minimum_reachable, staff_asks_details, terse_staff | **not passed**; Groq text retries blocked by the persona's daily token cap |
| other 5 | unchanged from section 2 |

## 10. Definition of done (spec section 7) and the 2026-11-24 re-runs

| Spec section 7 item | Status | Why |
|---|---|---|
| Rules engine: full unit-test coverage of the 5.1 rules, written test-first | **Met** | 198 unit tests pass (`uv run pytest -q`), written test-first |
| Phase 1: Saif completes one successful order and one correct refusal by voice, including a hand-tested "please hold" | **Not met** | The voice order and the voice refusal were dropped by ruling on 2026-11-23: Saif asked the agents to test instead, so the automated simulated-restaurant evals replaced the manual calls. The hold/silence check is still pending (manual). See [phase1-results.md](phase1-results.md) |
| Phase 3: every scenario passes one text-only run with no `quota_error`; happy path plus two others pass one full-audio run | **Not met** | Text: 8 of 11 scenarios passed within 3 attempts (section 2); `minimum_reachable`, `staff_asks_details`, `terse_staff` have no pass, with or without Gemini or Groq as the bot (below). Audio: only `happy_path` passed (Gemini in Task 9, Groq qwen in section 9); `sold_out_substitute` and `pushes_forbidden` did not |
| Results write-up for the mentor: what passed, what failed, latency and quota numbers, limitations | **Met** | This document |

**Re-runs on 2026-11-24** (quota had reset; a 1-token probe of `gemini-3.5-flash-lite`, `gpt-oss-120b`, `gpt-oss-20b` and
`qwen/qwen3.8-27b` all answered). Evidence: [evals/confirmation/final-fix/](../evals/confirmation/final-fix/) (summaries
and [attempt-diagnostics.txt](../evals/confirmation/final-fix/attempt-diagnostics.txt)). They are kept apart from the
2026-11-23 results above, and the statuses were produced by the fixed runner. About 30 minutes of run time in total.

1. **Text retries, bot on Gemini `gemini-3.5-flash-lite`**: stopped by me after 4 attempts. The probe passed, but real
   calls returned "429 You exceeded your current quota" from the bot's own LLM (3 `minimum_reachable` attempts and 1
   `staff_asks_details` attempt, all `quota_error`; a 5th attempt was interrupted). I switched the bot to Groq rather than
   spend more Gemini calls
   ([summary](../evals/confirmation/final-fix/text-gemini-bot-aborted-summary.md)).
2. **Text retries, bot on Groq `qwen/qwen3.8-27b`** (3 attempts each, `--sleep 30`;
   [summary](../evals/confirmation/final-fix/text-retries-qwen-bot-summary.md)):

| Scenario | Result (bot: qwen/qwen3.8-27b, 2026-11-24) | Attempts |
|---|---|---|
| minimum_reachable | **fail** (0/3) | All 3 `call_dropped`: the persona hung up after 3 to 4 turns while the bot was mid-reply; the cart reached 1950 of the 2200 minimum, no `confirm_order` |
| staff_asks_details | **fail** (0/3) | All 3 `call_dropped` (the persona ended the call by `end_call` after 3 to 4 turns in 2 of them, hung up after 5 turns in the third); the judge said "met" in all 3, the report check overrode it |
| terse_staff | **fail** (0/3) | Attempt 1 `quota_error` (a 429 in the bot log), attempts 2 and 3 `call_dropped` after a persona hang-up (2 to 3 turns) |

3. **Audio, bot on `qwen/qwen3.8-27b`** (3 attempts each;
   [summary](../evals/confirmation/final-fix/audio-qwen-bot-summary.md)): `sold_out_substitute` **fail** (0/3) and
   `pushes_forbidden` **fail** (0/3). All 6 attempts are `call_dropped`: the persona ended the call by `end_call` after 3
   to 9 turns in 5 of them and hung up after 1 turn in the sixth. The judge said "met" in 3 of the 6 (false passes, overridden by the report
   check).

No attempt in these runs broke a budget, forbidden-item or never-keyword rule, and none is a clean bot success: every
non-quota fail is a call that was cut off before the bot could confirm an order, mostly by the simulated restaurant
(`gpt-oss-120b`) ending the call early, as in section 3. So the three text scenarios and the two audio scenarios stay
**not passed**, and the persona's early hang-up is now the clear blocker for the rest of the suite (next step 2).
The re-run does not change the 8 of 11 count.

Unit tests at the end of the fix wave: 198 pass. Re-scoring the saved Task 10 and 10b runs with the final runner gives
the same statuses as before the fix wave.


## 11. All-Gemini runs (2026-11-24, after the persona goal-wording fix)

Bot `gemini-3.5-flash-lite`, persona `gemini_native_llm` `gemini-3.5-flash-lite`, judge `gemini_llm` `gemini-3.5-flash-lite`, text mode.
Summaries and per-attempt table: [evals/confirmation/persona-hangups/](../evals/confirmation/persona-hangups/ANALYSIS.md)
(`gemini-20261124-*-summary.md`). The earlier results above are unchanged and used the Groq persona.

| Scenario | Result | Notes |
|---|---|---|
| terse_staff | **pass** (2/3) | Groq persona before: 0/3, all hang-ups |
| sold_out_no_substitute | **pass** (2 attempts, 1 pass) | restaurant ended after the bot's decline |
| minimum_reachable | **fail** (0/3) | the bot gave up (food 2100 of 2200); the persona ended only after the bot's goodbye |
| happy_path | **fail** (1 completed attempt; 2 quota_error) | order placed; judge conduct 0.83 below 1.0 |
| staff_asks_details | quota_error (0/9 counted) | 4 attempts reached a confirmed order with no persona hang-up; judge calls hit the 15 requests/min limit |

Persona same-turn hang-ups: 0 of 21 attempts (Groq baseline: 19 of 36). The limit was Gemini's 15 requests/min, not the daily cap.

## 12. minimum_reachable bot fix (2026-11-24, engine now names the shortfall)

Bot, persona `gemini-3.5-flash-lite`; judge Groq `gpt-oss-20b`; text mode. Summaries: `evals/confirmation/persona-hangups/mrfix-20261124-*-summary.md`, details in ANALYSIS.md ("minimum_reachable bot fix").

| Scenario | Result | Notes |
|---|---|---|
| minimum_reachable | **fail** (0/3 counted; 1 attempt placed the correct order, Rs 2400) | the other 2 were Gemini timeout/503; the one real attempt failed only on judge conduct 0.83 |
| happy_path, sold_out_no_substitute | quota_error | Gemini daily quota exceeded; not rerun |

## 13. All-local run on Ollama qwen3:8b (2026-11-24; bot, persona and judge all local)

Evidence: `evals/confirmation/all-ollama/` (README.md has the per-attempt table). Text mode, RX 6600 8 GB, `OLLAMA_NUM_PARALLEL=3`, 4k context, q8 KV cache, thinking off (`reasoning_effort: none`). No cloud API, so no quota errors.

| Scenario | Result | Notes |
|---|---|---|
| happy_path | **pass** (2 attempts, 1 pass) | both orders placed, but the bot invented unit prices (925/125, 1050/50); attempt 1 failed judge conduct 0.75 |
| minimum_reachable | **fail** (0/3) | one order met the Rs 2200 minimum (judge disagreed), one looped on a total mismatch, one invented prices and fees and wrote a tool call as text |
| staff_asks_details | **fail** (0/3) | the bot never called a tool or named an item; the judge said "goal met" twice when no order existed |

Persona same-turn hang-ups: 0 of 8. Bot first token per turn: median 1.4 s (p90 3.3 s); call 20 to 45 s; judge 14 to 31 s. Judge and deterministic check disagreed in 5 of 8 attempts. Verdict: usable to run the harness with no limits, but qwen3:8b is clearly weaker than the Gemini bot (invented prices, tool-call mistakes) and is not a reliable judge.

## 14. Local judge check: gemma4:12b (2026-11-24)

Re-judging 25 saved conversations (`evals/confirmation/all-ollama/judge-gemma4.md`): gemma4:12b agreed with the deterministic check in 12 of 25 (9 false passes, 4 false fails; about 100 s per conversation), qwen3:8b in 14 of 25 (3 false passes, 8 false fails; 16 s), the original judges (Groq, Gemini, qwen3) in 13 of 25. Neither local model is a reliable judge; gemma4:12b also needs flash attention off on this GPU (it crashes the Vulkan runner on prompts over about 500 tokens otherwise) and a separate server with 8192 context.

## 15. Hybrid setup: Gemini bot, local Ollama persona (2026-11-25)

Evidence: `evals/confirmation/hybrid-2026-11-25/` (README.md has the per-attempt table). The simulated restaurant is now local `qwen3:8b` (default `evals/simulator.yaml`); the judge was throttled Gemini because Groq gpt-oss-20b timed out on the judge's parallel questions (8000 tokens/min cap).

| Scenario | Result | Notes |
|---|---|---|
| minimum_reachable | **pass** (1/3) | ordered 2 biryani + 3 raita, Rs 2400 |
| staff_asks_details | **pass** (1/3) | ordered Rs 1950 |
| happy_path | fail (0/1) | order correct, no violation; judge conduct 0.875 (bot asked about the minimum order 3 times) |
| sold_out_no_substitute | **pass** (1/1) | not_ordered |
| terse_staff | fail (0/2 usable) | one attempt `quota_error` (judge HTTP 503) twice; one fail: the persona kept quoting a wrong total and the bot ended not_ordered after editing its order to match |

Why the attempt counts differ: `happy_path` ran 1 attempt because that run was started with a single attempt (its summary shows 0/1), so it is not a pass@3 failure. `terse_staff` has 3 attempts across 2 runs: the first run recorded 1 attempt (`quota_error`, a judge HTTP 503), and a second run made 2 more (1 fail, 1 `quota_error`). `minimum_reachable`, `staff_asks_details` and `sold_out_no_substitute` stop at the first pass, so they ran 1 attempt.

Persona (7 calls): 0 same-turn hang-ups, 0 lines written for the customer, stayed in role. Gemini requests per call (bot only): 13.4 on average, against 19.6 had the persona also used Gemini, so about 31% fewer, not half. n = 7 calls, one run each; small sample.

## 16. Price check: eval menu check and engine price lock (2026-11-25)

Closes the gap seen in sections 13 and 15: the bot invented prices (all-Ollama) and, with the hybrid `terse_staff` run, bent its cart (removed items, fee set to 0, biryani re-added at Rs 1350) to match a wrong total.

- **Eval layer.** `evals/expected.yaml` now holds each scenario's menu (`menu_pkr`) and fees (`fees_pkr`) as its persona states them. `check_report_full` fails a report whose unit price differs from the menu ("price for chicken biryani was 1350, menu says 900"), whose item is not on the menu, or whose delivery fee or tax differs (a call that never recorded fees is not flagged unless it confirmed an order).
- **Engine layer.** The first price accepted for an item is locked for the whole call, including after `remove_item`; the first non-zero delivery fee or tax is locked too. A change is refused unless the bot passes `price_corrected=true` (add_item) or `corrected=true` (set_fees), which is recorded in the tool event. A `confirm_order` total mismatch now tells the bot to ask the restaurant to itemise rather than edit the cart. The prompt says the same.

Rescore of every saved report.json (25 files, all in `evals/confirmation/all-ollama/judge-gemma4-evidence/`; the hybrid reports were not saved) with the old checks against the new ones. These passed the old checks and now fail:

| Saved attempt | New violations |
|---|---|
| happy_path 20261123-185933 attempt 3 (ordered) | biryani 975 vs 900; delivery fee 0 vs 150 |
| happy_path 20261124-182423 attempt 1 (ordered) | biryani 925 vs 900; raita 125 vs 150 |
| minimum_reachable 20261124-182645 attempt 1 (ordered) | biryani 800 vs 900 |

One more (terse_staff 20261123-185933 attempt 3, call_dropped) gains a price violation but already failed. Verified by unit tests only; no bot or API run yet, so how the engine guard changes real conversations is untested.

Notes on scope:
- happy_path 20261123-185933 attempt 3 was **not** one of the v1 passes. In v1 it already failed, on judge conduct 0.67 (section 2). It "passed the old checks" only in the sense of the deterministic report checks.
- This rescore covers only the 25 saved report files, so it is a **lower bound**. The v1 passes for happy_path and price_drop_optional came from a re-run (20261123-192810) whose reports were not saved, so they cannot be re-checked against the menu. The v1 passes with saved reports still pass: sold_out_substitute, sold_out_no_substitute, price_over_budget and pushes_forbidden. late_delivery and minimum_unreachable (not_ordered, no order placed) have no saved reports either. Because bots demonstrably invented prices in the same period, the v1 headline of 8 of 11 is best read as "4 re-verified against the menu, plus 4 that cannot be re-checked (2 of them placed no order)".

## 17. Groq judge throttle (2026-11-25)

The default judge (Groq `openai/gpt-oss-20b`) timed out in the hybrid run because its ~7 parallel questions, each carrying the whole transcript, exceed Groq's free 8000 tokens/minute per model. The throttle built for Gemini now covers Groq: `evals/judge.yaml` uses `groq_classifier` with one call at a time, 30 s apart, 3 retries on rate-limit errors (15 s base backoff) and a 600 s classifier timeout (queue wait counts toward it; the judge asks 1 goal question plus 1 per bot turn). The spacing is a rough estimate: a question is ~2.5-3.4k input tokens plus a JSON answer, so 2 per minute is ~6-7k TPM, and long transcripts rely on the 429 retry. Cost: a full judgement takes ~2-5 minutes per call (re-judging 3 saved all-Ollama conversations took 6 min 23 s in total at the earlier 20 s spacing, 100-140 s each in the runs observed, with no timeouts). Re-judge only, no bot run, so judge quality is untested beyond that. Pipecat reads only the `eval:` block; its explainer reuses the classifier's service, so it shares the limiter.

## 18. Short live check of the final setup (2026-11-25)

Four scenarios, 1 attempt each, committed defaults (Gemini gemini-3.5-flash-lite bot, Ollama qwen3:8b persona, throttled Groq gpt-oss-20b judge). Evidence: `evals/confirmation/short-check-2026-11-25/`.

| Scenario | Result | Note |
|---|---|---|
| happy_path | fail | persona quoted Rs 1250 for a Rs 2100 cart; lock refused confirm_order; bot ended not_ordered |
| terse_staff | fail | persona quoted 1950 (items only); lock refused twice; bot asked to itemise, kept the correct prices, ended not_ordered |
| minimum_reachable | pass | ordered, 2400 |
| sold_out_no_substitute | pass | not_ordered, item sold out |

The price lock refused only wrong totals (3 refusals, all quoted totals that did not match the correct cart); no refusal on a legitimate order, no `price_corrected`/`corrected` misuse, no price violation in any report. The two fails come from the simulated restaurant's arithmetic, not the bot. Judge took 2-5.5 min per call with no timeouts and no 429s; one Groq 400 on the explainer was retried. One attempt per scenario, so this shows the pieces work together, not a pass rate.

## 19. Persona totals and the restaurant_error status (2026-11-25)

Section 18 showed the two fails came from the simulated restaurant's arithmetic (Rs 1250 for a Rs 2100 cart; 1950 with the delivery fee forgotten), with the bot behaving correctly. Two changes so the suite measures the bot:

1. **Totals in every persona.** Each of the 11 personas now has a line `Totals (Rs, delivery included): 2 chicken biryani = 1950; 2 chicken biryani + 1 raita = 2100; ... When you quote a total, use these exact figures; never add it up yourself.` `tests/test_persona_totals.py` recomputes every figure from `menu_pkr`/`fees_pkr` in `evals/expected.yaml` (format documented at the top of the test), which also pins the persona menu values to expected.yaml.
2. **`restaurant_error` status** (`order_agent/suite.py`, `settle_status`; also applied by `--rescore`). A would-be `fail` becomes `restaurant_error` only if all of these hold: the bot's cart matches the menu exactly (unit prices, delivery fee and tax; no zero-fee exemption; no `price_corrected`/`corrected` flag); every refused `confirm_order` quote differs from the menu-correct total of that cart; no such quote is a figure on the persona's Totals line (a quote that matches a valid order may be right about a different order, so it is ambiguous); the judge's `conduct` metric passed; no order was confirmed and the only violations are consequences of there being no order. Ambiguous cases count as bot failures. It is retried like `quota_error`; a scenario with only `restaurant_error`/`quota_error` attempts is reported as such, never as pass or fail. The note reads "restaurant quoted Rs X, which matches no valid order (correct for this cart: Rs Y); bot declined". A first version of the rule was too loose: it would have labelled a bot that never set the delivery fee (cart 1950, persona correctly quoting 2100) as a restaurant error.

**Rescore of the section 18 short check** (`evals/results/20261125-145529`) under the conservative rule: both now stay `fail`. happy_path (quote 1250 vs a correct 2100 cart) meets the cart and quote conditions, but the judge's conduct metric failed (0.67), so it is not relabelled; terse_staff (quote 1950) is ambiguous because 1950 is the valid total of 2 biryani. The two passes are unchanged. So the section 18 fails remain bot-side in the record, and the rule would only have relabelled happy_path had its conduct metric passed.

**Live check** (`--only happy_path,terse_staff --attempts 2 --sleep 30`, committed defaults; evidence in `evals/confirmation/persona-totals-2026-11-25/`):

| Scenario | Attempt | Persona total | Status | Note |
|---|---|---|---|---|
| happy_path | 1 | correct (2100) | pass | order confirmed |
| terse_staff | 1 | correct (1950 for 2 biryani + delivery) | fail | bot's own error: it added the biryani at 975 and set delivery to 0 to make the cart match, then the lock refused; price violation |
| terse_staff | 2 | correct (2100) | fail | bot's own error: it recorded raita at 300 and delivery at 0 so the cart matched 2100, and confirmed; two price violations |

With correct totals the restaurant no longer causes the fail, which exposes a real bot weakness: with the terse persona the bot sometimes invents prices to reconcile a total (the engine's price lock cannot catch a wrong first price). No `restaurant_error` occurred live, because the persona did not misquote. Two attempts show that the persona quoted the right total every time (3 of 3 quotes); they are not a pass rate.
