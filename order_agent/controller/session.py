"""CallController: one conversation, independent of the channel (voice, HTTP, tests).

A head feeds it events and tool calls, and supplies CallHooks for the things only the channel can
do (inject a developer message, hang up). No Pipecat or web-framework imports here.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from order_agent.controller.nudge import NUDGE_DELAY_SECS, NUDGE_TEXT
from order_agent.controller.prompt import build_system_prompt
from order_agent.controller.toolspecs import TOOL_SPECS, ToolSpec
from order_agent.controller.tools import ToolOutcome
from order_agent.model.brief import OrderBrief
from order_agent.model.report import CallReport, TranscriptLine
from order_agent.model.rules import OrderSession

__all__ = ["CallController", "CallHooks", "NudgeDecision", "ToolOutcome"]

OPENING_TEXT = "Nobody has spoken yet. Open the call: greet, say you'd like to place a delivery order."


@dataclass(frozen=True)
class NudgeDecision:
    nudge: bool
    text: str = NUDGE_TEXT
    delay_secs: float = NUDGE_DELAY_SECS


class CallHooks(Protocol):
    async def inject(self, text: str) -> None: ...  # add a developer message and run the LLM

    async def hangup(self) -> None: ...  # end the channel (after the report is written)


class CallController:
    def __init__(
        self,
        brief: OrderBrief,
        *,
        reports_dir: Path,
        now: datetime | None = None,
        hooks: CallHooks | None = None,
        opening_wait_secs: float = 3.0,
        nudge_delay_secs: float = 3.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        now = now if now is not None else datetime.now()
        self.brief = brief
        self.reports_dir = reports_dir
        self.session = OrderSession(brief, now)
        self.transcript: list[TranscriptLine] = []
        self.started_at = now
        self.report: CallReport | None = None
        self.report_path: Path | None = None
        self._hooks = hooks
        self._opening_wait_secs = opening_wait_secs
        self._nudge_delay_secs = nudge_delay_secs
        self._sleep = sleep

    @property
    def instructions(self) -> str:
        return build_system_prompt(self.brief)

    @property
    def opening_text(self) -> str:
        return OPENING_TEXT

    def tool_specs(self) -> tuple[ToolSpec, ...]:
        return TOOL_SPECS

    def add_line(self, role: Literal["agent", "restaurant"], text: str) -> None:
        self.transcript.append(TranscriptLine(role=role, text=text, at=datetime.now()))

    def attach_hooks(self, hooks: CallHooks) -> None:
        """Late binding: the voice head builds the controller before the objects its hooks need."""
        if self._hooks is not None:
            raise RuntimeError("hooks are already attached")
        self._hooks = hooks
