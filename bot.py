import asyncio
import logging
import os
import traceback

import discord
from discord.ext import commands

# 🔥 Logging
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("DISCORD_TOKEN")
print("TOKEN LOADED:", bool(TOKEN))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print("🔥 on_ready fired")
    print(f"Logged in as {bot.user}")

    await bot.change_presence(status=discord.Status.online)
    await bot.tree.sync(guild=None)
    print("✅ Slash commands synced")


async def main():
    async with bot:
        # All music commands, playlist UI, Lavalink nodes, and playback handling live in new_cog.py.
        await bot.load_extension("new_cog")
        await bot.start(TOKEN)


try:
    asyncio.run(main())
except Exception:
    print("💀 BOT CRASHED:")
    traceback.print_exc()
