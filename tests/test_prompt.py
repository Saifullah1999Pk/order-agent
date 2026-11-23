from order_agent.prompt import build_system_prompt


def test_prompt_contains_rules(brief):
    prompt = build_system_prompt(brief)
    for text in (
        "2500",
        "chicken biryani",
        "chicken karahi",
        "seafood",
        "21:00",
        "House 12, Street 4, F-7/2, Islamabad",
        brief.customer_name,
    ):
        assert text in prompt


def test_prompt_forbids_inventing(brief):
    prompt = build_system_prompt(brief)
    assert "Never state a price or item the restaurant did not say" in prompt
    assert "use the tools" in prompt


def test_prompt_mentions_spoken_style(brief):
    prompt = build_system_prompt(brief)
    assert "short" in prompt
    assert "no lists or markdown" in prompt
