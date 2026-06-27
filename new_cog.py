import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class LavalinkPlayer(wavelink.Player):
    async def on_voice_state_update(self, data, /) -> None:
        channel_id = data["channel_id"]

        if not channel_id:
            await self._destroy()
            return

        self._connected = True
        self._voice_state["voice"]["session_id"] = data["session_id"]
        self._voice_state["channel_id"] = str(channel_id)
        self.channel = self.client.get_channel(int(channel_id))  # type: ignore[arg-type]

    async def _dispatch_voice_update(self) -> None:
        assert self.guild is not None

        voice = self._voice_state["voice"]
        session_id = voice.get("session_id")
        token = voice.get("token")
        endpoint = voice.get("endpoint")
        channel_id = self._voice_state.get("channel_id")

        if not session_id or not token or not endpoint or not channel_id:
            return

        request = {
            "voice": {
                "sessionId": session_id,
                "token": token,
                "endpoint": endpoint,
                "channelId": channel_id,
            }
        }

        try:
            await self.node._update_player(self.guild.id, data=request)
        except wavelink.LavalinkException:
            await self.disconnect()
        else:
            self._connection_event.set()

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix='!',
            intents=intents
        )

    async def setup_hook(self):
        """Setup hook to connect to Lavalink"""
        node = wavelink.Node(
            uri='https://lavalinkv4.serenetia.com:443', # replace with a real one btw
            password='https://seretia.link/discord' # replace with a real password btw 
        )

        try:
            await wavelink.Pool.connect(client=self, nodes=[node])
            print("Successfully connected to Lavalink server!")
        except Exception as e:
            print(f"Failed to connect to Lavalink: {e}")

    async def on_ready(self):
        print(f'Bot logged in as {self.user}')
        print(f'Guilds: {len(self.guilds)}')

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            print(f'Synced {len(synced)} command(s)')
        except Exception as e:
            print(f'Failed to sync commands: {e}')

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """Event fired when Lavalink node is ready"""
        print(f'Lavalink node {payload.node.identifier} is ready!')
        print(f'Session ID: {payload.session_id}')

bot = Bot()

@bot.tree.command(name="music", description="Play music from YouTube or other sources")
@app_commands.describe(query="YouTube URL or search query")
async def music(interaction: discord.Interaction, query: str):
    """Play music command"""

    # Check if user is in voice channel
    if not interaction.user.voice:
        await interaction.response.send_message("You need to be in a voice channel!", ephemeral=True)
        return

    # Defer the response since connecting and loading might take time
    await interaction.response.defer()

    try:
        # Get the voice channel
        channel = interaction.user.voice.channel

        # Connect to voice channel if not already connected
        if not interaction.guild.voice_client:
            vc: LavalinkPlayer = await channel.connect(cls=LavalinkPlayer)
            print(f"Connected to voice channel: {channel.name}")
        else:
            vc: wavelink.Player = interaction.guild.voice_client

        # Search for tracks
        print(f"Searching for: {query}")

        # Determine if it's a URL or search query
        if query.startswith('http://') or query.startswith('https://'):
            tracks = await wavelink.Playable.search(query)
        else:
            tracks = await wavelink.Playable.search(f"ytsearch:{query}")

        if not tracks:
            await interaction.followup.send("No tracks found!")
            return

        # Get the first track
        track = tracks[0]

        print(f"Track found: {track.title}")
        print(f"Author: {track.author}")
        print(f"Duration: {track.length}ms")
        print(f"URI: {track.uri}")
        print(f"Source: {track.source}")

        # Play the track
        await vc.play(track)

        # Create embed for response
        embed = discord.Embed(
            title="Now Playing",
            description=f"**{track.title}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Author", value=track.author, inline=True)
        embed.add_field(name="Duration", value=f"{track.length // 60000}:{(track.length // 1000) % 60:02d}", inline=True)
        embed.add_field(name="Source", value=track.source.upper(), inline=True)

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        await interaction.followup.send(embed=embed)

        print(f"Started playing: {track.title}")
        print(f"Player state: playing={vc.playing}, paused={vc.paused}")

    except wavelink.exceptions.LavalinkException as e:
        print(f"Lavalink error: {e}")
        await interaction.followup.send(f"Lavalink error: {e}")
    except Exception as e:
        print(f"Error playing track: {e}")
        import traceback
        traceback.print_exc()
        await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="stop", description="Stop playing and disconnect")
async def stop(interaction: discord.Interaction):
    """Stop music and disconnect"""

    vc: wavelink.Player = interaction.guild.voice_client

    if not vc:
        await interaction.response.send_message("Not connected to a voice channel!", ephemeral=True)
        return

    await vc.disconnect()
    await interaction.response.send_message("Stopped and disconnected!")
    print("Stopped playback and disconnected")

@bot.tree.command(name="pause", description="Pause the current track")
async def pause(interaction: discord.Interaction):
    """Pause current track"""

    vc: wavelink.Player = interaction.guild.voice_client

    if not vc or not vc.playing:
        await interaction.response.send_message("Nothing is playing!", ephemeral=True)
        return

    await vc.pause(True)
    await interaction.response.send_message("Paused!")
    print("Paused playback")

@bot.tree.command(name="resume", description="Resume the current track")
async def resume(interaction: discord.Interaction):
    """Resume current track"""

    vc: wavelink.Player = interaction.guild.voice_client

    if not vc or not vc.paused:
        await interaction.response.send_message("Nothing is paused!", ephemeral=True)
        return

    await vc.pause(False)
    await interaction.response.send_message("Resumed!")
    print("Resumed playback")

@bot.tree.command(name="status", description="Check Lavalink and bot status")
async def status(interaction: discord.Interaction):
    """Check status of Lavalink connection and playback"""

    embed = discord.Embed(title="Bot Status", color=discord.Color.blue())

    # Check Lavalink nodes
    nodes = wavelink.Pool.nodes
    if nodes and len(nodes) > 0:
        node = list(nodes.values())[0]
        embed.add_field(
            name="Lavalink Node",
            value=f"Connected\nPlayers: {len(node.players)}",
            inline=True
        )
    else:
        embed.add_field(name="Lavalink Node", value="Not connected", inline=True)

    # Check voice client
    vc: wavelink.Player = interaction.guild.voice_client
    if vc:
        status_text = f"Channel: {vc.channel.name}\n"
        status_text += f"Playing: {vc.playing}\n"
        status_text += f"Paused: {vc.paused}\n"

        if vc.current:
            status_text += f"\n**Current Track:**\n{vc.current.title}"

        embed.add_field(name="Voice Status", value=status_text, inline=False)
    else:
        embed.add_field(name="Voice Status", value="Not connected to voice", inline=False)

    await interaction.response.send_message(embed=embed)

# Event for when a track starts
@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    """Event fired when a track starts playing"""
    print(f"Track started: {payload.track.title}")
    print(f"Player: {payload.player}")

# Event for when a track ends
@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    """Event fired when a track ends"""
    print(f"Track ended: {payload.track.title}")
    print(f"Reason: {payload.reason}")

    if payload.reason == "loadFailed":
        print("LOAD FAILED - The track failed to load/play!")
        print("This usually means:")
        print("  - Video is geo-blocked or region-restricted")
        print("  - Video is age-restricted")
        print("  - Video was deleted or made private")
        print("  - YouTube client compatibility issue")

# Event for track exceptions
@bot.event
async def on_wavelink_track_exception(payload: wavelink.TrackExceptionEventPayload):
    """Event fired when a track encounters an exception"""
    print(f"Track exception: {payload.track.title}")
    print(f"Error: {payload.exception}")
    print(f"Details: {payload}")

if __name__ == "__main__":
    if not TOKEN:
        print("BOT_TOKEN not found in .env file!")
    else:
        print("Starting bot...")
        bot.run(TOKEN)
