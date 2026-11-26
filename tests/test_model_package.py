"""The Model modules live in order_agent.model (the old flat paths are gone, T052)."""


def test_brief_lives_in_model():
    from order_agent.model.brief import OrderBrief, WantedLine, load_brief

    assert OrderBrief and WantedLine and callable(load_brief)


def test_matching_lives_in_model():
    from order_agent.model.matching import match_line, normalise

    assert callable(normalise) and callable(match_line)


def test_rules_live_in_model():
    from order_agent.model.rules import CartItem, OrderSession, ToolEvent, ToolResult

    assert CartItem and OrderSession and ToolEvent and ToolResult


def test_report_lives_in_model():
    from order_agent.model.report import (
        CallReport, TranscriptLine, build_report, summarise, write_report,
    )

    assert CallReport and TranscriptLine
    assert callable(build_report) and callable(summarise) and callable(write_report)
