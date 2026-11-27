from order_agent.controller.prompt import build_system_prompt


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
    assert "give add_item a price only when the restaurant said that item's price" in prompt
    assert "never guess or work out a price" in prompt


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
    from order_agent.controller.prompt import build_system_prompt

    text = build_system_prompt(brief)
    assert "ask the restaurant for exactly that, then record it with add_item after they agree" in text
    assert "add exactly that" not in text


def test_prompt_minimum_guidance_is_honest_about_budget(brief):
    text = build_system_prompt(brief)
    assert "never invent" in text.lower()
    assert "has already checked the budget" not in text
    assert "if it only says to ask a price, ask" in text
    assert "follow the next result" in text


def test_prompt_forbids_bending_prices_to_match_total(brief):
    prompt = build_system_prompt(brief)
    assert "never change prices, fees or items to make a total match" in prompt
    assert "ask them to itemise" in prompt


def test_prompt_total_only_rule(brief):
    prompt = build_system_prompt(brief)
    assert "do not work out item prices from it" in prompt
    assert "add the items without a price and confirm with their total" in prompt
    assert "Never invent a price or a fee" in prompt
    assert "set_price" in prompt


def test_prompt_no_derived_prices_or_guessed_fees(brief):
    prompt = build_system_prompt(brief)
    assert "never by dividing or subtracting from a total" in prompt
    assert "Only record fees the restaurant stated" in prompt
    assert "a bare 'no' to a combined question" in prompt


def test_prompt_asks_for_item_readback_and_forbids_own_totals(brief):
    prompt = build_system_prompt(brief).lower()
    assert "read your items back with their quantities, together with the total and the delivery time" in prompt
    assert "pass what the restaurant read back as restaurant_items" in prompt
    assert "never state a total you worked out yourself" in prompt
    assert "if the restaurant's read-back or total differs from your order, say so politely and ask them to check" in prompt


def test_prompt_declines_pushed_items_out_loud(brief):
    prompt = build_system_prompt(brief).lower()
    assert "if the restaurant suggests or pushes an item you did not ask for" in prompt
    assert "politely say no thank you in your next reply, every time" in prompt


def test_prompt_total_including_delivery_is_not_a_fee(brief):
    prompt = build_system_prompt(brief).lower()
    assert "a total alone, a total 'including delivery', or a bare 'no' to a combined question" in prompt
    assert "does not tell you the delivery fee" in prompt


def test_prompt_asks_only_about_brief_items_and_listed_substitutes(brief):
    prompt = build_system_prompt(brief).lower()
    assert "ask only about the items in your brief and their listed substitutes" in prompt
    assert "do not ask for other dishes" in prompt
