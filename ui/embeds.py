import nextcord
import wavelink

# Central Global Tracking States
ACTIVE_PLAYERS = {}
AUTO_DISCONNECT_TASKS = {}
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
    loop_status = "✅ Enabled" if getattr(player, "loop", False) else "❌ Disabled"
    autoplay_mode = player.autoplay
    ap_label = {
        wavelink.AutoPlayMode.enabled: "✅ Full",
        wavelink.AutoPlayMode.partial: "✨ Partial",
        wavelink.AutoPlayMode.disabled: "❌ Disabled",
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
    if requester == "Autoplay" and not avatar and bot_user:
        avatar = bot_user.avatar.url if bot_user.avatar else None

    footer_text = f"Requested by {requester}"
    if is_persistent:
        footer_text += " | In Voice Channel"

    embed.set_footer(text=footer_text, icon_url=avatar)
    return embed


async def update_player_message(player, bot_user=None):
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
