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


def test_prompt_quote_fidelity(brief):
    prompt = build_system_prompt(brief)
    assert "quoted_total_pkr must be exactly the number the restaurant said" in prompt
    assert "never correct the quote yourself" in prompt
    assert "ask them to check" in prompt


def test_prompt_states_order_right_after_greeting(brief):
    prompt = build_system_prompt(brief)
    assert "right after the greeting, say clearly what you would like" in prompt.lower()
    assert "then ask about availability and prices" in prompt.lower()


def test_prompt_asks_fees_and_minimum_once_together(brief):
    prompt = build_system_prompt(brief).lower()
    assert "ask about the delivery fee, tax and minimum order once, together" in prompt
    assert "do not ask the same question twice" in prompt


def test_prompt_does_not_reask_known_no_tax_or_minimum(brief):
    prompt = build_system_prompt(brief).lower()
    assert "already said there is no tax or no minimum order, do not ask again" in prompt


def test_prompt_asks_total_and_time_once_items_agreed(brief):
    prompt = build_system_prompt(brief).lower()
    assert "once the items are agreed, ask for the total and the delivery time, then confirm" in prompt


def test_prompt_add_item_only_with_stated_price(brief):
    prompt = build_system_prompt(brief).lower()
    assert "only call add_item after the restaurant has said the price" in prompt
    assert "never guess a price" in prompt


def test_prompt_refusal_guidance_matches_rules(brief):
    prompt = build_system_prompt(brief)
    assert "smaller quantity" not in prompt
    assert "never lower a quantity" in prompt
    over = prompt.index("is over budget")
    tail = prompt[over:]
    assert tail.index("optional") < tail.index("substitute") < tail.index("not_ordered")
    minimum = prompt.index("is under the minimum order")
    assert "add optional items" in prompt[minimum : minimum + 300]


def test_prompt_follows_named_minimum_shortfall(brief):
    from order_agent.prompt import build_system_prompt

    text = build_system_prompt(brief)
    assert "add exactly the item and quantity it names" in text
