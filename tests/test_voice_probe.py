"""T025: make_probe lives in the voice head (no network: the genai import is lazy, the key check comes first)."""

import pytest

from order_agent.config import Settings


def test_probe_constants_and_import_home():
    from order_agent.heads.voice.probe import PROBE_TIMEOUT_SECS, make_probe

    assert PROBE_TIMEOUT_SECS == 10.0
    assert callable(make_probe)


def test_make_probe_needs_a_google_key():
    from order_agent.heads.voice.probe import make_probe

    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        make_probe(Settings(google_api_key=None))
