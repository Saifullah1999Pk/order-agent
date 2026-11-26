"""T048-T050: eval tooling lives in order_agent.evaltools."""


def test_eval_config_and_preflight_live_in_evaltools():
    from order_agent.evaltools.eval_config import apply_eval_configs
    from order_agent.evaltools.preflight import preflight_message

    assert callable(apply_eval_configs) and callable(preflight_message)


def test_throttle_and_eval_llm_live_in_evaltools():
    from order_agent.evaltools.eval_llm import gemini_llm
    from order_agent.evaltools.throttle import Throttle, is_rate_limit_error

    assert callable(gemini_llm) and callable(is_rate_limit_error) and Throttle


def test_every_yaml_factory_still_resolves_through_the_compat_module():
    """FR-010: evals/*.yaml keep naming order_agent.eval_llm.*; each resolves to the evaltools object."""
    import importlib
    from pathlib import Path

    import yaml

    import order_agent.evaltools.eval_llm as real

    evals = Path(__file__).resolve().parent.parent / "evals"
    files = sorted(evals.glob("judge*.yaml")) + sorted(evals.glob("simulator*.yaml"))
    assert files
    seen = 0
    for path in files:
        for factory in _factories(yaml.safe_load(path.read_text(encoding="utf-8"))):
            module_name, attr = factory.rsplit(".", 1)
            resolved = getattr(importlib.import_module(module_name), attr)
            assert callable(resolved)
            assert resolved is getattr(real, attr), factory
            seen += 1
    assert seen >= 7


def _factories(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "factory":
                yield value
            else:
                yield from _factories(value)
    elif isinstance(node, list):
        for item in node:
            yield from _factories(item)


def test_suite_lives_in_evaltools():
    from order_agent.evaltools.suite import load_expected, render_summary, rescore_run

    assert callable(load_expected) and callable(render_summary) and callable(rescore_run)
