"""Request and response models of the HTTP head (contracts/http-api.md)."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator

from order_agent.model.brief import OrderBrief
from order_agent.model.report import CallReport

_BRIEF_NAME = re.compile(r"[A-Za-z0-9_-]+")


class StartSession(BaseModel):
    brief: OrderBrief | None = None
    brief_name: str | None = None
    call_time: datetime | None = None

    @field_validator("brief_name")
    @classmethod
    def _plain_name(cls, value: str | None) -> str | None:
        if value is not None and not _BRIEF_NAME.fullmatch(value):
            raise ValueError("brief_name may only contain letters, digits, '_' and '-'")
        return value

    @model_validator(mode="after")
    def _exactly_one_brief(self) -> "StartSession":
        if (self.brief is None) == (self.brief_name is None):
            raise ValueError("give exactly one of 'brief' or 'brief_name'")
        return self


class ToolInfo(BaseModel):
    name: str
    description: str
    properties: dict[str, Any]
    required: list[str]


class SessionCreated(BaseModel):
    session_id: str
    instructions: str
    opening_text: str
    tools: list[ToolInfo]


class SessionInfo(BaseModel):
    session_id: str
    state: Literal["live", "ended"]
    order_state: Literal["open", "confirmed", "ended"]
    transcript_lines: int
    report_ready: bool


class ActionRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}


class ActionResult(BaseModel):
    ok: bool
    message: str
    ended: bool


class TranscriptRequest(BaseModel):
    role: Literal["agent", "restaurant"]
    text: str

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class EndRequest(BaseModel):
    pass


class ReportResponse(BaseModel):
    report: CallReport
    summary: str
    report_path: str  # relative to the server's reports dir, never absolute
