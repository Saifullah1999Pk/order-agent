"""Per-call state: the order session, the transcript, and the one-shot report.

No Pipecat imports here.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from loguru import logger

from order_agent.brief import OrderBrief
from order_agent.config import Settings
from order_agent.report import write_report
from order_agent.controller.nudge import (  # noqa: F401 - re-exported
    MAX_NUDGES,
    NUDGE_DELAY_SECS,
    NUDGE_TEXT,
    NudgeScheduler,
    NudgeTracker,
    should_nudge,
)
from order_agent.controller.session import CallController
from order_agent.heads.voice.llm_factory import llm_http_options  # noqa: F401 - re-exported


class CallState(CallController):
    """Compatibility shim for the old Settings-based constructor; the logic lives in CallController."""

    def __init__(self, brief: OrderBrief, settings: Settings, now: datetime):
        super().__init__(brief, reports_dir=settings.reports_dir, now=now)
        self.settings = settings

    on_disconnect = CallController.drop

    def _write_report(self, report) -> Path:
        # Resolved through this module so tests that patch call.write_report keep working.
        return write_report(report, self.reports_dir)


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
