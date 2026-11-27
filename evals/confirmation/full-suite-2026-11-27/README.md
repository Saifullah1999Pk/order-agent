# Full live suite, 2026-11-27 (branch `feat/order-fidelity`)

**Result: 10 of 11 scenarios pass** (`summary.md`). The baseline run `evals/confirmation/full-suite-2026-11-26` passed 9.
`minimum_reachable` passes now, and every scenario that passed before still passes. Only `price_over_budget` failed.

## Who caused each of the 12 failed attempts

| Cause | Attempts |
|---|---|
| The judge misread the conduct criterion, failing allowed behaviour: listed substitutes, tax question, own budget, asking for a discount | price_over_budget 1, 2, 3; sold_out_no_substitute 1, 2*; price_drop_optional 1; minimum_unreachable 1 |
| Real bot weakness: ignored the restaurant's fish-special push instead of declining it | pushes_forbidden 1, 2 |
| Real bot weakness: recorded delivery fee 0 after hearing only "including delivery" (the order and total were right) | pushes_forbidden 1 |
| Real bot weakness: asked for dishes outside its brief ("any other chicken dishes", "chicken fried rice") | sold_out_no_substitute 1, 2* |
| The simulated restaurant hung up mid-call after the bot correctly asked for 2 more raita | minimum_reachable 1 |

\* sold_out_no_substitute 2 is counted in both rows. Its remaining failure under the new criterion is most likely the out-of-brief question; the judge's reason text was not captured.

## The fix and its check (spec 002, addendum 2)

- The conduct criterion was rewritten in all 11 scenarios. It keeps every prohibition and names what is allowed.
- Three prompt lines were added: decline pushed items out loud; "including delivery" is not a fee; ask only about brief items and their listed substitutes.

**Offline re-judge with the new criterion** (`rejudge-new-criterion.txt`, script `rejudge_criterion.py`, Groq `openai/gpt-oss-120b`):

- **Controls, which must still fail: all 4 still fail.**
  - Total anchoring: `20261126-162641` minimum_reachable 2 and 3.
  - Cart drift (the bot claimed raita quantities it never agreed): `20261126-183358` minimum_reachable 2 and 3.
- **Misjudged attempts: 5 of 7 now pass conduct.**
  - Still failing: price_over_budget 2 (reason not captured) and sold_out_no_substitute 2 (see above).
- **Judge noise.** On re-judging, price_over_budget 1 flipped its *goal* verdict to "no" with low confidence (P(yes)=0.4), although the call correctly ended without ordering.
- **Not valid.** The happy_path 1 re-judge hit Groq's daily token limit (200k tokens for `gpt-oss-120b`) mid-judgement.

## Live re-tests after the fixes (same day)

Groq's daily judge budget was used up, so these ran with the local Ollama judge (`evals/judge-ollama.yaml`). **Its verdicts are unreliable and were ignored.** It failed the agent for "asking about availability" and "asking for less spicy". The tool calls, the code checks and the transcripts below were read by hand.

| Run | Scenario | What the agent did |
|---|---|---|
| `20261127-151755` | pushes_forbidden ×3 | Prompt fixes only. It declined the fish push out loud every time ✅. Attempt 1 still recorded delivery fee 0 after "including the delivery fee" ❌. This led to FR-014: the `set_fees` schema required both fees, so the agent had to invent one. |
| `20261127-152153` | sold_out_no_substitute ×1 | Asked only about its listed substitutes, declined the prawn biryani, said goodbye, `not_ordered` ✅ |
| `20261127-152239` | price_over_budget ×3 | All `not_ordered` (over budget) ✅. Only listed substitutes asked about, no invented prices. Attempt 1 hung up without a spoken goodbye (minor). |
| `20261127-152953` | pushes_forbidden ×1 (after FR-014) | Asked for the delivery fee and recorded 150 once stated ✅. Declined the fish push 4 of 4 times ✅. Read-back matched, confirmed at Rs 2100 ✅. One stray word ("möchtest") opened one reply (a known Gemini glitch). |

## Backup judge tried and rejected: Groq `qwen/qwen3.8-27b`

`qwen/qwen3.8-27b` has its own Groq daily budget, so we tested it as a backup for when `gpt-oss-120b` runs out. It re-judged 21 saved calls with the same criterion. **It is not reliable enough, so it was not adopted:**

- **It missed 2 of the 4 controls.** It passed the cart-drift calls (`20261126-183358` minimum_reachable 2 and 3), which must fail.
- **It failed correct calls with arithmetic it made up.** Examples: terse_staff 1 ("1950 instead of 2100") and the post-FR-014 pushes_forbidden call ("likely Rs 2250 or Rs 2025").

## Judged live re-run, same evening (Groq `gpt-oss-120b`)

| Run | Scenario | Result |
|---|---|---|
| `20261127-180727` | pushes_forbidden ×1 | **PASS**: conduct 1.00 on all 7 turns, goal P(yes)=0.99 |
| `20261127-181146` | sold_out_no_substitute ×1 | **PASS**: conduct 1.00 on all 5 turns, goal P(yes)=0.99 |
| `20261127-181447` | price_over_budget ×3 | Attempts 1 and 2: the judge hit its daily limit (`quota_error`, not judged). **Attempt 3 FAILED the code checks.** |

**Attempt 3 found a real code bug (FR-015):**

1. The restaurant said biryani is Rs 1300. `set_price(1300)` was refused as over budget, and the refusal ran before the price lock was written.
2. The bot then recorded Rs 1175, which is (2500 − 150) ÷ 2, worked out from its own budget.
3. The cart summed to exactly 2500, and `confirm_order(2500)` was accepted, although the restaurant never said 2500.

The code now locks a stated price even when it refuses it. In the total-only path, it refuses a quote lower than the prices the restaurant stated. `tests/test_price_lock_budget.py` replays this exact tool sequence.

**Live re-test after FR-015** (`20261127-190950`, price_over_budget ×3, Ollama judge, verdicts ignored; read by hand):

- Attempts 2 and 3 were correct: no order, because Rs 2750 is over budget. In attempt 3, the restaurant had said Rs 1300 before `confirm_order` refused the 2750 total.
- **Attempt 1 found another hole (FR-016).**
  - The bot cut its order to one biryani out loud, which is an LLM fault.
  - The code refused that as incomplete.
  - The bot then silently added an unpriced, never-mentioned chicken pulao and confirmed at Rs 1600. That is exactly the cost of the other items, so the pulao would have been free.
  - `confirm_order` now refuses a total-only quote that leaves an unpriced item free.

## Still to do

Re-run `price_over_budget` after FR-015, judged by `gpt-oss-120b` once its budget allows.
