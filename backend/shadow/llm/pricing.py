"""Token Factory list prices. Checked once. Do not duplicate these numbers."""

from __future__ import annotations

CHECKED_AT = "2026-10-07"

# USD per 1M tokens. Response usage is the billing source of truth.
PRICES: dict[str, dict[str, float]] = {
    "nvidia/Nemotron-3_5-Lightning": {"input": 0.06, "output": 0.24},
    "nvidia/Nemotron-3_5-Super": {"input": 0.30, "output": 0.90},
    "nvidia/Nemotron-3_5-Ultra": {"input": 1.00, "output": 3.00},
}

DEFAULT_MODEL = "nvidia/Nemotron-3_5-Lightning"
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICES[model]
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]


def estimate_tokens(text: str) -> int:
    """Conservative character estimate with at least a 20% margin."""
    # JSON tokenizers are often denser than 4 characters per token.
    return max(1, int((len(text) / 2) * 1.2) + 1)
