"""Tavily is used for fresh external evidence, not general browsing."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx


class NotConfigured(RuntimeError):
    pass


class TavilySearch:
    mode = "LIVE"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        key = os.environ.get("TAVILY_API_KEY", "")
        if not key:
            raise NotConfigured("TAVILY_API_KEY is not set")
        self._key = key
        self._transport = transport

    def search(self, query: str) -> list[dict[str, Any]]:
        payload = {
            "api_key": self._key,
            "query": query,
            "search_depth": "basic",
            "max_results": 3,
            "include_answer": False,
        }
        with httpx.Client(transport=self._transport, timeout=30) as client:
            response = client.post("https://api.tavily.com/search", json=payload)
            response.raise_for_status()
            body = response.json()
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        facts = []
        for item in body.get("results") or []:
            facts.append(
                {
                    "query": query,
                    "source": item.get("url"),
                    "observed_at": observed,
                    "claim": item.get("content") or item.get("title"),
                    "provenance": "tavily",
                    "mode": "LIVE",
                }
            )
        return facts
