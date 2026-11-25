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
from order_agent.controller.nudge import (  # noqa: F401 - re-exported
    MAX_NUDGES,
    NUDGE_DELAY_SECS,
    NUDGE_TEXT,
    NudgeScheduler,
    NudgeTracker,
    should_nudge,
)
from order_agent.rules import OrderSession


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
