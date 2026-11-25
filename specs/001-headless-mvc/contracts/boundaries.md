# Contract: Layer boundaries and the boundary check

## Layers and allowed imports

Each rule lists forbidden import prefixes (matched on dotted module names, so `pipecat` forbids
`pipecat.services.google.llm`). "Third-party allowed" lists the only non-stdlib packages the layer may use.

| Layer (path under `order_agent/`) | Third-party allowed | May import from `order_agent` | Forbidden |
|---|---|---|---|
| `model/` | `pydantic`, `yaml` | `order_agent.model` | `pipecat`, `google`, `openai`, `groq`, `ollama`, `anthropic`, `fastapi`, `starlette`, `uvicorn`, `aiohttp`, `httpx`, `requests`, `websockets`, `loguru`, `dotenv`; `order_agent.controller`, `order_agent.heads`, `order_agent.evaltools`, `order_agent.config` |
| `controller/` | `loguru` | `order_agent.model`, `order_agent.controller` | same third-party list as model (except `loguru`); `order_agent.heads`, `order_agent.evaltools`, `order_agent.config` |
| `heads/voice/` | `pipecat`, `google`, `loguru`, `dotenv` | `model`, `controller`, `config`, `heads.voice` | `fastapi`, `starlette`, `uvicorn` (the Pipecat runner owns the web server); `order_agent.heads.http_api`; `order_agent.evaltools` |
| `heads/http_api/` | `fastapi`, `starlette`, `uvicorn`, `pydantic`, `loguru` | `model`, `controller`, `heads.http_api` (and `config` only in `__main__`) | `pipecat`, `torch`, `faster_whisper`, `kokoro`, `google`, `openai`, `groq`, `ollama`; `order_agent.heads.voice`; `order_agent.evaltools` |
| `evaltools/` | `pipecat` (eval classes), `yaml`, `dotenv`, `loguru` | `model`, `config`, `evaltools` | `order_agent.controller`, `order_agent.heads` |

Rules the table encodes:
- No head may import `order_agent.model.rules` or `order_agent.model.matching` (SC-005: the rules engine is
  reached only through the Controller). Heads may import `model.brief` (to load a brief) and
  `model.report` (to read or summarise a report).
- One compat module is allowed outside the layers: `order_agent/eval_llm.py`, which may contain only
  re-export imports from `order_agent.evaltools.eval_llm` (a test checks this with `ast`). All other
  flat modules besides `__init__.py` and `config.py` fail the classification test once step 7 is done.
- `controller/prompt.py` (instructions for the LLM) lives in the Controller; the Model holds domain and
  rules only (`brief`, `matching`, `rules`, `report`).
- Dependencies point inward only: `heads -> controller -> model`. No inner layer imports an outer one.
- `loguru` is allowed in the Controller (logging only) and forbidden in the Model (pure domain).
- `order_agent.config` (API keys, provider selection) is never importable from Model or Controller.
- The two heads never import each other.
- Entry points (`bot.py`, `run_suite.py`) are outside the layer check; they are only wiring.

## `tests/test_architecture.py` design

```python
LAYERS = {"model": ..., "controller": ..., "heads/voice": ..., "heads/http_api": ..., "evaltools": ...}

def imported_modules(source: str, package: str) -> set[str]:
    """ast.walk: Import and ImportFrom at any depth; relative imports resolved against `package`."""

def violations(source: str, layer: str, package: str) -> list[str]:
    """Names from imported_modules() that match the layer's forbidden prefixes, or that are
    third-party and not in the layer's allow-list. Stdlib is recognised via sys.stdlib_module_names."""
```

Tests:
1. `test_real_tree_has_no_violations`: for each layer directory, each `*.py`, `violations(...) == []`
   (parametrised per file so a failure names the file and import).
2. `test_checker_catches_forbidden_imports`: bad snippets per layer (for example `import pipecat` in
   model, `from order_agent.heads.voice import x` in controller, `from fastapi import FastAPI` in
   controller, a lazy `def f(): import google.genai` in model, `from . import x` that resolves to an
   outer layer) each yield at least one violation; a clean snippet yields none. This is the SC-002
   proof that the check fails on a violation.
3. `test_every_module_is_classified`: every `*.py` under `order_agent/` is in a layer directory, is
   `order_agent/__init__.py`, is `order_agent/config.py`, or is the allowed compat module
   `order_agent/eval_llm.py` (re-exports only). A new top-level module fails the test until
   someone assigns it a layer (this keeps SC-006 true).
4. `test_runtime_import_graph` (subprocess, `python -I -c`): import `order_agent.model`, then
   `order_agent.controller`; assert none of `pipecat`, `fastapi`, `starlette`, `uvicorn`, `google`,
   `openai`, `torch` is in `sys.modules`. Separate subprocess for `order_agent.heads.http_api.app`
   asserting no `pipecat`, `torch`, `faster_whisper`, `kokoro`.

No new dependency (stdlib `ast`, `pathlib`, `subprocess`, `sys`). During migration steps 1 to 6 the
table is applied only to directories that exist; step 7 requires all of them.

## Adding a head (documented in the README at step 8)
1. Create `order_agent/heads/<name>/`.
2. Build a `CallController(brief, reports_dir=..., hooks=<your CallHooks or None>)`.
3. Translate channel events into the controller calls listed in `controller-api.md`.
4. Add the head to `LAYERS` in `tests/test_architecture.py` with its allowed third-party packages.
