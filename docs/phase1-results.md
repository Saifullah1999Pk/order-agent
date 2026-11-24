# Phase 1 results (Saif plays the restaurant)

Not run: reduced by ruling on 2026-11-23. The automated simulated-restaurant evals replaced the manual calls
(Saif asked the agents to test instead). One optional hold/silence check ("one minute please", then about 10 s of
silence) is still pending (manual). The results of the automated runs are in [results-v1.md](results-v1.md).

## Call (a): happy path
- Expected: `ordered`, total 1950
- Not run (see above)

## Call (b): biryani finished, only fish biryani
- Expected: `not_ordered` (or karahi if offered)
- Not run (see above)

## Call (c): "one minute please", ~10 s silence
- Expected: the agent waits without talking over you
- Pending (manual)
