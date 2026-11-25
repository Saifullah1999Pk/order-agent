"""Compat shim: matching now lives in order_agent.model.matching."""
from order_agent.model.matching import match_line, normalise

__all__ = ["match_line", "normalise"]
