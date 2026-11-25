"""Compat shim: report now lives in order_agent.model.report."""
from order_agent.model.report import (
    CallReport,
    TranscriptLine,
    build_report,
    summarise,
    write_report,
)

__all__ = ["CallReport", "TranscriptLine", "build_report", "summarise", "write_report"]
