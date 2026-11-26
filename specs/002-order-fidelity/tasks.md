# Tasks: Order Fidelity at Confirmation

**Input**: [spec.md](spec.md), [plan.md](plan.md), and the constitution v1.0.0.

**Execution rules**:

- Strict TDD: a failing test (RED) first, then the smallest change that passes (GREEN).
- One commit per task, message `feat|test|docs: T00N <summary>`, ending with the session's attribution line.
- `uv run pytest -q` is green before each commit, and the passing count never drops.
- Changing an existing test needs a stated reason in the commit message.
- No network, bots, evals or API calls.
- Before each commit, run the secret grep. Never push.

- [ ] T001 [US1] Mismatch refusal no longer reveals computed totals (FR-001), in `order_agent/model/rules.py`
  - RED: in a `tests/test_rules*.py` file, a quote that differs from the cart total is refused. The message contains none of the computed figures: the cart total, items total, fee and tax as formatted numbers. It does contain "Do not tell the restaurant a total of your own" and "itemise".
  - GREEN: the new text from plan.md.
  - Existing tests that pin the old numbers change, with the reason.

- [ ] T002 [US2] `restaurant_items` read-back check in `OrderSession.confirm_order` (FR-002, FR-003, FR-004)
  - RED:
    - cart 2 chicken biryani and 3 raita, read-back 2 and 4: refused, the reason names "raita: restaurant 4, order 3", and it says not to change the order;
    - a missing item, an extra item, and duplicates summed;
    - a matching read-back using an alias name ("biryani"): the other checks proceed;
    - an omitted read-back: identical result and identical recorded event args as today.
  - GREEN: per the plan's design, with the check first in `_confirm_order`.

- [ ] T003 [US2] Controller schema plus argument conversion and validation (FR-006, FR-007)
  - RED: `TOOL_SPECS` `confirm_order` has an optional `restaurant_items` (array of `{name, quantity}`), and `required` is unchanged. `perform("confirm_order", {..., "restaurant_items": [...]})` reaches the Model. Malformed values (a non-list, a missing key, quantity 0, quantity 1.5, a string quantity) each give exactly one refusal with no exception, through both `perform` and the voice tool handler.
  - GREEN: `toolspecs.py` and `tools.py`. Update the `test_tool_text_is_pinned` hash, with the reason stated.

- [ ] T004 [US2] Prompt asks for the read-back and forbids stating own totals (FR-005), in `order_agent/controller/prompt.py`
  - RED: a prompt test asserts the confirmation guidance mentions reading back the items with quantities, passing `restaurant_items`, and never stating a total the bot worked out itself.
  - GREEN: edit only the confirmation bullet.

- [ ] T005 Docs: one README line on the read-back check, and the test count from `uv run pytest --collect-only -q`.

- [ ] T006 LIVE, NEEDS THE USER'S GO-AHEAD: `run_suite.py --only minimum_reachable` (SC-002), then the full suite (SC-003). Compare with `evals/results/20261126-162641`.
