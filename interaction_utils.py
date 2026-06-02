"""Small Discord interaction helpers used by the music cog."""

from __future__ import annotations

import discord


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = False, thinking: bool = False) -> None:
    if interaction.response.is_done():
        return
    try:
        await interaction.response.defer(ephemeral=ephemeral, thinking=thinking)
    except discord.HTTPException:
        pass


async def send_interaction_message(interaction: discord.Interaction, *args, **kwargs):
    try:
        if interaction.response.is_done():
            return await interaction.followup.send(*args, **kwargs)
        return await interaction.response.send_message(*args, **kwargs)
    except discord.HTTPException:
        # If the initial response path raced or failed, try the followup path once.
        return await interaction.followup.send(*args, **kwargs)
