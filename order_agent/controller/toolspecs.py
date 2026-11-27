"""LLM-visible tool definitions, free of any framework type.

A head turns these into its own schema objects (for Pipecat, FunctionSchema).
The text is copied verbatim from the legacy tools.py: it is what the LLM sees.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    properties: dict  # JSON-schema property map
    required: list[str]


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="add_item",
        description="Add an item the restaurant has offered to the order. Give unit_price_pkr only if the restaurant actually stated that item's price; if they only give a total, leave it out. Never work out or guess a price.",
        properties={
            "name": {"type": "string", "description": "Item name as the restaurant said it."},
            "quantity": {"type": "integer", "description": "How many to add."},
            "unit_price_pkr": {"type": "number", "description": "Price of one unit in PKR, only if the restaurant stated it. Omit if unknown."},
            "price_corrected": {"type": "boolean", "description": "Only true if the restaurant clearly said this item's price changed from what they said before. Never use it to make a total match."},
        },
        required=["name", "quantity"],
    ),
    ToolSpec(
        name="set_price",
        description="Record the price of an item already in the order, only when the restaurant states that item's price. Never divide, subtract or otherwise derive a price from a total.",
        properties={
            "name": {"type": "string", "description": "Name of the item in the order."},
            "unit_price_pkr": {"type": "number", "description": "Price of one unit in PKR, as the restaurant stated it."},
            "price_corrected": {"type": "boolean", "description": "Only true if the restaurant clearly said this item's price changed from what they said before. Never use it to make a total match."},
        },
        required=["name", "unit_price_pkr"],
    ),
    ToolSpec(
        name="remove_item",
        description="Remove an item from the order.",
        properties={"name": {"type": "string", "description": "Name of the item to remove."}},
        required=["name"],
    ),
    ToolSpec(
        name="set_fees",
        description="Record the delivery fee and tax the restaurant stated. Give only the ones they said: leave out the delivery fee if they have not stated it ('including delivery' is not a fee). Use 0 only when they clearly said there is none.",
        properties={
            "delivery_fee_pkr": {"type": "number", "description": "Delivery fee in PKR, only if the restaurant stated it."},
            "tax_pkr": {"type": "number", "description": "Tax in PKR, only if the restaurant stated it."},
            "corrected": {"type": "boolean", "description": "Only true if the restaurant clearly said a fee changed from what they said before. Never use it to make a total match."},
        },
        required=[],
    ),
    ToolSpec(
        name="set_minimum_order",
        description="Record the restaurant's minimum order for food, if they state one.",
        properties={"minimum_pkr": {"type": "number", "description": "Minimum order in PKR."}},
        required=["minimum_pkr"],
    ),
    ToolSpec(
        name="confirm_order",
        description="Confirm the order with the total and delivery time the restaurant quoted.",
        properties={
            "quoted_total_pkr": {"type": "number", "description": "The all-in total the restaurant quoted, in PKR."},
            "delivery_minutes": {"type": "integer", "description": "Delivery time in minutes (longest end of a range)."},
            "restaurant_items": {
                "type": "array",
                "description": "The items and quantities the restaurant read back when confirming, if they listed them.",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "quantity": {"type": "integer"}},
                    "required": ["name", "quantity"],
                },
            },
        },
        required=["quoted_total_pkr", "delivery_minutes"],
    ),
    ToolSpec(
        name="end_call",
        description="End the call once the order is confirmed, or when it cannot be made.",
        properties={
            "outcome": {"type": "string", "enum": ["ordered", "not_ordered"], "description": "ordered only after confirm_order succeeded."},
            "reason": {"type": "string", "description": "Short reason for the outcome."},
        },
        required=["outcome", "reason"],
    ),
)
