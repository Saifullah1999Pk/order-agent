"""FR-007: importing the HTTP head loads no speech or Pipecat modules."""
import subprocess
import sys

FORBIDDEN = ["pipecat", "torch", "faster_whisper", "kokoro", "google.genai", "openai"]

_SCRIPT = """
import json, sys
{extra}
import order_agent.heads.http_api.app
print(json.dumps([m for m in {forbidden!r} if m in sys.modules]))
"""


def _loaded(extra: str = "") -> list[str]:
    import json

    out = subprocess.run(
        [sys.executable, "-I", "-c", _SCRIPT.format(extra=extra, forbidden=FORBIDDEN)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_http_head_import_loads_no_speech_stack():
    assert _loaded() == []


def test_budget_check_detects_a_heavy_import():
    # the check itself works: a deliberate pipecat import is reported
    assert "pipecat" in _loaded("import pipecat")
