"""The Model modules live in order_agent.model; old flat paths are compat shims."""


def test_brief_lives_in_model():
    from order_agent.model.brief import OrderBrief, WantedLine, load_brief
    import order_agent.brief as old

    assert old.OrderBrief is OrderBrief
    assert old.WantedLine is WantedLine
    assert old.load_brief is load_brief


def test_matching_lives_in_model():
    from order_agent.model.matching import match_line, normalise
    import order_agent.matching as old

    assert old.normalise is normalise
    assert old.match_line is match_line
