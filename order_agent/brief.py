"""Compat shim: the brief now lives in order_agent.model.brief."""
from order_agent.model.brief import OrderBrief, WantedLine, load_brief

__all__ = ["OrderBrief", "WantedLine", "load_brief"]
