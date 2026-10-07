"""Duffel test-mode flight search. Live tokens and orders are refused."""

from __future__ import annotations

import os
from typing import Any

import httpx


class NotConfigured(RuntimeError):
    pass


class DuffelTestAdapter:
    """Search only. Requires a duffel_test_ token. Never creates a paid order."""

    mode = "LIVE"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        token = os.environ.get("DUFFEL_ACCESS_TOKEN", "")
        if not token:
            raise NotConfigured("DUFFEL_ACCESS_TOKEN is not set")
        if not token.startswith("duffel_test_"):
            raise NotConfigured("refusing a Duffel token that is not test mode")
        self._token = token
        self._version = os.environ.get("DUFFEL_VERSION", "v2")
        self._transport = transport

    def search(self, origin: str, destination: str, departure_date: str) -> dict[str, Any]:
        payload = {
            "data": {
                "slices": [
                    {"origin": origin, "destination": destination, "departure_date": departure_date}
                ],
                "passengers": [{"type": "adult"}],
                "cabin_class": "economy",
            }
        }
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Duffel-Version": self._version,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        with httpx.Client(transport=self._transport, timeout=30) as client:
            response = client.post("https://api.duffel.com/air/offer_requests", json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        if body.get("data", {}).get("live_mode") is True:
            raise NotConfigured("Duffel returned live_mode; refusing")
        return {"mode": "LIVE", "provider": "duffel-test", "data": body.get("data", {})}
