# Quickstart: validating Headless MVC

Run from `order-agent/`. Windows 11, Git Bash. Anything that starts Pipecat needs
`PYTHONIOENCODING=utf-8`. See [contracts/](contracts/) for the API details.

## 1. Regression safety (US1, SC-001)

```bash
uv run pytest -q
```
Expect: all tests pass. Baseline before this feature: 366 passed. After: 366 plus the new architecture,
controller and HTTP tests, none of the old ones removed or weakened. Changed tests are listed in
research.md R9.

## 2. Boundary check (US3, SC-002)

```bash
uv run pytest tests/test_architecture.py -q
```
Expect: pass. Prove it can fail: temporarily add `import pipecat` to `order_agent/model/rules.py`, rerun,
expect a failure naming the file and the import, then revert. (The suite also proves this on synthetic
snippets, so the manual step is optional.)

## 3. Headless HTTP head (US2, SC-003)

```bash
uv run python -m order_agent.heads.http_api          # serves http://127.0.0.1:8000
```
In another shell, a scripted order (briefs/example.yaml):
```bash
curl -s -X POST localhost:8000/sessions -H 'content-type: application/json' -d '{"brief_name":"example"}'
curl -s -X POST localhost:8000/sessions/$ID/actions -H 'content-type: application/json' \
  -d '{"tool":"add_item","arguments":{"name":"chicken biryani","quantity":2,"unit_price_pkr":900}}'
# ... set_fees, confirm_order, end_call ...
curl -s localhost:8000/sessions/$ID/report
```
Expect: allowed/refused answers match the voice agent's; a forbidden item or over-budget quote is refused
with `ok:false`; the report has the same fields as a voice-call report. No speech model loads (the server
starts in about a second and imports no Pipecat; verified by a test).

## 4. Voice head unchanged (US1)

```bash
PYTHONIOENCODING=utf-8 uv run python bot.py
```
Open http://localhost:7860/client/, connect, play the restaurant. Expect: the bot opens the call if you
stay silent for 3 s, orders, confirms, ends, and a report appears in `reports/`.

## 5. Live eval parity (SC-004), after migration step 5

```bash
PYTHONIOENCODING=utf-8 uv run python run_suite.py --only happy_path
```
Expect: pass within the usual attempts using the default setup. Record the result in the PR (evidence
scrubbed of keys, account ids and local paths first). Quota or simulator failures are not bot failures
(Constitution IV).

## 6. Rescore unchanged (FR-010), after migration step 7

```bash
uv run python run_suite.py --rescore <copy of a committed results dir>
```
Rescore rewrites summary.md in place, so run it on a copy of the directory and diff against the original. Expect identical classifications. No API calls are made.

## 7. Docs (FR-011, SC-006)

Read the README architecture section: every top-level module is assigned to Model, Controller, Head or
Eval tooling, there is a diagram, and "how to add a head" is present.
