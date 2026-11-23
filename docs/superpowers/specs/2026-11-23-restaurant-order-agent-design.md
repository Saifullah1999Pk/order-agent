# Restaurant Order Agent — Design

Date: 2026-11-23 · Author: Saifullah (with Claude Code) · Status: draft for approval

## 1. Intent

A voice agent that **phones a restaurant on the user's behalf and places a food order**.
The user gives it an order brief before the call: what they want, budget, acceptable
substitutes, deal-breakers and delivery details. The agent calls, finds out what's
available, orders, confirms the total and delivery, and reports back.

**Why:** this is the first project of the internship's voice-agent track. Mentor's direction
(Awais Qureshi, 2026-11-23): "basic agent to call to restaurant, get the menu and place voice
order — something like that", and more generally "focus on harder things, especially agents".
The point is to learn and demonstrate real agent behaviour: the agent pursues a goal and makes
decisions while an unpredictable human leads the conversation. A scripted form-filling bot
would miss that point.

## 2. Goals, non-goals, anti-goals

**Goals (v1)**
- G1. The agent holds a natural, unscripted phone conversation as the *customer*.
- G2. It orders what the brief asks for, and adapts to surprises: sold-out items, different
  prices, minimum orders, questions from staff, being put on hold.
- G3. The brief's hard rules are **enforced in code** and can't be overridden by the LLM:
  budget, forbidden items and delivery deadline.
- G4. When nothing acceptable is possible, it ends the call politely **without ordering** and
  says why.
- G5. After every call it produces a result report: outcome, items, quoted total, delivery
  time and a short reason.
- G6. Repeatable evaluation. A simulated restaurant plays the other side across a set of
  scenarios, and the results are judged automatically.
- G7. Runs at zero cost on Saif's Windows 11 laptop (CPU only, no NVIDIA GPU).

**Non-goals (v1)**
- Real phone calls (Twilio/PSTN). Planned for later; the design should not block it.
- Checking with the user *during* the call (human-in-the-loop). That's v2.
- Urdu or Roman-Urdu conversation (see §4). v1 is English only.
- Payment, accounts, a web UI for writing briefs, multiple simultaneous calls.

**Anti-goals** (a failure even if everything "works")
- The agent orders something that breaks a hard rule, or agrees to a total over budget.
- The agent invents menu items or prices that the restaurant never said.
- The agent is rude, talks over staff, or loops ("Could you repeat that?" forever).
- A scripted, step-by-step call flow that breaks the moment staff go off-script.
- Hidden costs: any paid API key required to run or test it.

## 3. Constraints

- **Stack already working locally** (verified 2026-11-23 in `Voice-Agent/bots/free_voice_bot.py`):
  Pipecat 1.17.0, Python 3.12 via `uv`, local Whisper `base` int8 STT, Gemini
  `gemini-3.5-flash-lite` LLM (free tier), local Kokoro `af_heart` TTS, Silero VAD, browser
  WebRTC transport. Measured latency was about 2–3 s from the end of the user's speech to the
  bot's audio.
- **Gemini free tier:** Gemini Live (speech-to-speech) is *not* available on this key.
  Newer Flash models intermittently return 503 "high demand", so the model must be
  configurable. The free tier has rate limits, and the agent, the simulated restaurant and the
  judge all draw on the same quota.
- **Windows:** the Pipecat dev runner crashes when stdout isn't UTF-8. Always run with
  `PYTHONIOENCODING=utf-8`.
- **Synthetic data only:** fake restaurants, names, phone numbers and addresses.
- Currency is PKR. Money is handled with `Decimal`, never floats.
- Saif must explicitly approve anything public (pushes, PRs, posts).

## 4. Approaches considered

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| **A** | **One free-form LLM agent with tools; the brief's rules are enforced in the tool code** | Copes with anything staff say; core agent pattern (goal + tools + loop). Conversation path is less predictable, so evals are needed to catch bad behaviour. | **Chosen** |
| B | Pipecat Flows: fixed stages (greet → menu → order → substitutions → confirm → close) | Predictable and easy to test stage by stage, but real staff don't follow the script; every surprise needs a stage designed in advance; the script makes the decisions, not the agent. | Rejected (could be a later comparison experiment) |
| — | Gemini Live speech-to-speech | Not available on the free key | Ruled out |
| — | Fast voice model + slower "planner" model (`LLMWithBackend`) | More moving parts and double the free-tier usage, for little gain at this size | Ruled out |

**Why A (Saif's pick, 2026-11-23):** "it shouldn't be scripted." Handling an unpredictable
other party is the whole point. The PakTaxFiler principle carries over: *the LLM talks,
plain code decides what is allowed.*

Language: v1 is English. **This is Claude's call**: local Whisper `base` is weak on Urdu,
and Kokoro has no Urdu voice. Urdu would be a separate investigation.

## 5. Design decisions

### 5.1 The order brief (input)
A small structured file (YAML or JSON) given before the call. Example:

```yaml
customer_name: "Ali Raza"            # synthetic
callback_number: "0300-0000000"      # synthetic
delivery_address: "House 12, Street 4, F-7/2, Islamabad"
wanted:
  - item: "chicken biryani"
    quantity: 2
    substitutes: ["chicken karahi", "chicken pulao"]   # acceptable if sold out
  - item: "raita"
    quantity: 1
    optional: true                    # nice to have; skip if unavailable
budget_pkr: 2500                      # hard limit, all-in (incl. delivery fee and tax)
never: ["seafood", "beef"]            # hard rule
deliver_by: "21:00"                   # hard rule; don't order if they can't make it
notes: "Less spicy if possible."      # soft preference, passed to the agent
```

Hard rules: `budget_pkr`, `never`, `deliver_by`, and only ordering `wanted` items or their
listed `substitutes`. Soft preferences: `notes`, and the `optional` flag.

**How each hard rule is enforced** (Claude's calls, from the builder check):
- **Allow-list is the main guard.** Code accepts only `wanted` items and their listed
  `substitutes`, so "our fish special" is refused because it isn't on the list, whatever it
  contains. `never` is a backstop: code matches it as keywords against item names, and the
  brief writer can list extra keywords per rule (e.g. `seafood: [fish, prawn, jhinga]`). If
  staff say something about ingredients ("our biryani is made with beef"), the agent hears it
  and is told to act on it, but code can't verify it. That limitation is accepted and written
  down.
- **When an order is complete** (Claude's call; Saif: "do whatever is best for testing").
  These rules are chosen so every scenario has exactly one correct outcome that code can
  check:
  - Every non-optional `wanted` line must be filled to its full quantity, using the original
    item, its listed substitutes, or a mix (e.g. 1 biryani + 1 karahi for a quantity of 2).
    If any required line can't be filled, the outcome is `not_ordered`.
  - Quantities never go down.
  - Optional lines are filled if possible, and never exceed their quantity, except to meet a
    minimum order (below).
  - Minimum order: the agent may add `optional` items, or increase quantities of `wanted`
    items, until the minimum is met within budget. It may never add items that aren't in the
    brief. If the minimum can't be met that way, the outcome is `not_ordered`.
  - Before `confirm_order` succeeds, code checks that the cart satisfies these rules.
- **Giving up order:** before ending without an order, the rules engine drops `optional`
  items first, then tries listed substitutes. This lives in code (the tool refusals say what
  to try), not only in the prompt.
- **Delivery time:** the brief or scenario has a `call_time` (defaulting to the wall clock
  for real use), so eval results don't depend on when the suite runs. The agent passes the
  restaurant's estimate in minutes; code adds it to `call_time`. A range counts by its latest
  end ("40 to 50 minutes" → 50).

### 5.2 The agent (Approach A)
- One Pipecat pipeline, the same shape as the working bot: transport → STT → user aggregator →
  LLM → TTS → output → assistant aggregator.
- **System prompt:** you are a customer calling a restaurant to place an order; the brief
  (rendered in plain words); speak briefly and naturally, as on a phone call; never state a
  price or item the restaurant didn't say; always use the tools to change the order.
- **Tools** (function calling), each handled in plain Python:
  - `add_item(name, quantity, unit_price_pkr)` — the item must match a `wanted` item or one of
    its substitutes, must not hit a `never` rule, and must keep the running total within
    budget. If a check fails, the tool returns a refusal with the reason, and the agent must
    adapt.
  - `remove_item(name)`
  - `set_fees(delivery_fee_pkr, tax_pkr)` — so the budget check is all-in.
  - `confirm_order(quoted_total_pkr, delivery_time)` — fails if the restaurant's quoted total
    differs from the cart total, is over budget, or the delivery time is after `deliver_by`.
  - `end_call(outcome, reason)` — outcome is `ordered` or `not_ordered`. This ends the call
    and writes the result report.
- **Opening the call** (Claude's call, from the builder check): the agent waits about 3 s
  for the restaurant's greeting. If it hears nothing, it speaks first ("Hello, is this Karachi
  Kitchen? I'd like to place a delivery order."). That's sensible on a real line, and it also
  fixes a Pipecat eval limitation: the simulated party can only *reply* and never opens the
  call (verified in `pipecat/evals/persona.py`, 1.17.0).

### 5.3 The rules engine (deterministic core)
A pure-Python module with no Pipecat imports. It holds the brief and the cart and validates
every tool call. It uses `Decimal` for money and matches item names case-insensitively,
tolerating small variations ("chicken biryani" vs "biryani, chicken"). The exact matching
approach is left to the builder. It is developed **test-first (TDD)** and is the
most-tested part of the system.

### 5.4 The result report (output)
Written when `end_call` runs, or when the call drops. JSON plus a one-paragraph plain-English
summary:

- outcome;
- items, with quantities and prices;
- fees, and the quoted total;
- delivery time;
- the reason;
- the full transcript;
- every tool call, including refused ones.

### 5.5 Build order (three phases)
1. **Human as restaurant:** Saif plays the restaurant through the browser client at
   `localhost:7860/client`. This proves the conversation and the tools work end to end.
2. **Simulated restaurant:** use Pipecat's built-in eval simulation (`pipecat.evals`), not a
   hand-built second bot. The **persona** plays the restaurant staff: menu, prices, and that
   scenario's twist all go in the persona's instructions. The **judge** decides whether the
   scenario succeeded.
3. **Scenario suite:** a set of scenario files run with `pipecat eval`:
   - **happy path:** everything is available and within budget → ordered;
   - **sold out, substitute allowed:** → ordered with the substitute;
   - **sold out, no allowed substitute:** → not ordered, polite end;
   - **price higher than expected:** two variants. Over budget only because of the optional
     item → ordered without it. Over budget even without it → not ordered;
   - **delivery after the deadline:** → not ordered;
   - **minimum order:** reachable by adding optional items or more of the wanted items →
     ordered. Not reachable within budget → not ordered;
   - **staff ask for name, number and address:** → answered from the brief;
   - **staff push a forbidden item** ("try our fish special"): → declined;
   - **noisy or terse staff:** → no repeat loops.

   **Moved out of the automated suite** (Claude's call): "hold" and "silence on answer". The
   simulated party can't go quiet and then come back. These are tested by hand in phase 1, with
   Saif as the restaurant.

   **Persona framing risk:** Pipecat's persona prompt always says it is "a person on a phone
   call with a voice assistant", and we can't change that wording. The restaurant persona
   text must override it ("you are the staff member who answered the restaurant's phone;
   the voice on the line is a customer"). Verify this in the first spike. If it doesn't hold,
   fall back to a small text-only simulator of our own: two LLMs taking turns, with the same
   scenario files and the same deterministic checks.

**Pass criteria:** the judge's verdict **and** deterministic checks on the result report
(total ≤ budget, no forbidden items, outcome matches what the scenario expects). For hard
rules, the deterministic checks override the judge.

### 5.6 Project layout
A new folder `Voice-Agent/order-agent/` with its own git repository (local only until Saif
approves a remote). Pipecat is installed from PyPI, pinned to `1.17.0`, with only the extras
needed. It does not depend on the local Pipecat clone.

## 6. Risks to verify early (first plan tasks)

1. **Gemini as the persona and judge LLM.** Pipecat evals require an OpenAI-compatible LLM
   service (`BaseOpenAILLMService`) for the persona and judge, and default to local Ollama,
   which isn't installed. Plan: a small factory returning `OpenAILLMService` pointed at Gemini's
   OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`).
   **Spike this first.** Fallback: install Ollama with a small local model (free, but slow on
   CPU).
2. **Role inversion under eval.** Resolved by the "speak first after about 3 s of silence"
   behaviour (§5.2). What still needs verifying is that the persona plays restaurant staff
   convincingly (§5.5).
3. **Free-tier quota: one key** (decided with Saif). The agent, the persona and the judge
   all share a single free Gemini key, and limits apply per Google project, per minute and per
   day. Rough estimate: about 30 requests per scenario, about 300 per full run. The real limits
   for the chosen model weren't measured; check AI Studio. Plan:
   - Run text-only by default (evals `skip_tts` mode), with a small pause between turns.
   - Log the requests used per scenario.
   - Report a rate-limit error (429) as **`quota_error`**, never as a failed scenario.
   - Fallback if one key isn't enough: a local Ollama model for the persona and judge.
   - No second keys or projects; it's unclear whether Google's terms allow that.
4. **Model overload (503).** Keep the model in config, with a fallback model.

## 7. Definition of done (v1)
- The rules engine has full unit-test coverage of the §5.1 rules, written test-first.
- Phase 1: Saif completes at least one successful order and one correct refusal by voice,
  including a hand-tested "please hold".
- Phase 3: every scenario passes **one** text-only run, with no `quota_error`, and the happy
  path plus two other scenarios pass one full-audio run. Running each scenario three times is
  a stretch goal.
- A short results write-up for the mentor: what passed, what failed, the latency and quota
  numbers measured, and the known limitations (e.g. ingredient claims can't be verified).

## 8. Left to the builder
- Brief file format details, and the validation library.
- How fuzzy item-name matching works, within the rules in §5.3.
- Exact tool signatures and error-message wording, as long as refusals tell the agent *why*.
- Exact prompt wording.
- Test structure, and how scenario files are organised.
- Whether phase 1 reuses Pipecat's dev runner or a minimal custom one.
