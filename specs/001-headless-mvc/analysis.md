# Specification Analysis: 001 Headless MVC

Consistency analysis across spec.md, plan.md and tasks.md against the constitution (v1.0.0). It ran
read-only via `/speckit-analyze` on 2026-11-25. Below are the findings and the resolution decided for
each.

**Note**: task IDs in this report refer to the numbering before the F2 and F4 tasks were inserted (T014 and T030 are new in `tasks.md`; later IDs shifted).

**Summary**: 0 CRITICAL · 3 HIGH · 6 MEDIUM · 6 LOW. Requirement coverage is 18 of 18; FR-010,
FR-012 and SC-004 are covered only in part.

## HIGH

| ID | Finding | Resolution |
|---|---|---|
| F1 | Seven `evals/judge*.yaml` and `simulator-*.yaml` files name `order_agent.eval_llm.*` factories. Moving `eval_llm` would break them, which contradicts FR-010 ("unchanged"). Task T047 edits them. | Keep a compatibility module `order_agent/eval_llm.py` that re-exports the factories from the new location. The YAML files stay unchanged. The boundary check allows this one shim. |
| F2 | T029 deletes `make_on_end`, but `tests/test_call.py` (around lines 90 and 104) still uses it, so the suite would go red. These tests are missing from R9. | Add a task before T029 that ports those tests to the controller's end-of-call API, and list them in R9. |
| F3 | SC-004 compares against "pre-restructure behaviour", but no pre-change live run is planned. `happy_path` has passed and failed in different runs. | The baseline is the committed regression evidence for the current setup (`evals/confirmation/unpriced-items-2026-11-25/`, run 3: happy_path pass). SC-004 is redefined as: the post-restructure live `happy_path` (T031, needs user go-ahead) is no worse on the deterministic checks than that baseline. |

## MEDIUM

| ID | Finding | Resolution |
|---|---|---|
| F4 | The voice head has a circular construction: the hooks need the worker and context, the tools need the controller, and the controller needs the hooks. The contract has no way to attach hooks later. | Add a `CallController.attach_hooks(hooks)` method (or a constructor with lazy hooks) to the contract and tasks, with a test. |
| F5 | The SC-005 rule (heads may not import `model.rules` or `model.matching`) is in T019 but not in `contracts/boundaries.md`. | Add it to boundaries.md. |
| F6 | `hooks.py`, `bridge.py` and `tests/architecture.py` are missing from the plan's layout. | Add them to the layout in plan.md. |
| F7 | T002 imports `tests.architecture`, but `tests/` has no `__init__.py`. | Either add `tests/__init__.py` or put the helper under `tests/` and import it through `conftest.py`. Decide in the task. |
| F8 | The README still says "285 passing", but the baseline is 366. T055 only updates the count. | T055 sets the count from the final test run. |
| F9 | The FR-012 environment variables (`ORDER_BRIEF`, `ORDER_CALL_TIME`, `ORDER_REPORTS_DIR`, `ORDER_AGENT_*`) have no test. Only `bot.py --help` is covered. | Add a test that the voice head reads them through `config.load_settings` (no network). |

## LOW

- F10: The HTTP model fields are defined only in the contract, not in data-model.md. Add a short
  entry.
- F11: Whether `report_path` is relative or absolute is untested.
- F12: The contract says `ToolOutcome` lives in `session.py`, but the plan defines it in `tools.py`.
  Align them.
- F13: T028 and T041–T043 could start without a failing test. Make RED explicit.
- F14: Some [P] markers hedge on file conflicts. Run them in sequence unless they are truly
  independent.
- F15: The `python -I` subprocess import tests assume an editable install. Note the setup step.
