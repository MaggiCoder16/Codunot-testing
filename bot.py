import discord
from discord import app_commands
from discord.ext import commands
import wavelink
import asyncio
import os
import logging
import traceback

# 🔥 Logging
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("DISCORD_TOKEN")
print("TOKEN LOADED:", bool(TOKEN))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 🔗 Lavalink Nodes (V4 ONLY)
NODES = [
    {"host": "lava-v4.ajieblogs.eu.org", "port": 443, "password": "https://dsc.gg/ajidevserver", "secure": True},
    {"host": "lava-all.ajieblogs.eu.org", "port": 443, "password": "https://dsc.gg/ajidevserver", "secure": True},
    {"host": "lava-v4.ajieblogs.eu.org", "port": 80, "password": "https://dsc.gg/ajidevserver", "secure": False},
    {"host": "lavalink.jirayu.net", "port": 443, "password": "youshallnotpass", "secure": True},
]


# 🔄 Connect Lavalink Nodes (with retries)
async def connect_nodes():
    nodes = [
        wavelink.Node(
            uri=f"http{'s' if n['secure'] else ''}://{n['host']}:{n['port']}",
            password=n["password"]
        )
        for n in NODES
    ]

    for i in range(5):
        try:
            print(f"🔄 Connecting to Lavalink... ({i+1}/5)")
            await wavelink.Pool.connect(nodes=nodes, client=bot)
            print("✅ Lavalink connected")
            return
        except Exception as e:
            print(f"❌ Lavalink failed: {e}")
            await asyncio.sleep(5)

    print("💀 All nodes failed")


# 🚀 Ready Event
@bot.event
async def on_ready():
    print("🔥 on_ready fired")
    print(f"Logged in as {bot.user}")

    await bot.change_presence(status=discord.Status.online)

    await connect_nodes()

    await bot.tree.sync(guild=None)
    print("✅ Slash commands synced")


# 🎧 Wavelink Events (DEBUG GOLD 🔥)
@bot.listen()
async def on_wavelink_node_ready(node):
    print(f"🟢 Node ready: {node.uri}")


@bot.listen()
async def on_wavelink_track_start(payload):
    print(f"▶️ Track started: {payload.track.title}")


@bot.listen()
async def on_wavelink_track_end(payload):
    print(f"⏹️ Track ended: {payload.track.title}")


@bot.listen()
async def on_wavelink_track_exception(payload):
    print(f"💀 Track error: {payload.exception}")


@bot.listen()
async def on_wavelink_websocket_closed(payload):
    print(f"🔌 Websocket closed: {payload.code} | {payload.reason}")


# 🎵 /play command (ONLY COMMAND)
@bot.tree.command(name="play", description="Play a song")
@app_commands.describe(query="Song name or URL")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    try:
        # ❌ Not in VC
        if not interaction.user.voice:
            return await interaction.followup.send("❌ Join a voice channel first.")

        channel = interaction.user.voice.channel

        player: wavelink.Player = interaction.guild.voice_client

        # 🔗 Connect if not connected
        if not player:
            print("🔗 Connecting to VC...")
            player = await channel.connect(cls=wavelink.Player)

            # ⚠️ Wait until ready (VERY IMPORTANT)
            for _ in range(10):
                if player.connected:
                    break
                await asyncio.sleep(0.3)

        print("🔍 Searching:", query)

        # 🔍 Force YouTube search
        tracks = await wavelink.Playable.search(query, source="ytsearch")

        print("🔍 Results:", tracks)

        if not tracks:
            return await interaction.followup.send("❌ No results found.")

        # 📀 Playlist vs single
        if isinstance(tracks, wavelink.Playlist):
            track = tracks.tracks[0]
        else:
            track = tracks[0]

        print(f"🎵 Selected: {track.title}")

        # ▶️ Play
        await player.play(track)

        print("✅ Play command sent")

        await interaction.followup.send(f"▶️ Playing: {track.title}")

    except Exception:
        print("💀 ERROR in /play:")
        traceback.print_exc()
        await interaction.followup.send("❌ Something went wrong.")


# 🚀 Safe startup (GitHub Actions friendly)
async def main():
    async with bot:
        await bot.start(TOKEN)


try:
    asyncio.run(main())
except Exception:
    print("💀 BOT CRASHED:")
    traceback.print_exc()
