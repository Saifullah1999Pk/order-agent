from order_agent.model.matching import match_line, normalise


def test_normalise_strips_plurals_and_punctuation():
    assert normalise("Chicken Biryanis") == frozenset({"chicken", "biryani"})
    assert normalise("biryani, chicken") == frozenset({"chicken", "biryani"})
    assert normalise("Dishes") == frozenset({"dish"})


def test_match_ignores_case_order_plural(brief):
    biryani = brief.wanted[0]
    assert match_line(brief, "Chicken Biryanis") == (biryani, False)
    assert match_line(brief, "biryani, chicken") == (biryani, False)
    assert match_line(brief, "chicken karahi") == (biryani, True)


def test_match_rejects_partial_name(brief):
    assert match_line(brief, "chicken") is None
    assert match_line(brief, "fish special") is None
