"""Google Calendar writes stay off unless real actions and a refresh token exist."""

from __future__ import annotations

import os
from typing import Any

import httpx


class NotConfigured(RuntimeError):
    pass


class GoogleCalendarAdapter:
    mode = "LIVE"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        self._client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self._refresh = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
        if not (self._client_id and self._client_secret and self._refresh):
            raise NotConfigured("Google Calendar credentials are incomplete")
        self._transport = transport
        self._enabled = os.environ.get("SHADOW_REAL_ACTIONS_ENABLED", "false").lower() == "true"

    def _token(self) -> str:
        with httpx.Client(transport=self._transport, timeout=30) as client:
            response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            return str(response.json()["access_token"])

    def update_event(self, calendar_id: str, event_id: str, body: dict[str, Any]) -> dict[str, Any]:
        if not self._enabled:
            raise NotConfigured("SHADOW_REAL_ACTIONS_ENABLED is false; calendar write refused")
        token = self._token()
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
        with httpx.Client(transport=self._transport, timeout=30) as client:
            response = client.patch(url, json=body, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            return {"mode": "LIVE", "event": response.json()}
