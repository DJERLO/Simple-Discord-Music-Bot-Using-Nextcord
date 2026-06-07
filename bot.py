import asyncio
import os
import time

import nextcord
import wavelink
from dotenv import load_dotenv
from nextcord import Interaction
from nextcord.ext import commands

from views import QueueView as QueueSongList

# Load variables from the .env file
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")

# Set up the bot with the necessary intents
intents = nextcord.Intents.default()
intents.message_content = True  # Enables the message content intent

bot = commands.Bot(command_prefix="/", intents=intents)


# Compatibility class to bridge Wavelink Player with Nextcord's VoiceProtocol
class WavelinkPlayer(wavelink.Player, nextcord.VoiceProtocol):
    pass


# Helper functions for time and progress display
def format_time(ms: int) -> str:
    """Formats milliseconds into M:SS."""
    seconds = int(ms // 1000)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def get_track_artwork(track: wavelink.Playable) -> str:
    """Helper to retrieve the best available artwork for a track."""
    artwork = getattr(track, "artwork", None) or getattr(track, "thumbnail", None)
    if not artwork and "youtube" in getattr(track, "source", ""):
        return f"https://i.ytimg.com/vi/{track.identifier}/hqdefault.jpg"
    return artwork


# Track the active music player message per guild
ACTIVE_PLAYERS = {}
AUTO_DISCONNECT_TASKS = {}

VOICE_DISCONNECT_TIMEOUT = 300.0  # 5 minutes in seconds
MESSAGE_DELETE_TIMEOUT = 60.0     # 1 minute in seconds

@bot.event
async def on_voice_state_update(member, before, after):
    # Ignore bot's own voice state changes to prevent logic collisions during moves
    if member.bot:
        return

    # Get the voice client for the server
    vc = member.guild.voice_client
    if not vc:
        return

    old_channel = before.channel
    new_channel = after.channel
    guild_id = str(member.guild.id)

    # Scenario A: The bot was left alone in an empty channel
    if old_channel and vc.channel == old_channel:
        # Count human users remaining in the channel
        human_count = sum(1 for m in old_channel.members if not m.bot)

        if human_count == 0:
            # If a countdown task is already running for this guild, do nothing
            if guild_id in AUTO_DISCONNECT_TASKS:
                return

            # Define the background cleanup task
            async def disconnect_timeout():
                try:
                    await asyncio.sleep(VOICE_DISCONNECT_TIMEOUT)
                    # Re-verify the current state of the voice client
                    current_vc = member.guild.voice_client
                    if (
                        current_vc
                        and current_vc.channel
                        and sum(1 for m in current_vc.channel.members if not m.bot) == 0
                    ):
                        # Clear state data before leaving
                        if hasattr(current_vc, "queue"):
                            current_vc.queue.clear()

                        await bot.change_presence(activity=None)

                        player_msg = ACTIVE_PLAYERS.get(guild_id)
                        if player_msg:
                            try:
                                channel_name = current_vc.channel.name
                                await player_msg.channel.send(
                                    f"I've left **{channel_name}** because "
                                    "it's been empty for too long.",
                                    delete_after=MESSAGE_DELETE_TIMEOUT,
                                )
                                await player_msg.delete()
                            except Exception:
                                pass
                            ACTIVE_PLAYERS[guild_id] = None

                        await current_vc.disconnect()
                except asyncio.CancelledError:
                    pass  # Task was aborted safely by a user rejoining
                finally:
                    AUTO_DISCONNECT_TASKS.pop(guild_id, None)

            # Spin up the background task
            task = asyncio.create_task(disconnect_timeout())
            AUTO_DISCONNECT_TASKS[guild_id] = task

    # Scenario B: A human user joined a channel where the bot is currently idling
    if new_channel and vc.channel == new_channel:
        human_count = sum(1 for m in new_channel.members if not m.bot)
        if human_count > 0:
            # Cancel the active countdown task if a human rejoins
            task = AUTO_DISCONNECT_TASKS.pop(guild_id, None)
            if task:
                task.cancel()
                try:
                    await task  # Await the task to ensure cancellation is processed
                except asyncio.CancelledError:
                    pass


@bot.event
async def on_ready():
    """Connect to Lavalink node (defined in application.yml) when the bot is ready"""
    node: wavelink.Node = wavelink.Node(
        uri="http://127.0.0.1:2333", password="youshallnotpass"
    )
    await wavelink.Pool.connect(nodes=[node], client=bot)
    await bot.sync_application_commands()


# Slash Command to skip the current song
@bot.slash_command(name="skip", description="Skips the current playing song")
async def skip(interaction: Interaction):
    """
    Skips the currently playing song in the voice channel.
    If no song is playing, it informs the user.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client
    if vc and (vc.playing or vc.paused):
        await vc.skip()
        await interaction.response.send_message(
            "Skipped the current song.", ephemeral=True
        )
    else:
        await interaction.response.send_message("Not playing anything to skip.")


# Slash Command to pause the currently playing song
@bot.slash_command(name="pause", description="Pause the currently playing song.")
async def pause(interaction: Interaction):
    """
    Pauses the currently playing song in the voice channel.
    If no song is playing, it informs the user.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if vc is None:
        return await interaction.response.send_message(
            "I'm not in a voice channel.", ephemeral=True
        )

    # Check if something is actually playing
    if not vc.playing:
        return await interaction.response.send_message(
            "Nothing is currently playing.", ephemeral=True
        )

    # Pause the track
    await vc.pause(True)
    await interaction.response.send_message("Playback paused!", ephemeral=True)


# Slash Command to resume the currently paused song
@bot.slash_command(name="resume", description="Resume the currently paused song.")
async def resume(interaction: Interaction):
    """
    Resumes the currently paused song in the voice channel.
    If no song is paused, it informs the user.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if vc is None:
        return await interaction.response.send_message(
            "I'm not in a voice channel.", ephemeral=True
        )

    # Check if it's actually paused
    if not vc.paused:
        return await interaction.response.send_message(
            "I’m not paused right now.", ephemeral=True
        )

    # Resume playback
    await vc.pause(False)
    await interaction.response.send_message("Playback resumed!", ephemeral=True)


# Slash Command to stop playback and clear the queue
@bot.slash_command(name="stop", description="Stop playback and clear the queue.")
async def stop(interaction: Interaction):
    """
    Stops playback and clears the queue for the current guild.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client

    if not vc:
        return await interaction.response.send_message(
            "I'm not connected to any voice channel.", ephemeral=True
        )

    guild_id_str = str(interaction.guild_id)
    vc.queue.clear()

    # Dynamic Cleanup of Persistent Voice Channel Embed Interface
    if guild_id_str in ACTIVE_PLAYERS:
        try:
            await ACTIVE_PLAYERS[guild_id_str].delete()
        except Exception:
            pass
        ACTIVE_PLAYERS[guild_id_str] = None

    await vc.disconnect()
    await bot.change_presence(activity=None)
    await interaction.response.send_message(
        "Stopped playback and disconnected", ephemeral=True
    )


@bot.slash_command(name="play", description="Play a song or add it to the queue.")
async def play(interaction: Interaction, song: str):
    """
    Plays a song or adds it to the queue.
    Args:
        interaction (Interaction): The interaction object from the slash command.
        song (str): The song to play or add to the queue.
    returns:
        None
    """
    await interaction.response.defer()

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send(
            "You must be in a voice channel.", ephemeral=True, 
            delete_after=MESSAGE_DELETE_TIMEOUT
        )
        return

    voice_channel = interaction.user.voice.channel
    vc: WavelinkPlayer = interaction.guild.voice_client

    if not vc:
        vc = await voice_channel.connect(cls=WavelinkPlayer)
    elif voice_channel != vc.channel:
        guild_id = str(interaction.guild_id)

        # 1. Clean up the old player interface before moving to a new channel
        old_msg = ACTIVE_PLAYERS.get(guild_id)
        if old_msg:
            try:
                await old_msg.delete()
            except Exception:
                pass
            ACTIVE_PLAYERS[guild_id] = None

        # Cancel pending disconnect tasks and reset state if the bot was idling
        task = AUTO_DISCONNECT_TASKS.pop(guild_id, None)
        if task:
            task.cancel()
            try:
                # Wait for the task to acknowledge cancellation
                await task
            except asyncio.CancelledError:
                pass
            vc.queue.clear()  # Clear the queue when moving to a new channel
            if vc.playing or vc.paused:
                vc.ignore_next_cleanup = True
                await vc.stop()  # Stop current playback when moving to a new channel

        try:
            # Attempt to move the player to the user's new channel
            await vc.move_to(voice_channel)
        except Exception:
            # If moving fails (e.g. ChannelTimeoutException)
            # fallback to a fresh connection
            try:
                await vc.disconnect()
            except Exception:
                pass
            vc = await voice_channel.connect(cls=WavelinkPlayer)

    # Search for the track(s) using Wavelink's optimized search
    tracks = await wavelink.Playable.search(song)

    if not tracks:
        await interaction.followup.send(
            "No results found.", 
            ephemeral=True, 
            delete_after=MESSAGE_DELETE_TIMEOUT
        )
        return

    # Store requester data in the track extras
    extras = {
        "requester": interaction.user.display_name,
        "avatar": interaction.user.avatar.url if interaction.user.avatar else None,
    }

    if isinstance(tracks, wavelink.Playlist):
        for track in tracks:
            track.extras = extras
        await vc.queue.put_wait(tracks)
        message = f"Added playlist **{tracks.name}** ({len(tracks)} tracks) to queue."
        thumbnail = getattr(tracks, "artwork", None) or (
            tracks[0].artwork if tracks else None
        )
    else:
        track = tracks[0]
        track.extras = extras
        await vc.queue.put_wait(track)
        message = (
            f"**{track.title}** by **{track.author}** ({format_time(track.length)})"
        )
        thumbnail = get_track_artwork(track)

    embed = nextcord.Embed(
        title="Added to Queue", description=message, color=nextcord.Color.orange()
    )
    if thumbnail:
        embed.set_image(url=thumbnail)
    embed.set_footer(
        text=f"Requested by {interaction.user.display_name}", icon_url=extras["avatar"]
    )

    await interaction.followup.send(
        embed=embed,
        ephemeral=True,
        delete_after=MESSAGE_DELETE_TIMEOUT
    )

    if not vc.playing:
        await vc.play(vc.queue.get())


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player: WavelinkPlayer = payload.player
    track: wavelink.Playable = payload.track
    guild_id = str(player.guild.id)

    embed = nextcord.Embed(
        title="💿 Now Playing",
        description=f"[{track.title}]({track.uri})",
        color=nextcord.Color.green(),
    )

    embed.add_field(name="Artist", value=track.author, inline=True)
    embed.add_field(name="Duration", value=format_time(track.length), inline=True)

    artwork = get_track_artwork(track)

    if artwork:
        embed.set_image(url=artwork)

    requester = getattr(track.extras, "requester", "Unknown")
    avatar = getattr(track.extras, "avatar", None)
    embed.set_footer(
        text=f"Requested by {requester} | In Voice Channel", icon_url=avatar
    )

    await bot.change_presence(
        activity=nextcord.Activity(
            type=nextcord.ActivityType.listening,
            name=f"{track.title} by {track.author} [{format_time(track.length)}]",
            timestamps={
                "start": int(time.time()),
                "end": int(time.time() + (track.length // 1000)),
            },
        )
    )

    # Update or send the player interface message
    try:
        msg = ACTIVE_PLAYERS.get(guild_id)
        if msg:
            try:
                await msg.edit(embed=embed)
                return
            except Exception:
                pass
        ACTIVE_PLAYERS[guild_id] = await player.channel.send(embed=embed)
    except Exception:
        ACTIVE_PLAYERS[guild_id] = None


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player: WavelinkPlayer = payload.player
    if not player or not player.guild:
        return

    guild_id = str(player.guild.id)

    # 1. Handle intentional migration: if our custom flag is set, skip the cleanup
    if getattr(player, "ignore_next_cleanup", False):
        player.ignore_next_cleanup = False
        return

    # 2. Handle track replacement: if the song was replaced by /play, do nothing
    if payload.reason == "replaced":
        return

    if not player.queue.is_empty:
        next_track = player.queue.get()
        await player.play(next_track)
    else:
        # Clean up the interface when the queue finishes
        msg = ACTIVE_PLAYERS.get(guild_id)
        if msg:
            try:
                await msg.delete()
            except Exception:
                pass
            ACTIVE_PLAYERS[guild_id] = None

        await player.disconnect()
        await bot.change_presence(activity=None)


@bot.slash_command(name="queue", description="Show the current music queue.")
async def queue(interaction: Interaction):
    """
    Displays the current music queue for the guild in a paginated embed view.
    Only the user who invoked the command can interact with the pagination buttons.

    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client
    if not vc or vc.queue.is_empty:
        await interaction.response.send_message(
            "The queue is currently empty.", ephemeral=True
        )
        return

    # Convert Wavelink queue to the format expected by our QueueView
    songs_list = []
    for track in vc.queue:
        songs_list.append((track.uri, track.title, track.artwork, track.length / 1000))

    view = QueueSongList(songs_list, interaction.user, str(interaction.guild_id))
    await interaction.response.send_message(
        embed=view.get_embed(), view=view, ephemeral=True
    )
    view.message = await interaction.original_message()


@bot.slash_command(name="clearqueue", description="Clear the current music queue.")
async def clearqueue(interaction: Interaction):
    """
    Clears the current music queue for the guild.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client
    if vc:
        vc.queue.clear()
    await interaction.response.send_message(
        "The music queue has been cleared.", ephemeral=True
    )


@bot.slash_command(name="shuffle", description="Shuffle the current music queue.")
async def shuffle(interaction: Interaction):
    """
    Shuffles the current music queue for the guild.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client
    if vc and not vc.queue.is_empty:
        vc.queue.shuffle()
        await interaction.response.send_message(
            "The music queue has been shuffled.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "The queue is currently empty, nothing to shuffle.", ephemeral=True
        )


@bot.slash_command(
    name="nowplaying", description="Show details of the currently playing song."
)
async def nowplaying(interaction: Interaction):
    """Shows a detailed embed of the current track including a progress bar."""
    vc: WavelinkPlayer = interaction.guild.voice_client

    if not vc or not vc.playing:
        return await interaction.response.send_message(
            "Nothing is currently playing.", ephemeral=True
        )

    track = vc.current
    embed = nextcord.Embed(
        title="💿 Currently Playing",
        description=f"[{track.title}]({track.uri})",
        color=nextcord.Color.blue(),
    )

    embed.add_field(name="Artist", value=track.author, inline=True)
    embed.add_field(name="Duration", value=format_time(track.length), inline=True)

    artwork = get_track_artwork(track)

    if artwork:
        embed.set_thumbnail(url=artwork)

    requester = getattr(track.extras, "requester", "Unknown")
    avatar = getattr(track.extras, "avatar", None)
    embed.set_footer(text=f"Requested by {requester}", icon_url=avatar)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="ping", description="Check the bot's latency.")
async def ping(interaction: Interaction):
    """
    Responds with the bot's latency in milliseconds.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(
        f"Pong! Latency: {latency_ms}ms", ephemeral=True
    )


@bot.slash_command(name="help", description="Show available commands and usage.")
async def help_command(interaction: Interaction):
    """
    Provides a help message listing all available commands and their descriptions.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    help_text = (
        "**Available Commands:**\n"
        "/play [song name or URL] - Play a song or add it to the queue.\n"
        "/skip - Skip the currently playing song.\n"
        "/pause - Pause the currently playing song.\n"
        "/resume - Resume the currently paused song.\n"
        "/shuffle - Shuffle the current music queue.\n"
        "/nowplaying - Show details of the currently playing song.\n"
        "/stop - Stop playback and clear the queue.\n"
        "/queue - Show the current music queue.\n"
        "/clearqueue - Clear the current music queue.\n"
        "/ping - Check the bot's latency.\n"
        "/help - Show this help message."
    )
    await interaction.response.send_message(help_text, ephemeral=True)


# Run the bot with your token
if __name__ == "__main__":
    bot.run(bot_token)
