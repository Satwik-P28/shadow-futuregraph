"""One sandbox service per browser session. The public process must not share plans."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import Any


class SessionStore:
    def __init__(self, factory: Callable[[], Any], limit: int = 48) -> None:
        self._factory = factory
        self._limit = limit
        self._items: dict[str, Any] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str | None) -> tuple[str, Any, bool]:
        with self._lock:
            if session_id and session_id in self._items:
                self._order.remove(session_id)
                self._order.append(session_id)
                return session_id, self._items[session_id], False
            new_id = uuid.uuid4().hex
            service = self._factory()
            self._items[new_id] = service
            self._order.append(new_id)
            while len(self._order) > self._limit:
                dropped = self._order.pop(0)
                self._items.pop(dropped, None)
            return new_id, service, True
