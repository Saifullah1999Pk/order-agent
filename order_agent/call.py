"""Per-call state: the order session, the transcript, and the one-shot report.

Compat module: old import paths re-export the controller and voice-head names.
"""

from datetime import datetime

from order_agent.config import Settings
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
from order_agent.model.brief import OrderBrief


class CallState(CallController):
    """Compatibility shim for the old Settings-based constructor; the logic lives in CallController."""

    def __init__(self, brief: OrderBrief, settings: Settings, now: datetime):
        super().__init__(brief, reports_dir=settings.reports_dir, now=now)
        self.settings = settings

    on_disconnect = CallController.drop
