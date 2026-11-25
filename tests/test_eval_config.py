"""run_suite can swap the persona and judge configs; the committed defaults stay unchanged."""

from pathlib import Path

from pipecat.evals.scenario import EvalScenarioFile
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.evals.services import llm_service_from_config, classifier_from_config

from order_agent.eval_config import apply_eval_configs

ROOT = Path(__file__).parent.parent
SCENARIO = ROOT / "evals" / "scenarios" / "happy_path.yaml"


def load():
    return list(EvalScenarioFile.load(SCENARIO))[0]


def test_defaults_untouched_without_overrides():
    s = apply_eval_configs(load(), None, None)
    # hybrid default: local Ollama persona, Groq judge (the bot is configured separately, Gemini by default)
    assert s.simulator["service"] == "ollama"
    assert s.simulator["model"] == "qwen3:8b"
    assert s.judge["factory"] == "order_agent.eval_llm.groq_classifier"


def test_ollama_override_replaces_persona_and_judge():
    s = apply_eval_configs(load(), ROOT / "evals" / "simulator.yaml", ROOT / "evals" / "judge-ollama.yaml")
    assert s.simulator["service"] == "ollama"
    assert s.simulator["model"] == "qwen3:8b"
    assert s.simulator["extra"] == {"reasoning_effort": "none"}
    assert s.judge["model"] == "qwen3:8b"
    persona = llm_service_from_config(s.simulator, where="simulator")
    assert isinstance(persona, OLLamaLLMService)
    assert persona._settings.model == "qwen3:8b"
    assert persona._settings.extra == {"reasoning_effort": "none"}
    assert classifier_from_config(s.judge, where="judge.eval") is not None


def test_override_only_one_side():
    s = apply_eval_configs(load(), ROOT / "evals" / "simulator.yaml", None)
    assert s.simulator["service"] == "ollama"
    assert s.judge["factory"] == "order_agent.eval_llm.groq_classifier"


def test_run_suite_has_selection_flags():
    import run_suite

    args = run_suite.build_parser().parse_args(["--simulator", "a.yaml", "--judge", "b.yaml"])
    assert (args.simulator, args.judge) == ("a.yaml", "b.yaml")
    args = run_suite.build_parser().parse_args([])
    assert (args.simulator, args.judge) == (None, None)


def test_ollama_classifier_has_long_timeout_and_thinking_off():
    from pipecat.classifiers.llm.classifier import LLMClassifier

    from order_agent.eval_llm import ollama_classifier

    c = ollama_classifier({"model": "qwen3:8b", "timeout_s": 300})
    assert isinstance(c, LLMClassifier)
    assert c._timeout == 300
    assert isinstance(c._llm, OLLamaLLMService)
    assert c._llm._settings.model == "qwen3:8b"
    assert c._llm._settings.extra == {"reasoning_effort": "none"}
    assert ollama_classifier({})._timeout == 300  # default must outlast the queue of parallel questions


def test_judge_ollama_yaml_uses_that_factory():
    s = apply_eval_configs(load(), None, ROOT / "evals" / "judge-ollama.yaml")
    assert s.judge["factory"] == "order_agent.eval_llm.ollama_classifier"


def test_gemini_and_groq_persona_configs_build_services():
    from pipecat.services.google.llm import GoogleLLMService
    from pipecat.services.groq.llm import GroqLLMService

    g = apply_eval_configs(load(), ROOT / "evals" / "simulator-gemini.yaml", None).simulator
    assert g["factory"] == "order_agent.eval_llm.gemini_native_llm"
    assert g["model"] == "gemini-3.5-flash-lite"
    r = apply_eval_configs(load(), ROOT / "evals" / "simulator-groq.yaml", None).simulator
    assert r["factory"] == "order_agent.eval_llm.groq_llm"
    assert r["model"] == "openai/gpt-oss-120b"
    assert not (ROOT / "evals" / "simulator-ollama.yaml").exists()


def test_default_ollama_persona_keeps_reasoning_effort_none():
    assert load().simulator["extra"] == {"reasoning_effort": "none"}


def test_committed_default_judge_is_throttled_groq(monkeypatch):
    import yaml

    from order_agent.eval_llm import ThrottledOpenAILLMService

    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    j = apply_eval_configs(load(), None, None).judge  # Pipecat passes the eval block through
    assert j["factory"] == "order_agent.eval_llm.groq_classifier"
    assert j["model"] == "openai/gpt-oss-20b"
    assert (j["max_concurrency"], j["min_interval_s"], j["max_retries"], j["retry_base_s"]) == (1, 20, 3, 15)
    assert j["timeout_s"] >= 300
    clf = classifier_from_config(j, where="judge.eval")
    assert clf._timeout >= 300
    assert isinstance(clf._llm, ThrottledOpenAILLMService)
    # the explainer block uses the same limiter, so the two never run in parallel
    ex = yaml.safe_load((ROOT / "evals" / "judge.yaml").read_text(encoding="utf-8"))["explainer"]
    assert ex["factory"] == "order_agent.eval_llm.groq_llm"
    exp = llm_service_from_config(ex, where="judge.explainer")
    assert clf._llm._throttle is exp._throttle
