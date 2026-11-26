# Implementation Plan: Order Fidelity at Confirmation

**Branch**: `feat/order-fidelity` | **Spec**: [spec.md](spec.md) | **Constitution**: v1.0.0

## Summary

There are two changes at `confirm_order`. First, the mismatch refusal stops leaking computed totals (FR-001). Second, an optional `restaurant_items` read-back is checked against the cart in the Model (FR-002 to FR-004, FR-007). The Controller carries the schema and argument conversion (FR-006), and its prompt asks for the read-back (FR-005). Neither head changes, because both use `TOOL_SPECS` and `perform`.

## Constitution Check

- **I. Headless MVC.** The rule lives in `order_agent/model/rules.py`. Argument conversion goes in `controller/tools.py`, the schema in `controller/toolspecs.py`, and the prompt in `controller/prompt.py`. No head edits. ✅
- **II. The LLM talks, code decides.** The quantity check is enforced in code, and refusals say why and what to do instead. ✅
- **III. Test-first.** Every task starts RED. Changed existing tests state their reason. ✅
- **IV. Evidence over judgement.** The live verification (SC-002, SC-003) needs the user's go-ahead and is compared on deterministic checks. ✅
- **V. Free, safe and honest.** No new services. ✅

## Design

- **Model (`OrderSession.confirm_order`).** It gains a keyword argument `restaurant_items: list[tuple[str, int]] | None = None`.
  - Names are matched to cart lines with the existing matcher (the same one `add_item` and `remove_item` use), and duplicates are summed.
  - A name that matches no cart line counts as an extra item.
  - Differences are listed as `"<item>: restaurant <n>, order <m>"`, with the order's quantity 0 for an extra item and the restaurant's 0 for a missing one.
  - The refusal says: "Refused: the restaurant's read-back does not match your order (<differences>). Politely correct the restaurant with your order's items and quantities. Do not change the order to match; then confirm again with their read-back."
  - The check runs first inside `_confirm_order`. The recorded event args include `restaurant_items` only when it is given, so existing report events stay byte-identical.
- **Mismatch refusal (FR-001).** "Refused: the restaurant's total does not match the prices and fees you recorded. Do not tell the restaurant a total of your own. Ask them to itemise the total: each item with its price, then the delivery fee and tax. Do not edit the cart or the fees to make the totals match. Only if they clearly state a changed price or fee, correct it (add_item with price_corrected=true, or set_fees with corrected=true); if they cannot explain it, end the call as not_ordered."
- **Controller.**
  - `toolspecs.py` adds a `restaurant_items` property: an array of objects `{name: string, quantity: integer}`, not required, described as "The items and quantities the restaurant read back when confirming, if they listed them."
  - `tools.py` converts and validates it. A non-list, a missing name or quantity, or a non-integer or non-positive quantity gives a refusal "Refused: restaurant_items must be a list of {name, quantity} with whole-number quantities of at least 1."
  - `prompt.py`: the confirmation bullet asks the bot to read back its items with their quantities, the total and the delivery time; to pass the restaurant's read-back as `restaurant_items`; and never to state a total it worked out itself.
- **Tests that change, with reasons.**
  - The old mismatch-text assertions, wherever they pin the numbers.
  - `test_tool_text_is_pinned`, whose hash changes because `confirm_order` gains a property (FR-006).
  - The prompt snapshot or prompt tests, if any pin the confirmation bullet.

## Steps

1. FR-001: the refusal text (Model), RED then GREEN.
2. FR-002 to FR-004: read-back matching in the Model.
3. FR-006 and FR-007: the Controller schema plus conversion and validation, with the hash update.
4. FR-005: the prompt bullet.
5. Docs: the README rules section gets one line on the read-back check; the test count follows `--collect-only`.
6. Live verification (SC-002, SC-003): only with the user's go-ahead.
