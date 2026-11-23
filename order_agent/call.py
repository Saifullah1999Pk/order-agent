"""Per-call state: the order session, the transcript, and the one-shot report.

No Pipecat imports here.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Literal

from order_agent.brief import OrderBrief
from order_agent.config import Settings
from order_agent.report import TranscriptLine, build_report, write_report
from order_agent.rules import OrderSession


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
