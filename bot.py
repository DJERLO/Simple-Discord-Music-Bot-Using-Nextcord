import asyncio
import logging
import os
import time
from logging.handlers import RotatingFileHandler

import nextcord
import wavelink
from dotenv import load_dotenv
from nextcord import Interaction
from nextcord.ext import commands

from views import QueueView as QueueSongList

# Load variables from the .env file
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")

# Create a rotating file handler for logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MusicBot")

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    "music_bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

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


def create_now_playing_embed(player: WavelinkPlayer, track: wavelink.Playable, is_persistent: bool = True) -> nextcord.Embed:
    """Centralized helper to create the Now Playing embed for events and commands."""
    embed = nextcord.Embed(
        title="💿 Now Playing" if is_persistent else "💿 Currently Playing",
        description=f"[{track.title}]({track.uri})",
        color=nextcord.Color.green() if is_persistent else nextcord.Color.blue(),
    )

    embed.add_field(name="Artist", value=track.author, inline=True)
    
    album_name = getattr(track, "album", None)
    if album_name and hasattr(album_name, "name") and album_name.name:
        embed.add_field(name="Album", value=album_name.name, inline=True)

    embed.add_field(name="Duration", value=format_time(track.length), inline=True)

    # Status Indicators
    loop_status = "✅ Enabled" if getattr(player, "loop", False) else "❌ Disabled"
    autoplay_mode = player.autoplay
    ap_label = {
        wavelink.AutoPlayMode.enabled: "✅ Full",
        wavelink.AutoPlayMode.partial: "✨ Partial",
        wavelink.AutoPlayMode.disabled: "❌ Disabled"
    }.get(autoplay_mode, "Unknown")

    embed.add_field(name="Volume", value=f"{player.volume}%", inline=True)
    embed.add_field(name="Looping", value=loop_status, inline=True)
    embed.add_field(name="Autoplay", value=ap_label, inline=True)

    artwork = get_track_artwork(track)
    if artwork:
        if is_persistent:
            embed.set_image(url=artwork)
        else:
            embed.set_thumbnail(url=artwork)

    requester = getattr(track.extras, "requester", "Autoplay")
    avatar = getattr(track.extras, "avatar", None)
    if requester == "Autoplay" and not avatar:
        avatar = bot.user.avatar.url if bot.user.avatar else None

    footer_text = f"Requested by {requester}"
    if is_persistent:
        footer_text += " | In Voice Channel"
    
    embed.set_footer(text=footer_text, icon_url=avatar)
    return embed


async def update_player_message(player: WavelinkPlayer):
    """Updates the existing persistent player message in the channel with current state."""
    guild_id = str(player.guild.id)
    msg = ACTIVE_PLAYERS.get(guild_id)
    if msg and player.current:
        embed = create_now_playing_embed(player, player.current, is_persistent=True)
        try:
            await msg.edit(embed=embed)
        except Exception:
            pass


# Track the active music player message per guild
ACTIVE_PLAYERS = {}
AUTO_DISCONNECT_TASKS = {}
GUILD_AUTOPLAY_MODES = {}
VOICE_DISCONNECT_TIMEOUT = 300.0  # 5 minutes in seconds
MESSAGE_DELETE_TIMEOUT = 60.0  # 1 minute in seconds


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

            logger.info(
                f"Empty channel detected in guild {guild_id}. "
                f"Starting {VOICE_DISCONNECT_TIMEOUT}s disconnect timer."
            )

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
                        logger.info(f"Inactivity timer expired for guild {guild_id}.")
                        # Clear state data before leaving
                        if hasattr(current_vc, "queue"):
                            current_vc.queue.clear()

                        await bot.change_presence(activity=None)

                        player_msg = ACTIVE_PLAYERS.get(guild_id)
                        if player_msg:
                            try:
                                channel_name = current_vc.channel.name
                                logger.info(
                                    f"Bot leaving {channel_name}"
                                    f"({guild_id}) due to inactivity."
                                )
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
                    logger.info(f"Disconnect timer for guild {guild_id} was cancelled.")
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
                logger.info(
                    f"Human rejoined channel in guild {guild_id}. Stopping timer."
                )
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
        await interaction.response.send_message("Not playing anything to skip.", ephemeral=True)


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
            "You must be in a voice channel.",
            ephemeral=True,
            delete_after=MESSAGE_DELETE_TIMEOUT,
        )
        return

    voice_channel = interaction.user.voice.channel
    vc: WavelinkPlayer = interaction.guild.voice_client

    if not vc:
        vc = await voice_channel.connect(cls=WavelinkPlayer)
        vc.autoplay = GUILD_AUTOPLAY_MODES.get(str(interaction.guild_id), wavelink.AutoPlayMode.disabled)
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
            logger.info(
                f"New play request in guild {guild_id}. Aborting disconnect timer."
            )
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
            "No results found.", ephemeral=True, delete_after=MESSAGE_DELETE_TIMEOUT
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
        embed=embed, ephemeral=True, delete_after=MESSAGE_DELETE_TIMEOUT
    )

    if not vc.playing:
        track = vc.queue.get()
        kwargs = {}
        if vc.autoplay == wavelink.AutoPlayMode.partial:
            kwargs["populate"] = True
            kwargs["max_populate"] = 5

        await vc.play(track, **kwargs)


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player: WavelinkPlayer = payload.player
    track: wavelink.Playable = payload.track
    guild_id = str(player.guild.id)

    embed = create_now_playing_embed(player, track, is_persistent=True)

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

    # 3. Handle Looping: Replay the current track if loop is enabled
    if getattr(player, "loop", False):
        await player.play(payload.track)
        return
    
    # 4. Determine the next track to play (checking user queue, then partial auto_queue)
    next_track = None
    kwargs = {}

    if not player.queue.is_empty:
        next_track = player.queue.get()
        if player.autoplay == wavelink.AutoPlayMode.partial:
            kwargs["populate"] = True
            kwargs["max_populate"] = 5
    elif player.autoplay == wavelink.AutoPlayMode.partial:
        # If auto_queue ALREADY has songs, grab the next one
        if not player.auto_queue.is_empty:
            next_track = player.auto_queue.get()
            kwargs["populate"] = True
            kwargs["max_populate"] = 5
        else:
            # BUG FIX: auto_queue is empty because it was skipped early or hadn't filled yet!
            # Force-populate recommendations using the song that just ended (payload.track)
            logger.info(f"Guild {guild_id}: Auto-queue empty on track end. Force populating recommendations.")
            kwargs["populate"] = True
            kwargs["max_populate"] = 5
            # Passing payload.track tells Lavalink what to base the new recommendations on
            await player.play(payload.track, **kwargs)
            return
    
    # 5. Execute playback or handle clean disconnects
    if next_track:
        await player.play(next_track, **kwargs)
    else:
        # 6. Handle Autoplay transition
        if player.autoplay == wavelink.AutoPlayMode.enabled:
            return
            
        # Only clean up the interface if the queue is empty AND autoplay is disabled
        msg = ACTIVE_PLAYERS.get(guild_id)
        if msg:
            try:
                await msg.delete()
            except Exception:
                pass
            ACTIVE_PLAYERS[guild_id] = None

        logger.info(f"Queue empty in guild {guild_id}. Disconnecting.")
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
    if not vc:
        return await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)

    # Convert Wavelink queue to the format expected by our QueueView
    songs_list = []
    for track in vc.queue:
        songs_list.append((track.uri, track.title, get_track_artwork(track), track.length / 1000))

    # Show recommended tracks from AutoQueue if mode is partial
    if vc.autoplay == wavelink.AutoPlayMode.partial and not vc.auto_queue.is_empty:
        for track in list(vc.auto_queue)[:5]:
            songs_list.append(
                (track.uri, f"✨ {track.title} (Auto-Queue)", get_track_artwork(track), track.length / 1000)
            )

    if not songs_list:
        return await interaction.response.send_message(
            "The queue is currently empty.", ephemeral=True
        )

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
    embed = create_now_playing_embed(vc, track, is_persistent=False)
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
        "/join - Make the bot join your voice channel.\n"
        "/volume - Set the playback volume (0-100).\n"
        "/loop - Toggle looping of the current track.\n"
        "/autoplay - Set autoplay mode for continuous music.\n"
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


@bot.slash_command(name="join", description="Make the bot join your voice channel.")
async def join(interaction: Interaction):
    """
    Makes the bot join the voice channel of the user who invoked the command.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            "You must be in a voice channel to use this command.",
            ephemeral=True,
            delete_after=MESSAGE_DELETE_TIMEOUT,
        )
        return

    voice_channel = interaction.user.voice.channel
    vc: WavelinkPlayer = interaction.guild.voice_client

    if vc and vc.channel == voice_channel:
        await interaction.response.send_message(
            "I'm already in your voice channel.", ephemeral=True
        )
        return
    elif vc and vc.channel != voice_channel:
        await vc.move_to(voice_channel)
    else:
        vc = await voice_channel.connect(cls=WavelinkPlayer)
        # Apply persistent autoplay mode if set
        vc.autoplay = GUILD_AUTOPLAY_MODES.get(str(interaction.guild_id), wavelink.AutoPlayMode.disabled)

    await interaction.response.send_message(
        f"Joined **{voice_channel.name}**!", ephemeral=True
    )

@bot.slash_command(name="volume", description="Set the playback volume (0-100).")
async def volume(interaction: Interaction, value: int):
    """
    Sets the playback volume for the current guild.
    Args:
        interaction (Interaction): The interaction object from the slash command.
        value (int): The desired volume level (0-100).
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client

    if not vc:
        return await interaction.response.send_message(
            "I'm not connected to any voice channel.", ephemeral=True
        )

    if value < 0 or value > 100:
        return await interaction.response.send_message(
            "Please provide a volume value between 0 and 100.", ephemeral=True
        )

    await vc.set_volume(value)
    await update_player_message(vc)
    await interaction.response.send_message(f"Volume set to {value}%.", ephemeral=True)

@bot.slash_command(name="loop", description="Toggle looping of the current track.")
async def loop(interaction: Interaction):
    """
    Toggles looping of the currently playing track.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client

    if not vc or not vc.playing:
        return await interaction.response.send_message(
            "Nothing is currently playing to loop.", ephemeral=True
        )

    vc.loop = not getattr(vc, "loop", False)
    status = "enabled" if vc.loop else "disabled"
    await update_player_message(vc)
    await interaction.response.send_message(f"Looping {status} for the current track.", ephemeral=True)

@bot.slash_command(name="autoplay", description="Set autoplay mode for continuous music.")
async def autoplay(
    interaction: Interaction,
    mode: str = nextcord.SlashOption(
        name="mode",
        description="Select the autoplay behavior",
        choices={
            "Enabled": "enabled",
            "Partial": "partial",
            "Disabled": "disabled",
        },
    ),
):
    """
    Sets the autoplay mode. 'Partial' is often used as an 'auto-queue' mode.
    Args:
        interaction (Interaction): The interaction object from the slash command.
        mode (str): The specific autoplay mode to apply.
    returns:
        None
    """
    vc: WavelinkPlayer = interaction.guild.voice_client

    if not vc:
        return await interaction.response.send_message(
            "I'm not connected to any voice channel.", ephemeral=True
        )

    mode_map = {
        "enabled": wavelink.AutoPlayMode.enabled,
        "partial": wavelink.AutoPlayMode.partial,
        "disabled": wavelink.AutoPlayMode.disabled,
    }

    GUILD_AUTOPLAY_MODES[str(interaction.guild_id)] = mode_map[mode]
    
    if vc:
        vc.autoplay = mode_map[mode]
        await update_player_message(vc)
    
    await interaction.response.send_message(
        f"Autoplay mode has been set to: **{mode.capitalize()}**", ephemeral=True
    )
    

# Run the bot with your token
if __name__ == "__main__":
    bot.run(bot_token)
