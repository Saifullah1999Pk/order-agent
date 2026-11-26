# order-agent Constitution

## Core Principles

### I. Headless MVC Architecture

The system is a headless core with interchangeable "heads".

- **Model**: the domain and its rules: order brief, item matching, rules engine (cart, budget,
  allow-list, forbidden foods, minimum order, delivery deadline, price/fee locks), and the call
  report. It MUST be pure Python with no imports from Pipecat, any LLM SDK, any web framework or any
  transport.
- **Controller**: runs a conversation. It starts a call from a brief, turns LLM tool calls into
  Model actions, handles nudges and end-of-call, and writes the report. It MUST expose a plain,
  framework-independent API and MUST NOT import transport or UI code.
- **Heads (adapters)**: the Pipecat voice pipeline, the eval transport, and any future phone line
  or HTTP API. They are thin. They translate between a channel and the Controller API and MUST NOT
  contain business rules or conversation state decisions.

Dependencies point inward: heads → controller → model, never the reverse.

Rationale: the same core must serve other voice agents (other domains, other channels) by swapping
only the head.

### II. The LLM Talks, Code Decides (NON-NEGOTIABLE)

- The LLM MAY only change order state through tools. Every tool call MUST be validated by the Model.
- Hard rules MUST be enforced in code, never only in prompts: budget, allowed items, forbidden
  foods, quantities, minimum order, delivery deadline, and quote and price fidelity.
- A refused action MUST tell the LLM why it was refused and what it may try instead.
- Money MUST use `Decimal`, never `float`.

Rationale: LLMs invent prices, bend totals and misread rules. Only deterministic code can be trusted
with the order.

### III. Test-First (NON-NEGOTIABLE)

- Every code change MUST start with a failing test (RED), then the smallest change that passes
  (GREEN).
- A refactor MUST keep the existing test suite green without weakening any test. Changing an
  existing test requires a stated reason.
- Unit tests MUST NOT call networks or real APIs.

Rationale: the test suite is what lets the architecture change while behaviour stays the same.

### IV. Evidence Over Judgement

- In evals, deterministic report checks (outcome, budget, prices, forbidden items, required items)
  MUST override any LLM judge. Judges are trusted only for soft qualities.
- Simulator or quota failures MUST NOT be counted as bot failures, but ambiguous cases MUST count
  against the bot.
- Every number published in docs or the README MUST trace to committed evidence. Limitations and
  regressions MUST be stated plainly.

Rationale: in our tests LLM judges agreed with the code checks only about half the time, and an
honest record matters more than a high score.

### V. Free, Safe and Honest

- Only free services are used: local models, free-tier cloud APIs, and local Ollama.
- Secrets MUST never be committed. API keys live in a gitignored `.env`. Evidence MUST be scrubbed of
  keys, account ids and local paths before commit.
- Test data is synthetic only.

## Technical Constraints

- Python 3.12 managed with `uv`. `pipecat-ai` pinned (currently 1.17.0).
- Windows 11 is a first-class platform. Anything running Pipecat sets `PYTHONIOENCODING=utf-8`.
- Speech is local (Whisper STT, Kokoro TTS). LLMs are configurable (Gemini, Groq, Ollama) through
  factories, never hard-coded in the Model or Controller.
- The eval suite is the behavioural acceptance test. It MUST keep working across refactors.

## Development Workflow

- New features and architectural changes go through Spec Kit: spec → plan → tasks → implement.
  Small fixes may skip it but still follow Principle III.
- Each change goes on its own branch and gets an independent review (spec compliance plus code
  quality) before merging to `main`.
- Public actions (pushing, making repos public, posting) require the maintainer's explicit OK.
  `main` is public.

## Governance

This constitution supersedes other practices in this repository. Every spec, plan and review MUST
check compliance with the principles above. Any deviation MUST be justified in the plan's complexity
section.

Amendments are made through `/speckit-constitution`, with a stated rationale. Versioning follows
semver:

- MAJOR: a principle is removed or redefined.
- MINOR: a principle or section is added.
- PATCH: wording only.

**Version**: 1.0.0 | **Ratified**: 2026-11-25 | **Last Amended**: 2026-11-25
