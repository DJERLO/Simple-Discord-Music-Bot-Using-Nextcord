"""
ui/embeds.py
Embeds for the music bot

This module provides functions for generating and updating embeds for the music bot.

Origin:
- Author: Jerlo De Leon
- Date: 2026-06-30

Global Variables:
-----------------
- ACTIVE_PLAYERS: A dictionary to track active players, keyed by guild ID.
- GUILD_AUTOPLAY_MODES: A dictionary to track autoplay modes, keyed by guild ID.
- VOTE_SKIPS: A dictionary to track vote skips, keyed by guild ID.
- MESSAGE_DELETE_TIMEOUT: The timeout for message deletion in seconds.

Functions:
- format_time(ms): Formats milliseconds into M:SS.
- get_track_artwork(track): Retrieves the best available artwork for a track.
- create_now_playing_embed(player, track, is_persistent=True):
Creates an embed for the Now Playing message.
- update_player_message(player, track, is_persistent=True):
Updates the player message with the current track.
- cleanup_player_message(player): Cleans up the player message after a track ends.
"""

import nextcord
import wavelink

from ui.views import PlaybackView

# Central Global Tracking States
ACTIVE_PLAYERS = {}
GUILD_AUTOPLAY_MODES = {}
VOTE_SKIPS = {}
MESSAGE_DELETE_TIMEOUT = 60.0  # 1 minute in seconds


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


def create_now_playing_embed(
    player: wavelink.Player,
    track: wavelink.Playable,
    is_persistent: bool = True,
    bot_user=None,
) -> nextcord.Embed:
    """
    Centralized helper to create the Now Playing embed for events and commands.
    If is_persistent is True, the embed is styled for the main player message with a
    larger image. If False, it's styled for ephemeral updates (like pause/resume)
    with a thumbnail.

    Arguments
    ---------
    player : wavelink.Player
        The player object for the guild.
    track : wavelink.Playable
        The track currently playing in the player.
    is_persistent : bool, optional
        Whether the embed should be styled for the main player message.
    bot_user : nextcord.User, optional
        The bot's user object.

    Returns
    -------
    nextcord.Embed
        The Now Playing embed.
    """

    if player.paused:
        color = nextcord.Color.orange()
    else:
        color = nextcord.Color.green()

    embed = nextcord.Embed(
        title="💿 Now Playing" if is_persistent else "💿 Currently Playing",
        description=f"[{track.title}]({track.uri})",
        color=color if is_persistent else nextcord.Color.blue(),
    )

    embed.add_field(name="Artist", value=track.author, inline=True)

    album_name = getattr(track, "album", None)
    if album_name and hasattr(album_name, "name") and album_name.name:
        embed.add_field(name="Album", value=album_name.name, inline=True)

    embed.add_field(name="Duration", value=format_time(track.length), inline=True)

    # Status Indicators
    loop_states = {
        wavelink.QueueMode.normal: "➡️ Normal",
        wavelink.QueueMode.loop: " 1️⃣ Track",
        wavelink.QueueMode.loop_all: "🔁 Queue",
    }
    autoplay_mode = player.autoplay
    ap_label = {
        wavelink.AutoPlayMode.enabled: "✅ Enabled",
        wavelink.AutoPlayMode.disabled: "❌ Disabled",
    }.get(autoplay_mode, "Unknown")

    embed.add_field(name="Volume", value=f"{player.volume}%", inline=True)
    embed.add_field(
        name="Looping",
        value=loop_states.get(player.queue.mode, "➡️ Normal"),
        inline=True,
    )
    embed.add_field(name="Autoplay", value=ap_label, inline=True)

    artwork = get_track_artwork(track)
    if artwork:
        if is_persistent:
            embed.set_image(url=artwork)
        else:
            embed.set_thumbnail(url=artwork)

    requester = getattr(track.extras, "requester", "Autoplay")
    avatar = getattr(track.extras, "avatar", None)
    if requester == "Autoplay" and not avatar and bot_user:
        avatar = bot_user.avatar.url if bot_user.avatar else None

    footer_text = f"Requested by {requester}"
    if is_persistent:
        footer_text += " | In Voice Channel"

    embed.set_footer(text=footer_text, icon_url=avatar)
    return embed


async def send_player_now_playing(player: wavelink.Player, bot_user=None):
    """
    Creates and sends the main player message in the channel.

    Arguments
    ---------
    player : wavelink.Player
        The player object for the guild.
    bot_user : nextcord.User, optional
        The bot's user object.
    """
    guild_id = str(player.guild.id)
    embed = create_now_playing_embed(
        player, player.current, is_persistent=True, bot_user=bot_user
    )

    view = PlaybackView(player=wavelink.Player, bot_user=bot_user)
    # Check if we are already tracking a message for this guild
    msg = ACTIVE_PLAYERS.get(guild_id)

    if msg:
        try:
            await msg.edit(embed=embed, view=view)
            return msg  # Successfully updated existing
        except (nextcord.NotFound, nextcord.HTTPException):
            # Message was deleted or inaccessible, fall through to send new
            pass

    # Send new if no existing message or edit failed
    new_msg = await player.channel.send(embed=embed, view=view)
    ACTIVE_PLAYERS[guild_id] = new_msg
    return new_msg


async def update_player_message(player: wavelink.Player, bot_user=None):
    """
    Updates the existing persistent player message
    in the channel with current state.
    This is used for events like pause/resume/seek where the track doesn't change
    but the status indicators do.

    Arguments
    ---------
    player : wavelink.Player
        The player object for the guild.
    bot_user : nextcord.User, optional
        The bot's user object.
    """
    guild_id = str(player.guild.id)
    msg = ACTIVE_PLAYERS.get(guild_id)
    if msg and player.current:
        embed = create_now_playing_embed(
            player, player.current, is_persistent=True, bot_user=bot_user
        )
        try:
            await msg.edit(embed=embed)
        except Exception:
            pass


async def cleanup_player_message(player: wavelink.Player):
    """
    Cleans up the existing persistent player message
    in the channel.

    Arguments
    ---------
    player : wavelink.Player
        The player object for the guild.
    """
    guild_id = str(player.guild.id)
    try:
        msg = ACTIVE_PLAYERS.get(guild_id)
        if msg:
            try:
                await msg.delete()
            except Exception:
                pass
            ACTIVE_PLAYERS[guild_id] = None
    except Exception:
        ACTIVE_PLAYERS[guild_id] = None


async def refresh_player_message(
    player: wavelink.Player, channel: nextcord.TextChannel, bot_user=None
):
    """
    Centralized helper to clean up the old dashboard and send a new one
    in a specific channel.

    Arguments
    ---------
    player : wavelink.Player
        The player object for the guild.
    channel : nextcord.TextChannel
        The channel to send the message in.
    bot_user : nextcord.User, optional
        The bot's user object.

    Returns
    -------
    nextcord.Message
        The new message sent.
    """
    guild_id = str(player.guild.id)

    # 1. Clean up old one
    await cleanup_player_message(player)

    # 2. Create fresh embed
    embed = create_now_playing_embed(
        player, player.current, is_persistent=True, bot_user=bot_user
    )

    # 3. Send and track
    new_msg = await channel.send(embed=embed)
    ACTIVE_PLAYERS[guild_id] = new_msg
    return new_msg
