from datetime import datetime, time
from decimal import Decimal

import pytest

from order_agent.brief import OrderBrief, WantedLine


def _make_brief(**overrides) -> OrderBrief:
    data = dict(
        customer_name="Ali Raza",
        callback_number="0300-0000000",
        delivery_address="House 12, Street 4, F-7/2, Islamabad",
        wanted=[
            WantedLine(
                item="chicken biryani",
                quantity=2,
                substitutes=["chicken karahi", "chicken pulao"],
            ),
            WantedLine(item="raita", quantity=1, optional=True),
        ],
        budget_pkr=Decimal("2500"),
        never={"seafood": ["seafood", "fish", "prawn", "jhinga"], "beef": ["beef"]},
        deliver_by=time(21, 0),
        call_time=datetime(2026, 11, 23, 19, 30),
        notes="Less spicy if possible.",
    )
    data.update(overrides)
    return OrderBrief(**data)


@pytest.fixture
def brief() -> OrderBrief:
    return _make_brief()


@pytest.fixture
def make_brief():
    return _make_brief
