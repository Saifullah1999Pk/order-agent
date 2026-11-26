"""run_suite's checks before any bot starts: config files, and Ollama being reachable. No network."""

import pytest

from order_agent.evaltools.eval_config import load_judge_config, load_simulator_config
from order_agent.evaltools.preflight import check_ollama, ollama_bases, preflight_message

OLLAMA_PERSONA = {"service": "ollama", "model": "qwen3:8b"}
GROQ_PERSONA = {"factory": "order_agent.eval_llm.groq_llm", "model": "openai/gpt-oss-120b"}
GROQ_JUDGE = {"factory": "order_agent.eval_llm.groq_llm"}
OLLAMA_JUDGE = {"factory": "order_agent.eval_llm.ollama_classifier", "model": "qwen3:8b"}
DEFAULT = "http://localhost:11434"


def test_no_ollama_anywhere_needs_no_check():
    assert ollama_bases(GROQ_PERSONA, GROQ_JUDGE, "gemini", None) == []


def test_ollama_persona_judge_and_bot_are_detected():
    assert ollama_bases(OLLAMA_PERSONA, GROQ_JUDGE, "gemini", None) == [DEFAULT]
    assert ollama_bases(GROQ_PERSONA, OLLAMA_JUDGE, "gemini", None) == [DEFAULT]
    assert ollama_bases(GROQ_PERSONA, GROQ_JUDGE, "ollama", None) == [DEFAULT]


def test_custom_urls_and_judge_endpoint_are_each_checked_once():
    judge = {**OLLAMA_JUDGE, "endpoint": "http://localhost:11435/v1"}
    bases = ollama_bases(OLLAMA_PERSONA, judge, "ollama", "http://box:9999/v1")
    assert bases == ["http://box:9999", "http://localhost:11435"]


def test_check_ollama_ok_and_unreachable_message():
    seen = []
    assert check_ollama([DEFAULT], lambda url: seen.append(url) or True) is None
    assert seen == [DEFAULT + "/api/tags"]
    msg = check_ollama([DEFAULT], lambda url: False)
    assert msg == (
        "Ollama is not running at http://localhost:11434: start it (see README) "
        "or pass --simulator evals/simulator-gemini.yaml"
    )


def test_preflight_message_skips_http_when_no_ollama():
    def boom(url):
        raise AssertionError("no network expected")

    assert preflight_message(GROQ_PERSONA, GROQ_JUDGE, {}, boom) is None


def test_preflight_message_reads_env_and_reports_down():
    env = {"ORDER_AGENT_LLM_PROVIDER": "ollama"}
    assert "not running" in preflight_message(GROQ_PERSONA, GROQ_JUDGE, env, lambda u: False)
    assert preflight_message(GROQ_PERSONA, GROQ_JUDGE, env, lambda u: True) is None


def test_missing_simulator_file_has_clear_message(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_simulator_config(tmp_path / "nope.yaml")


def test_judge_file_without_eval_block_is_rejected(tmp_path):
    f = tmp_path / "j.yaml"
    f.write_text("explainer: {model: x}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="eval:"):
        load_judge_config(f)


def test_non_mapping_and_invalid_yaml_are_rejected(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_simulator_config(f)
    f.write_text("a: [unclosed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid YAML"):
        load_simulator_config(f)


def test_run_suite_main_exits_before_starting_anything_on_bad_file(monkeypatch, capsys):
    import run_suite

    monkeypatch.setattr("sys.argv", ["run_suite.py", "--simulator", "does-not-exist.yaml"])
    monkeypatch.setattr(run_suite, "start_bot", lambda *a, **k: pytest.fail("bot must not start"))
    with pytest.raises(SystemExit) as e:
        run_suite.main()
    assert e.value.code != 0
    assert "does-not-exist.yaml" in capsys.readouterr().err


def test_run_suite_main_exits_when_ollama_is_down(monkeypatch, capsys):
    import run_suite

    monkeypatch.setattr("sys.argv", ["run_suite.py", "--only", "happy_path"])
    monkeypatch.setattr(run_suite, "ollama_up", lambda url: False)
    monkeypatch.setattr(run_suite, "start_bot", lambda *a, **k: pytest.fail("bot must not start"))
    with pytest.raises(SystemExit) as e:
        run_suite.main()
    assert e.value.code != 0
    assert "Ollama is not running at" in capsys.readouterr().err
