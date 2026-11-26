"""In-memory session registry: one CallController (and one lock) per session id."""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from order_agent.controller import CallController
from order_agent.model.brief import OrderBrief


class NotFound(Exception):
    pass


class TooManySessions(Exception):
    pass


class SessionStore:
    def __init__(self, max_sessions: int = 100) -> None:
        self.max_sessions = max_sessions
        self._controllers: dict[str, CallController] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def create(
        self, brief: OrderBrief, *, reports_dir: Path, now: datetime | None = None
    ) -> tuple[str, CallController]:
        if len(self._controllers) >= self.max_sessions:
            raise TooManySessions(f"At most {self.max_sessions} sessions at once; delete one first.")
        session_id = uuid.uuid4().hex
        controller = CallController(brief, reports_dir=reports_dir, now=now, hooks=None)
        self._controllers[session_id] = controller
        self._locks[session_id] = asyncio.Lock()
        return session_id, controller

    def get(self, session_id: str) -> CallController:
        try:
            return self._controllers[session_id]
        except KeyError:
            raise NotFound(f"No session with id {session_id}") from None

    def lock(self, session_id: str) -> asyncio.Lock:
        self.get(session_id)
        return self._locks[session_id]

    def delete(self, session_id: str) -> None:
        self.get(session_id)
        del self._controllers[session_id]
        del self._locks[session_id]

    def count(self) -> int:
        return len(self._controllers)
