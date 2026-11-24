"""The order brief: what the customer wants and the hard rules for the call."""

from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class WantedLine(BaseModel):
    item: str
    quantity: int = Field(ge=1)
    substitutes: list[str] = []
    optional: bool = False


class OrderBrief(BaseModel):
    customer_name: str
    callback_number: str
    delivery_address: str
    wanted: list[WantedLine] = Field(min_length=1)
    budget_pkr: Decimal = Field(gt=0)
    never: dict[str, list[str]]
    deliver_by: time
    call_time: datetime | None = None
    notes: str = ""

    @field_validator("budget_pkr", mode="before")
    @classmethod
    def _money_without_float(cls, value):
        # Go via str so a YAML float never picks up binary rounding.
        if isinstance(value, float):
            return Decimal(str(value))
        return value

    @field_validator("deliver_by", mode="before")
    @classmethod
    def _yaml_sexagesimal_time(cls, value):
        # YAML 1.1 reads an unquoted 21:00 as the int 1260 (21*60+0). Without
        # this, pydantic would take it as seconds and silently give 00:21.
        if isinstance(value, bool) or isinstance(value, float):
            raise ValueError('deliver_by must be a time like "21:00" (put it in quotes)')
        if isinstance(value, int):
            hours, minutes = divmod(value, 60)
            if not 0 <= hours <= 23:
                raise ValueError('deliver_by must be a time like "21:00" (put it in quotes)')
            return time(hours, minutes)
        return value

    @field_validator("never", mode="before")
    @classmethod
    def _normalise_never(cls, value):
        if isinstance(value, list):
            value = {name: [name] for name in value}
        if isinstance(value, dict):
            return {
                name: [name] + [k for k in keywords if k != name]
                for name, keywords in value.items()
            }
        return value


def load_brief(path: Path) -> OrderBrief:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return OrderBrief(**data)
