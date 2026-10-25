"""Runtime settings loaded from the environment (.env in repo root or backend/)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

# Reference list prices (USD per 1M tokens, input/output) for Nemotron on Token Factory.
# Used for the cost column in the agent trace; override with PRICE_<TIER>_IN / _OUT.
DEFAULT_PRICES = {
    "nano": (0.06, 0.24),
    "super": (0.30, 0.90),
    "ultra": (1.00, 3.00),
}

# Substrings used to pick a model ID for each tier out of GET /v1/models.
TIER_HINTS = {
    "nano": ["nemotron-3-nano-30b", "nemotron-3-nano", "nemotron-nano"],
    "super": ["nemotron-3-super", "nemotron-super"],
    "ultra": ["nemotron-3-ultra", "nemotron-ultra"],
}

# Fallback IDs, only used when /v1/models cannot be reached.
FALLBACK_MODELS = {
    "nano": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "super": "nvidia/nemotron-3-super-120b-a12b",
    "ultra": "nvidia/Nemotron-3-Ultra-550b-a55b",
}


def _price(tier: str) -> tuple[float, float]:
    default_in, default_out = DEFAULT_PRICES[tier]
    return (
        float(os.getenv(f"PRICE_{tier.upper()}_IN", default_in)),
        float(os.getenv(f"PRICE_{tier.upper()}_OUT", default_out)),
    )


@dataclass
class Settings:
    nebius_api_key: str = field(default_factory=lambda: os.getenv("NEBIUS_API_KEY", ""))
    nebius_base_url: str = field(
        default_factory=lambda: os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
    )
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    model_overrides: dict[str, str] = field(
        default_factory=lambda: {
            t: os.getenv(f"MODEL_{t.upper()}", "") for t in ("nano", "super", "ultra")
        }
    )
    prices: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {t: _price(t) for t in DEFAULT_PRICES}
    )
    demo_mode: str = field(default_factory=lambda: os.getenv("DEMO_MODE", "auto"))
    database_path: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", str(ROOT / "backend" / "bidscout.db"))
    )
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    )

    @property
    def has_llm(self) -> bool:
        return bool(self.nebius_api_key)

    @property
    def has_search(self) -> bool:
        return bool(self.tavily_api_key)


settings = Settings()
