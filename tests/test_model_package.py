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


def test_rules_live_in_model():
    from order_agent.model.rules import CartItem, OrderSession, ToolEvent, ToolResult
    import order_agent.rules as old

    assert old.OrderSession is OrderSession
    assert old.ToolResult is ToolResult
    assert old.ToolEvent is ToolEvent
    assert old.CartItem is CartItem
