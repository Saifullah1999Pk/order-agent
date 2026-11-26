"""T048-T050: eval tooling lives in order_agent.evaltools."""


def test_eval_config_and_preflight_live_in_evaltools():
    from order_agent.evaltools.eval_config import apply_eval_configs
    from order_agent.evaltools.preflight import preflight_message

    assert callable(apply_eval_configs) and callable(preflight_message)
