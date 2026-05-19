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
async def on_wavelink_node_ready(payload):
    print(f"🟢 Node ready: {payload.node.identifier}")


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

        # Turn on AutoPlay to enabled mode.
        player.autoplay = wavelink.AutoPlayMode.enabled

        # Lock the player to this channel.
        if not hasattr(player, "home"):
            player.home = channel
        elif player.home != channel:
            return await interaction.followup.send(
                f"You can only play songs in {player.home.mention}, as the player has already started there."
            )

        # 📀 Playlist vs single (queue-based playback logic)
        if isinstance(tracks, wavelink.Playlist):
            added = await player.queue.put_wait(tracks)
            await interaction.followup.send(
                f"Added the playlist **`{tracks.name}`** ({added} songs) to the queue."
            )
        else:
            track = tracks[0]
            print(f"🎵 Selected: {track.title}")
            await player.queue.put_wait(track)
            await interaction.followup.send(f"Added **`{track}`** to the queue.")

        if not player.playing:
            # Play now since nothing is currently playing.
            await player.play(player.queue.get(), volume=30)
            print("✅ Play command sent")

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
