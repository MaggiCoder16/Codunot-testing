import discord
from discord import app_commands
from discord.ext import commands
import wavelink
import asyncio
import os
import logging
import traceback
import json
from pathlib import Path

# 🔥 Logging
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("DISCORD_TOKEN")
print("TOKEN LOADED:", bool(TOKEN))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

PLAYLISTS_FILE = Path("playlists.json")
playlists_store: dict[str, dict[str, list[str]]] = {}


# 🔗 Lavalink Nodes (V4 ONLY)
NODES = [
    {"uri": "https://lavalinkv4.serenetia.com:443", "password": "https://dsc.gg/ajidevserver"},
]


def load_playlists():
    global playlists_store
    if not PLAYLISTS_FILE.exists():
        playlists_store = {}
        save_playlists()
        return

    try:
        with PLAYLISTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                playlists_store = data
            else:
                playlists_store = {}
    except Exception:
        traceback.print_exc()
        playlists_store = {}


def save_playlists():
    with PLAYLISTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(playlists_store, f, indent=2)


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


async def get_or_connect_player(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.followup.send("❌ Join a voice channel first.")
        return None

    channel = interaction.user.voice.channel
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        print("🔗 Connecting to VC...")
        player = await channel.connect(cls=wavelink.Player)

        for _ in range(10):
            if player.connected:
                break
            await asyncio.sleep(0.3)

    if not hasattr(player, "home"):
        player.home = channel
    elif player.home != channel:
        await interaction.followup.send(
            f"You can only play songs in {player.home.mention}, as the player has already started there."
        )
        return None

    return player


# 🚀 Ready Event
@bot.event
async def on_ready():
    print("🔥 on_ready fired")
    print(f"Logged in as {bot.user}")

    await bot.change_presence(status=discord.Status.online)

    load_playlists()

    await connect_nodes()

    await bot.tree.sync(guild=None)
    print("✅ Slash commands synced")


class PlaylistCreateModal(discord.ui.Modal, title="Create Playlist"):
    playlist_title = discord.ui.TextInput(label="Playlist title", placeholder="My favorite songs", max_length=80)
    songs = discord.ui.TextInput(
        label="Songs (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="Song A\nSong B\nhttps://youtube.com/watch?v=...",
        max_length=3000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        playlists_store.setdefault(guild_id, {})

        title = str(self.playlist_title.value).strip()
        entries = [line.strip() for line in str(self.songs.value).splitlines() if line.strip()]

        if not entries:
            return await interaction.followup.send("❌ You need at least one song.", ephemeral=True)

        playlists_store[guild_id][title] = entries
        save_playlists()

        await interaction.followup.send(
            f"✅ Playlist **{title}** saved with **{len(entries)}** songs.",
            ephemeral=True,
        )


playlist_group = app_commands.Group(name="playlist", description="Playlist commands")


@playlist_group.command(name="create", description="Create a playlist in a modal")
async def playlist_create(interaction: discord.Interaction):
    await interaction.response.send_modal(PlaylistCreateModal())


@bot.tree.command(name="playlists", description="List saved playlists")
async def playlists(interaction: discord.Interaction):
    await interaction.response.defer()

    guild_id = str(interaction.guild_id)
    guild_playlists = playlists_store.get(guild_id, {})

    if not guild_playlists:
        return await interaction.followup.send("❌ No playlists saved for this server yet. Use `/playlist create`.")

    lines = [f"• **{title}** ({len(songs)} songs)" for title, songs in guild_playlists.items()]
    lines.append("")
    lines.append("▶️ Play one with: `/playlist play name:<playlist name>`")
    return await interaction.followup.send("📚 Saved playlists:\n" + "\n".join(lines))


@playlist_group.command(name="play", description="Play a saved playlist")
@app_commands.describe(name="Name of the saved playlist")
async def playlist_play(interaction: discord.Interaction, name: str):
    await interaction.response.defer()

    guild_id = str(interaction.guild_id)
    guild_playlists = playlists_store.get(guild_id, {})

    if not guild_playlists:
        return await interaction.followup.send("❌ No playlists saved for this server yet. Use `/playlist create`.")

    if name not in guild_playlists:
        return await interaction.followup.send("❌ Playlist not found. Use `/playlists` to view names.")

    player = await get_or_connect_player(interaction)
    if not player:
        return

    player.autoplay = wavelink.AutoPlayMode.enabled

    added = 0
    for query in guild_playlists[name]:
        tracks = await wavelink.Playable.search(query, source="ytsearch")
        if tracks:
            await player.queue.put_wait(tracks[0])
            added += 1

    if added == 0:
        return await interaction.followup.send("❌ Could not find any playable tracks in this playlist.")

    if not player.playing:
        await player.play(player.queue.get(), volume=30)

    await interaction.followup.send(f"▶️ Added **{added}** songs from playlist **{name}** to the queue.")


bot.tree.add_command(playlist_group)


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
        player = await get_or_connect_player(interaction)
        if not player:
            return

        print("🔍 Searching:", query)

        # 🔍 Force YouTube search
        tracks = await wavelink.Playable.search(query, source="ytsearch")

        print("🔍 Results:", tracks)

        if not tracks:
            return await interaction.followup.send("❌ No results found.")

        # Turn on AutoPlay to enabled mode.
        player.autoplay = wavelink.AutoPlayMode.enabled

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
