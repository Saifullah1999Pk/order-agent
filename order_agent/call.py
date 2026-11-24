"""Per-call state: the order session, the transcript, and the one-shot report.

No Pipecat imports here.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from order_agent.brief import OrderBrief
from order_agent.config import Settings
from order_agent.report import TranscriptLine, build_report, write_report
from order_agent.rules import OrderSession


MAX_NUDGES = 2
NUDGE_TEXT = "You said nothing. Continue the call: answer the restaurant or state your order."


def should_nudge(
    content: str, *, had_function_call: bool, restaurant_spoke_since: bool, nudges_in_a_row: int
) -> bool:
    """True when an assistant turn ended with nothing said and the call would stall.

    A turn that only made a tool call is normal (the LLM is re-run with the result), and if
    the restaurant has spoken since, their turn already triggers a reply.
    """
    if content.strip() or had_function_call or restaurant_spoke_since:
        return False
    return nudges_in_a_row < MAX_NUDGES


NUDGE_DELAY_SECS = 3.0


def llm_http_options() -> dict:
    """google-genai HTTP options: retry 429/503 with exponential backoff (2 s, 4 s)."""
    return {
        "retry_options": {
            "attempts": 3,
            "initial_delay": 2.0,
            "exp_base": 2.0,
            "http_status_codes": [429, 503],
        }
    }


class NudgeTracker:
    """The flags behind the empty-reply nudge. bot.py calls these from its event handlers.

    "Restaurant spoke" means: after the current LLM run started. A restaurant turn that this
    run is answering does not count, so an empty answer to their question is still nudged.
    """

    def __init__(self) -> None:
        self._spoke_since_run = False
        self._had_function_call = False
        self._nudges = 0

    def on_user_turn_started(self) -> None:
        self._spoke_since_run = True
        self._nudges = 0

    def on_llm_run_started(self) -> None:
        self._spoke_since_run = False

    def on_function_call(self) -> None:
        self._had_function_call = True
        self._nudges = 0

    @property
    def restaurant_spoke_since_run(self) -> bool:
        return self._spoke_since_run

    def on_assistant_turn(self, content: str, interrupted: bool = False) -> bool:
        """The turn ended; return True if the LLM should be nudged."""
        if content.strip():
            self._nudges = 0
        nudge = not interrupted and should_nudge(
            content,
            had_function_call=self._had_function_call,
            restaurant_spoke_since=self._spoke_since_run,
            nudges_in_a_row=self._nudges,
        )
        self._had_function_call = False
        if nudge:
            self._nudges += 1
        return nudge


class NudgeScheduler:
    """At most one pending delayed nudge. `fire` runs after `delay` unless cancelled first.

    cancel() both cancels the task and bumps a generation counter, which the task re-checks
    after the sleep, so a stale nudge can never fire even if the cancel is missed.
    """

    def __init__(
        self,
        fire: Callable[[], Awaitable[None]],
        delay: float = NUDGE_DELAY_SECS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._fire = fire
        self._delay = delay
        self._sleep = sleep
        self._generation = 0
        self._task: asyncio.Task | None = None

    @property
    def pending(self) -> bool:
        return self._task is not None and not self._task.done()

    def schedule(self) -> None:
        self.cancel()  # replace, never stack
        self._task = asyncio.create_task(self._run(self._generation))

    def cancel(self) -> None:
        self._generation += 1
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _run(self, generation: int) -> None:
        await self._sleep(self._delay)
        if generation != self._generation:
            return
        self._task = None  # firing: later cancel() calls must not cancel this running task
        await self._fire()


class CallState:
    def __init__(self, brief: OrderBrief, settings: Settings, now: datetime):
        self.settings = settings
        self.session = OrderSession(brief, now)
        self.transcript: list[TranscriptLine] = []
        self.started_at = now
        self.report_path: Path | None = None
        self._lock = asyncio.Lock()

    def add_line(self, role: Literal["agent", "restaurant"], text: str) -> None:
        self.transcript.append(TranscriptLine(role=role, text=text, at=datetime.now()))

    async def finish(self, outcome: Literal["ordered", "not_ordered", "call_dropped"], reason: str) -> Path:
        """Write the report once; later calls (even concurrent ones) return the same path."""
        async with self._lock:
            if self.report_path is None:
                report = build_report(
                    self.session, outcome, reason, self.transcript, self.started_at, datetime.now()
                )
                self.report_path = write_report(report, self.settings.reports_dir)
            return self.report_path

    async def on_disconnect(self) -> Path:
        """The call ended; write a call_dropped report unless one already exists."""
        reason = "call ended without end_call"
        if self.session.state == "confirmed":
            reason += f" after the order was confirmed (total Rs {self.session.quoted_total_pkr:f})"
        return await self.finish("call_dropped", reason)


def make_on_end(
    call_state: CallState, push_end: Callable[[], Awaitable[None]]
) -> Callable[[str, str], Awaitable[None]]:
    """The end_call hook: write the report, then always end the pipeline.

    If writing fails, the error is logged and the pipeline still ends; the final
    on_disconnect() retries the write.
    """

    async def on_end(outcome: str, reason: str) -> None:
        try:
            path = await call_state.finish(outcome, reason)
            logger.info(f"Report written: {path}")
        except Exception:
            logger.exception("Could not write the report; the pipeline will still end")
        finally:
            await push_end()

    return on_end
