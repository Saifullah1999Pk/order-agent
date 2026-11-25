# Feature Specification: Headless MVC Architecture

**Feature Branch**: `feat/headless-mvc`
**Created**: 2026-11-25
**Status**: Draft
**Input**: User description: "Restructure order-agent into Headless MVC (mentor review: 'your repo has no design pattern … Headless MVC is a very suitable architectural approach for our Voice Agent platform or any other'). The domain model is already mostly pure; add a clear controller layer for call logic, make the Pipecat voice pipeline one thin 'head', and add a second head that proves the core is reusable, so the same core can later serve other voice agents (e.g. other domains and channels)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Same agent, cleaner structure (Priority: P1)

A developer restructures the code into Model, Controller and Heads. Anyone who uses the agent, whether
by calling it in the browser or running the eval suite, sees exactly the same behaviour as before.

**Why this priority**: a restructure is only worth it if nothing breaks. The existing test suite and
eval suite are the safety net, and protecting them comes first.

**Independent Test**: run the full unit-test suite and a live eval scenario before and after. Same
results, with no test weakened.

**Acceptance Scenarios**:

1. **Given** the restructured code, **When** the full unit-test suite runs, **Then** every test
   passes, and any test changed only to follow moved code is listed with its reason.
2. **Given** the restructured code and the default eval setup, **When** `happy_path` runs live,
   **Then** the bot can place a correct order as before (pass within the usual attempts).
3. **Given** a person talking to the bot in the browser, **When** they play the restaurant, **Then**
   the bot opens the call, orders, confirms and writes a report exactly as before.

---

### User Story 2 - Use the order core without the voice stack (Priority: P2)

A developer drives a complete restaurant order through a second, non-voice interface (a small local
HTTP API). They start a call from a brief, send the actions an LLM would take, and get the report,
all without loading speech models or Pipecat.

**Why this priority**: this is the proof that the core is headless and reusable. It is what lets the
same core power other channels and other voice agents later.

**Independent Test**: with only the core and the HTTP head running (no Pipecat pipeline, no speech
models), complete a scripted order equivalent to `happy_path` and receive a report identical in
structure to a voice call's report.

**Acceptance Scenarios**:

1. **Given** a brief, **When** a client starts a call session through the HTTP head, **Then** it
   receives a session id and the agent's instructions or opening line.
2. **Given** an open session, **When** the client submits tool actions (add item, set fees, confirm,
   end), **Then** it receives the same allowed or refused results, with the same reasons, that the
   voice agent would get.
3. **Given** a finished session, **When** the client requests the report, **Then** it receives the
   same report content the voice head would have written.
4. **Given** an action that breaks a hard rule (for example a forbidden item or an over-budget
   quote), **When** it is submitted through the HTTP head, **Then** it is refused exactly as in a
   voice call.

---

### User Story 3 - Layer boundaries that can't silently erode (Priority: P3)

A maintainer can trust that business rules stay in the Model, conversation logic stays in the
Controller, and channel code stays in the Heads, because an automated check fails when someone breaks
the boundary.

**Why this priority**: an architecture that isn't enforced decays. An automated check makes the
design pattern a property of the repo, not a promise.

**Independent Test**: add a forbidden import (for example, the Model importing Pipecat) on a scratch
branch and confirm the check fails. Remove it and confirm the check passes.

**Acceptance Scenarios**:

1. **Given** the Model, **When** the boundary check runs, **Then** it fails if any Model module
   imports Pipecat, an LLM SDK, a web framework, a transport or a Controller/Head module.
2. **Given** the Controller, **When** the boundary check runs, **Then** it fails if any Controller
   module imports a transport, web framework or Head module.
3. **Given** the repository docs, **When** a newcomer reads the architecture section, **Then** they
   can tell which layer every top-level module belongs to.

### Edge Cases

- A call drops mid-conversation in either head. The Controller still writes a report with outcome
  `call_dropped` and keeps "drop after a confirmed order" semantics, as today.
- Two sessions run concurrently in the HTTP head. Their carts, locks and reports MUST NOT leak into
  each other.
- An unknown session id, or an action on a finished session, is rejected with a clear error.
- Malformed tool arguments through either head get the same refusal behaviour as today: exactly one
  result per action, never an exception that stalls the conversation.
- Nudge behaviour (empty LLM turn → bounded nudges, cancelled on speech, a new run or end of call)
  still works in the voice head after the move.
- The eval transport and `--rescore` keep working with no change to scenario files.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The codebase MUST be organised into three layers, Model, Controller and Heads, each in
  its own package, with dependencies pointing only inward (Heads → Controller → Model).
- **FR-002**: The Model MUST contain all business rules and the order domain (brief, matching, rules
  engine with price/fee locks and minimum-order logic, report). It MUST NOT import Pipecat, LLM SDKs,
  web frameworks, transports, or Controller/Head code.
- **FR-003**: The Controller MUST provide a channel-independent API to:
  - start a call from a brief, returning the instructions and opening behaviour;
  - perform each tool action (add item, remove item, set price, set fees, set minimum order, confirm
    order, end call) and return the allowed/refused result with its reason;
  - record transcript lines;
  - handle "the restaurant spoke", "the LLM turn ended" and nudge decisions;
  - finish or drop a call;
  - produce the report.
- **FR-004**: The Controller MUST NOT import Pipecat, transports or web frameworks. Turning Controller
  operations into Pipecat function-call schemas is the voice head's job.
- **FR-005**: The voice head (Pipecat pipeline, browser and eval transports) MUST contain only
  channel translation (audio/STT/TTS wiring, mapping Pipecat events and tool calls to Controller
  calls). It MUST contain no business rules and no decisions about conversation state.
- **FR-006**: A second head, a local HTTP API, MUST let a client start a session from a brief,
  submit tool actions, add transcript lines, end the session and fetch the report, using the same
  Controller API.
- **FR-007**: The HTTP head MUST keep sessions isolated, reject unknown or closed sessions with clear
  errors, and run without loading speech models or the Pipecat pipeline.
- **FR-008**: Behaviour MUST be preserved. Every rule outcome, refusal message, report field and
  eval classification is unchanged by the restructure, verified by the existing test suite.
- **FR-009**: An automated boundary check (part of the unit tests) MUST fail on any import that
  violates FR-002 or FR-004.
- **FR-010**: The eval suite (`run_suite.py`, scenario files, `--rescore`, judge and simulator
  configs) MUST keep working unchanged from the user's point of view.
- **FR-011**: README and docs MUST describe the architecture: the layers, a diagram, which module
  lives where, and how to add a new head. Any changed commands MUST be updated.
- **FR-012**: Existing entry points MUST keep working (`uv run python bot.py`, `run_suite.py`
  flags, environment variables). A thin compatibility shim is allowed if files move.

### Key Entities

- **Order brief**: what the customer wants, budget, substitutes, forbidden foods, deadline, delivery
  details. Input to a call.
- **Call session**: one conversation's state. It holds the order session (cart, locks, fees, minimum),
  transcript, nudge state, timing, and whether a report has been written. It is owned by the
  Controller and identified by a session id in the HTTP head.
- **Tool action / result**: an action the LLM (or a client) asks for, with its arguments, and the
  Model's allowed/refused result with a reason.
- **Call report**: the outcome, items, fees, totals, transcript and every tool event. Produced by the
  Controller from the Model.
- **Head**: an adapter that connects one channel (voice in the browser, eval transport, HTTP) to the
  Controller API.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the existing unit tests pass after the restructure. Any test changed only for
  moved imports is listed with its reason. No test is weakened.
- **SC-002**: The boundary check reports 0 violations, and it demonstrably fails when a forbidden
  import is introduced.
- **SC-003**: A complete scripted `happy_path`-equivalent order succeeds through the HTTP head with no
  speech models or Pipecat pipeline loaded, and yields a report with the same fields as a voice-call
  report.
- **SC-004**: A live `happy_path` eval with the default setup passes within the usual attempts after
  the restructure, matching pre-restructure behaviour.
- **SC-005**: The voice head contains zero business-rule logic. Every rule decision is made by
  Model/Controller code, confirmed in the review checklist.
- **SC-006**: A newcomer can identify the layer of every top-level module from the README
  architecture section alone.

## Assumptions

- The second head is a small local HTTP API (FastAPI is already a project dependency through
  Pipecat's runner). It is for local development and demonstration only: no authentication, no
  deployment, no persistence beyond process memory.
- The HTTP head exercises the Controller with explicit tool actions from the client. It does not run
  an LLM itself. Connecting it to an LLM, a phone line or a web UI is future work.
- No new behaviour is added to the order domain. This is a structural change. Domain fixes found
  along the way are recorded as follow-ups, not mixed in.
- The eval harness (Pipecat evals, judge and simulator configs) stays as is. Only its imports and
  wiring may move.
- Free services only. No new paid dependencies.
- Reusing the core for a different domain (for example another business) is out of scope here. This
  restructure makes it possible but does not build it.
