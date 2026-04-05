import discord
from discord import app_commands
from discord.ext import commands
import wavelink
import os
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

NODES = [
    {"host": "lava-v4.ajieblogs.eu.org", "port": 443, "password": "https://dsc.gg/ajidevserver", "secure": True},
    {"host": "lava-all.ajieblogs.eu.org", "port": 443, "password": "https://dsc.gg/ajidevserver", "secure": True},
    {"host": "lava-v4.ajieblogs.eu.org", "port": 80, "password": "https://dsc.gg/ajidevserver", "secure": False},
    {"host": "lavalink.jirayu.net", "port": 443, "password": "youshallnotpass", "secure": True},
]


async def connect_nodes():
    nodes = [
        wavelink.Node(
            uri=f"http{'s' if n['secure'] else ''}://{n['host']}:{n['port']}",
            password=n["password"]
        )
        for n in NODES
    ]

    for i in range(5):  # retry system
        try:
            await wavelink.Pool.connect(nodes=nodes, client=bot)
            print("✅ Lavalink connected")
            return
        except Exception as e:
            print(f"❌ Lavalink connect failed (try {i+1}/5): {e}")
            await asyncio.sleep(5)

    print("💀 Failed to connect to all nodes.")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await connect_nodes()
    await bot.tree.sync()


@bot.tree.command(name="play", description="Play a song")
@app_commands.describe(query="Song name or URL")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    if not interaction.user.voice:
        return await interaction.followup.send("❌ Join a voice channel first.")

    channel = interaction.user.voice.channel

    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        player = await channel.connect(cls=wavelink.Player)

    tracks = await wavelink.Playable.search(query)

    if not tracks:
        return await interaction.followup.send("❌ No results found.")

    track = tracks[0]

    await player.play(track)

    await interaction.followup.send(f"▶️ Playing: {track.title}")


bot.run(TOKEN)
