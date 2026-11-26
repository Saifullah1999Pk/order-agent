"""CallController: one conversation, independent of the channel (voice, HTTP, tests).

A head feeds it events and tool calls, and supplies CallHooks for the things only the channel can
do (inject a developer message, hang up). No Pipecat or web-framework imports here.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from loguru import logger

from order_agent.controller.nudge import NUDGE_DELAY_SECS, NUDGE_TEXT, NudgeScheduler, NudgeTracker
from order_agent.controller.prompt import build_system_prompt
from order_agent.controller.toolspecs import TOOL_SPECS, ToolSpec
from order_agent.controller.tools import ToolDispatcher, ToolOutcome
from order_agent.model.brief import OrderBrief
from order_agent.model.matching import normalise
from order_agent.model.report import CallReport, TranscriptLine, build_report, write_report
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
        self._lock = asyncio.Lock()
        self._dispatcher = ToolDispatcher(self.session)
        self._nudges = NudgeTracker()
        self._opened = False
        self._turn_adds: set[tuple[frozenset[str], int]] | None = None  # None until the head reports a turn
        self._restaurant_has_spoken = False
        self._opening = NudgeScheduler(self._fire_opening, delay=opening_wait_secs, sleep=sleep)
        self._nudge_scheduler = NudgeScheduler(self._fire_nudge, delay=nudge_delay_secs, sleep=sleep)

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

    @property
    def finished(self) -> bool:
        return self.report_path is not None

    async def finish(self, outcome: Literal["ordered", "not_ordered", "call_dropped"], reason: str) -> Path:
        """Write the report once; later calls (even concurrent ones) return the same path."""
        async with self._lock:
            if self.report_path is None:
                report = build_report(
                    self.session, outcome, reason, self.transcript, self.started_at, datetime.now()
                )
                self.report_path = write_report(report, self.reports_dir)
                self.report = report
                self._nudge_scheduler.cancel()  # nothing fires after the call ended
                self._opening.cancel()
            return self.report_path

    async def drop(self) -> Path:
        """The call ended; write a call_dropped report unless one already exists."""
        self._nudge_scheduler.cancel()  # before the write, even if it fails: nothing fires into a dead call
        self._opening.cancel()
        reason = "call ended without end_call"
        if self.session.state == "confirmed":
            reason += f" after the order was confirmed (total Rs {self.session.quoted_total_pkr:f})"
        return await self.finish("call_dropped", reason)

    async def perform(
        self,
        tool: str,
        arguments: Mapping | None,
        reply: Callable[[ToolOutcome], Awaitable[None]] | None = None,
    ) -> ToolOutcome:
        """Run one tool call. Never raises. A successful end_call also ends the call.

        Order on a successful end_call: reply to the LLM, write the report, hang up. Each step is
        attempted even if the one before failed (the failure is logged).
        """
        repeat = self._same_turn_repeat(tool, arguments)
        if repeat is not None:
            return repeat
        outcome = await self._dispatcher.dispatch(tool, arguments)
        if tool == "add_item" and outcome.ok:
            key = self._add_key(arguments)
            if key is not None and self._turn_adds is not None:
                self._turn_adds.add(key)
        if tool == "end_call" and outcome.ended:
            await self._end_call(outcome, arguments or {}, reply)
        return outcome

    @staticmethod
    def _add_key(arguments: Mapping | None) -> tuple[frozenset[str], int] | None:
        """(normalised item name, quantity) of an add_item call, or None if it cannot be read."""
        try:
            name, quantity = arguments["name"], arguments["quantity"]
            if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or int(quantity) != quantity or not isinstance(name, str):
                return None
            return normalise(name), int(quantity)
        except Exception:  # noqa: BLE001 - the dispatcher gives the normal refusal
            return None

    def _same_turn_repeat(self, tool: str, arguments: Mapping | None) -> ToolOutcome | None:
        """FR-009: refuse an add_item identical (same normalised item name and quantity) to one accepted earlier this LLM turn."""
        if tool != "add_item" or self._turn_adds is None:
            return None
        key = self._add_key(arguments)
        if key is None or key not in self._turn_adds:
            return None
        message = f"Refused: you already added {key[1]} x {arguments['name']} in this turn. Add more only if the restaurant agreed to more, in your next turn."
        args = {k: arguments.get(k) for k in ("name", "quantity", "unit_price_pkr")}
        args["price_corrected"] = bool(arguments.get("price_corrected", False))
        self.session.record_refusal("add_item", args, message)
        return ToolOutcome(ok=False, message=message)

    async def _end_call(
        self,
        outcome: ToolOutcome,
        arguments: Mapping,
        reply: Callable[[ToolOutcome], Awaitable[None]] | None,
    ) -> None:
        if reply is not None:
            try:
                await reply(outcome)
            except Exception:
                logger.exception("Could not send the end_call result; ending the call anyway")
        try:
            path = await self.finish(arguments["outcome"], arguments["reason"])
            logger.info(f"Report written: {path}")
        except Exception:
            logger.exception("Could not write the report; the call will still end")
        self._nudge_scheduler.cancel()  # also when the report write failed
        self._opening.cancel()
        if self._hooks is not None:
            try:
                await self._hooks.hangup()
            except Exception:
                logger.exception("Hangup failed")

    # --- conversation events

    def restaurant_spoke(self, text: str | None = None) -> None:
        """The restaurant's turn started: reset the nudge flags, cancel a pending nudge."""
        self._restaurant_has_spoken = True
        self._opening.cancel()
        self._nudges.on_user_turn_started()
        self._nudge_scheduler.cancel()
        if text is not None:
            self.add_line("restaurant", text)

    def llm_turn_started(self) -> None:
        self._turn_adds = set()  # a new LLM turn: the same-turn add guard starts over (and arms on the first call)
        self._nudges.on_llm_run_started()
        self._nudge_scheduler.cancel()

    def function_calls_started(self) -> None:
        self._nudges.on_function_call()

    def llm_turn_ended(self, content: str, interrupted: bool = False) -> NudgeDecision:
        """The agent's turn ended. Returns whether the LLM is to be nudged (and schedules it)."""
        if content.strip():
            self.add_line("agent", content)
        nudge = self._nudges.on_assistant_turn(content, interrupted=interrupted)
        if nudge:
            logger.warning("Empty assistant turn, nudging the LLM")
            if self._hooks is not None and not self.finished:
                self._nudge_scheduler.schedule()
        return NudgeDecision(nudge=nudge, delay_secs=self._nudge_delay_secs)

    async def _fire_nudge(self) -> None:
        # Runs after a pause so the nudge does not land in the same per-minute quota window.
        # The hooks are read now, not at construction, so late attachment loses nothing.
        if self._hooks is not None and not self.finished:
            await self._hooks.inject(NUDGE_TEXT)

    def channel_opened(self) -> None:
        """Start the opening timer: if nobody speaks first, the agent opens the call."""
        if self._opened or self._hooks is None:
            return
        self._opened = True
        self._opening.schedule()

    async def _fire_opening(self) -> None:
        if self._hooks is None or self.finished or self._restaurant_has_spoken:
            return  # the normal turn flow answers them
        await self._hooks.inject(self.opening_text)
