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
2. **Given** the same cart, **When** `restaurant_items` lists exactly the cart's items and quantities (names matched with the existing item matching), **Then** the other confirmation checks run as today.
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
