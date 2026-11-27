# Feature Specification: Order Fidelity at Confirmation

**Feature Branch**: `feat/order-fidelity`
**Created**: 2026-11-26
**Status**: Draft
**Input**: Findings from the full live eval run `evals/results/20261126-162641` (9 of 11 scenarios pass). Reading every failed attempt showed two real bot problems at the confirmation step, both in `minimum_reachable`:

- **Total anchoring.** When the restaurant's quote differs from the cart, the `confirm_order` refusal tells the LLM "the cart total is X PKR (items …, delivery …, tax …)". The bot then tells the restaurant "my calculation comes to X". The simulated restaurant repeats X and the order is confirmed at a number the bot supplied (attempts 2 and 3). This breaks the existing rule "never state a price the restaurant did not say": a real restaurant could simply agree with the customer's figure.
- **Quantity mismatch.** The bot confirmed an order whose quoted total matched the cart while the restaurant's read-back listed different quantities: "four raita" in attempt 3 and "one raita" in attempt 1, against 3 in the cart. The total check passed, but the restaurant could deliver and charge for a different order.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The bot never anchors the restaurant on its own total (Priority: P1)

When the restaurant's quoted total does not match the order, the bot asks the restaurant to itemise and check its total. It never states a total it worked out itself.

**Why this priority**: an anchored total defeats the quote check, which is the main guard against over-charging. The code currently feeds the LLM the number it must not say.

**Independent Test**: a unit test calls `confirm_order` with a quote that differs from the cart total. The refusal text contains no cart, items, fee or tax totals, tells the bot not to state its own total, and asks it to have the restaurant itemise.

**Acceptance Scenarios**:

1. **Given** a cart whose computed total differs from the quote, **When** `confirm_order` is called, **Then** it is refused, the message contains none of the computed totals, and it instructs the bot to ask the restaurant to itemise without stating a total of its own.
2. **Given** the same refusal, **When** the restaurant itemises and a stated price or fee differs from what is recorded, **Then** the bot can still correct it through the existing `price_corrected` and `corrected` paths (unchanged).

---

### User Story 2 - The bot does not confirm when the restaurant's read-back disagrees with the order (Priority: P1)

Before confirming, the bot reads its items and quantities back. If the restaurant lists different items or quantities, the bot corrects the restaurant and does not confirm until they agree.

**Why this priority**: a matching total with the wrong items is still the wrong order, and nothing in code checks it today.

**Independent Test**: unit tests call `confirm_order` with an optional `restaurant_items` list. A mismatch (different quantity, missing item or extra item) is refused with a reason that names the difference and tells the bot to correct the restaurant without editing the cart. A matching list, or no list at all, behaves exactly as today.

**Acceptance Scenarios**:

1. **Given** a cart of 2 chicken biryani and 3 raita, **When** `confirm_order` is called with `restaurant_items` of 2 chicken biryani and 4 raita, **Then** it is refused, the reason names raita (restaurant 4, order 3), and it says to correct the restaurant and not to change the order to match.
2. **Given** the same cart, **When** `restaurant_items` lists exactly the cart's items and quantities (names matched to cart lines as described under Edge Cases), **Then** the other confirmation checks run as today.
3. **Given** `restaurant_items` is omitted, **When** `confirm_order` is called, **Then** behaviour is unchanged from today.
4. **Given** malformed `restaurant_items` (not a list, a missing name or quantity, a non-integer or non-positive quantity), **When** `confirm_order` is called, **Then** exactly one refusal result comes back, with no exception (same contract as other malformed arguments).

### Edge Cases

- The restaurant names an item with a different but matching name (for example "biryani" for "chicken biryani"). A name matches a cart line by exact normalised words (case, word order, plurals), else by the one cart line whose words contain, or are contained in, the name's words. If none or several qualify, it counts as an extra item.
- An item listed twice in `restaurant_items` is summed before comparing.
- A mismatch refusal is recorded in the report's tool events like any other refusal.
- Both checks apply to the voice head and the HTTP head identically, because both go through the Controller.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `confirm_order` refusal for a quote that differs from the cart total MUST NOT include the cart total, items total, delivery fee or tax figures. It MUST tell the LLM not to state a total of its own and to ask the restaurant to itemise (each item with its price, then the delivery fee and tax). The rest of the guidance stays the same: do not edit the cart or fees to match, correct only clearly stated changes, otherwise end as `not_ordered`.
- **FR-002**: `confirm_order` MUST accept an optional `restaurant_items` argument: the items and quantities the restaurant read back, each with a name and a positive integer quantity.
- **FR-003**: When `restaurant_items` is given and, after matching names to the cart and summing duplicates, any item or quantity differs from the cart, `confirm_order` MUST refuse. The reason names each difference (restaurant's quantity against the order's) and tells the LLM to correct the restaurant and not to change the order to match. This check runs before the quote and minimum checks.
- **FR-004**: When `restaurant_items` is omitted or matches, every existing confirmation rule and message is unchanged.
- **FR-005**: The system prompt MUST tell the bot to read back its items and quantities together with the total and delivery time before confirming, to pass what the restaurant read back as `restaurant_items`, and never to state a total it worked out itself.
- **FR-006**: The tool schema change MUST appear identically in both heads through the Controller's `TOOL_SPECS`. The tool-text snapshot test is updated, with the reason stated.
- **FR-007**: Malformed `restaurant_items` MUST produce exactly one refusal and never an exception (existing malformed-argument contract).

### Key Entities

- **Restaurant read-back**: the items and quantities the restaurant states when confirming, as reported by the LLM. It is compared against the cart; the cart stays the source of truth.

## Success Criteria *(mandatory)*

- **SC-001**: Unit tests cover FR-001 to FR-007. Every existing test passes; tests that pin the old mismatch refusal text or the tool-text hash change only with a stated reason.
- **SC-002**: A live re-run of `minimum_reachable` shows no bot reply stating a total the restaurant had not said, and no confirmation while the restaurant's read-back disagrees with the cart. This requires the user's go-ahead, because it uses API quota.
- **SC-003**: A live re-run of the full suite is no worse than `evals/results/20261126-162641` on the deterministic checks for every scenario. This also requires the user's go-ahead.

## Assumptions

- The LLM reports the restaurant's read-back honestly. Code cannot hear the call. This raises the bar; it is not proof. The prompt asks for the read-back, and the judge's conduct metric still checks the conversation.
- Judge-model reliability is a separate investigation (four of the run's eight judge-failed attempts were judge errors). It is out of scope here.
- The rare stray "data" token at the start of a Gemini reply (once in about 20 calls) is out of scope and recorded as a follow-up.

## Addendum (2026-11-26): the cart drifting from the conversation

A live re-run of `minimum_reachable` after FR-001 to FR-007 (`evals/results/20261126-183358`) found the following:

- No total anchoring occurred, and the read-back check fired as intended.
- It exposed a deeper bug. The bot's cart held more raita than it had asked the restaurant for, and the bot then "corrected" a restaurant that was right.
  - In attempt 2 the bot said "add one more raita", but recorded `add_item raita 1` twice in the same LLM turn.
  - In attempt 3 it recorded raita silently, and twice in one turn.
- The judge rightly failed the correcting turn.
- The root cause is in code. The minimum-order hint says "add N more X … The total would then be Y PKR". The bot adds immediately, before the restaurant agrees, and is handed a projected total it could repeat.

### Additional requirements

- **FR-008**: The minimum-order hint MUST tell the bot to ask the restaurant to add the suggested quantity, and to record it with `add_item` only after the restaurant agrees. It MUST NOT state a projected total. The suggested item, quantity and its cost-fit logic are unchanged.
- **FR-009**: The Controller MUST refuse an `add_item` call identical in item and quantity to one already accepted since the restaurant last spoke (the same restaurant turn). The refusal reads: "Refused: you already added <n> x <item> since the restaurant last spoke. Add more only after the restaurant agrees to more." The guard is armed by the first `llm_turn_started` and reset by `restaurant_spoke` (Pipecat reports an assistant turn for every LLM generation, including the re-run after tool results, so LLM turns cannot be the reset point). If the head never reports turns (the HTTP head), the guard is inactive.
- **SC-004**: A live re-run of `minimum_reachable` has no attempt where the cart holds an item quantity the bot never asked the restaurant for. This needs the user's go-ahead.

Tests that pin the old hint text change with a stated reason.

## Addendum 2 (2026-11-27): the full re-run and the judge's conduct wording

The full live run on this branch (`evals/results/20261127-130223`) passed 10 of 11 scenarios (the baseline `20261126-162641` passed 9). `minimum_reachable` now passes, and no scenario that passed before failed. Reading all 12 failed attempts found the following:

- **7 judge misreadings of the conduct criterion.** The old wording, "never states a price or item the restaurant did not say", was read literally. The judge failed the bot for asking about the listed substitutes in its brief, asking about tax, mentioning its own budget, or politely asking for a discount. These are what the bot is supposed to do.
- **2 real bot weaknesses in `pushes_forbidden`.** The bot ignored the restaurant's repeated fish-special push instead of declining it. In one attempt it also recorded a delivery fee of 0 after the restaurant said only "including delivery". That breaks an existing prompt rule; the order and total were right, but the report's fee was wrong.
- **2 cases of the bot asking for dishes outside its brief** ("any other chicken dishes", "chicken fried rice") in `sold_out_no_substitute`. It cannot order them, and asking invites offers it must refuse.
- **1 simulated-restaurant error** (`minimum_reachable` attempt 1): it hung up mid-call after the bot correctly asked for 2 more raita.

### Additional requirements

- **FR-010**: The prompt MUST tell the bot to decline, politely and out loud, every item the restaurant suggests or pushes that it did not ask for.
- **FR-011**: The prompt MUST state that a total "including delivery" does not tell the bot the delivery fee.
- **FR-012**: The prompt MUST tell the bot to ask only about its brief's items and their listed substitutes, never other dishes.
- **FR-013**: All 11 scenarios MUST share one conduct criterion, which keeps every prohibition (no price, fee, total, item or quantity presented as agreed unless the restaurant said so; no total the bot worked out itself; a confirmed total is the restaurant's) and names explicitly what is allowed (asking about the brief's items and listed substitutes, asking about fees, tax and the minimum, mentioning its own budget, politely asking for a lower price).
- **SC-005**: Re-judging saved attempts offline with the FR-013 criterion MUST still fail every known-bad control attempt: the two total-anchoring attempts (`20261126-162641` minimum_reachable 2 and 3) and the two cart-drift attempts (`20261126-183358` minimum_reachable 2 and 3).
  - Result: all four still fail.
  - Of the seven misjudged attempts, five now pass; one remaining failure is the out-of-brief question that FR-012 addresses.
  - Evidence: `evals/confirmation/full-suite-2026-11-27/`.
- **SC-006**: A live re-run of `pushes_forbidden`, `sold_out_no_substitute` and `price_over_budget` with the FR-010 to FR-013 changes. This needs the Groq judge's daily token budget, which the run and the re-judge exhausted on 2026-11-27, so it waits for the next window.

### Known limitations (recorded, not fixed)

- `gemini-3.5-flash-lite` sometimes disobeys an explicit prompt rule. One example is recording a fee the restaurant never stated. The code cannot hear the call, so it cannot catch this.
- The read-back check trusts the LLM's report of what the restaurant said.
- The free Groq judge allows about 200k tokens a day for `gpt-oss-120b`. That covers roughly one full suite (33 judged attempts) plus little else.
