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
    assert s.simulator["factory"] == "order_agent.eval_llm.gemini_native_llm"
    assert s.judge["factory"] == "order_agent.eval_llm.groq_llm"


def test_ollama_override_replaces_persona_and_judge():
    s = apply_eval_configs(load(), ROOT / "evals" / "simulator-ollama.yaml", ROOT / "evals" / "judge-ollama.yaml")
    for cfg in (s.simulator, s.judge):
        assert cfg["service"] == "ollama"
        assert cfg["model"] == "qwen3:8b"
        assert cfg["extra"] == {"reasoning_effort": "none"}
    persona = llm_service_from_config(s.simulator, where="simulator")
    assert isinstance(persona, OLLamaLLMService)
    assert persona._settings.model == "qwen3:8b"
    assert persona._settings.extra == {"reasoning_effort": "none"}
    assert classifier_from_config(s.judge, where="judge.eval") is not None


def test_override_only_one_side():
    s = apply_eval_configs(load(), ROOT / "evals" / "simulator-ollama.yaml", None)
    assert s.simulator["service"] == "ollama"
    assert s.judge["factory"] == "order_agent.eval_llm.groq_llm"


def test_run_suite_has_selection_flags():
    import run_suite

    args = run_suite.build_parser().parse_args(["--simulator", "a.yaml", "--judge", "b.yaml"])
    assert (args.simulator, args.judge) == ("a.yaml", "b.yaml")
    args = run_suite.build_parser().parse_args([])
    assert (args.simulator, args.judge) == (None, None)
