"""Tier helper fallback for the music cog."""

from __future__ import annotations

import os


async def get_tier_from_message(_interaction) -> str:
    return os.getenv("MUSIC_DEFAULT_TIER", "basic").lower()
