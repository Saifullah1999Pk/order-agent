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

## Still to do

The live re-run of `pushes_forbidden`, `sold_out_no_substitute` and `price_over_budget` (SC-006) waits for the Groq judge's daily token budget to reset.
