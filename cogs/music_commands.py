import asyncio
import logging

import nextcord
import wavelink
from nextcord import Interaction, SlashOption
from nextcord.ext import commands

from core.decorators import has_dj_permissions
from ui.embeds import (
    ACTIVE_PLAYERS,
    AUTO_DISCONNECT_TASKS,
    GUILD_AUTOPLAY_MODES,
    MESSAGE_DELETE_TIMEOUT,
    create_now_playing_embed,
    format_time,
    get_track_artwork,
    update_player_message,
)
from ui.views import QueueView as QueueSongList

logger = logging.getLogger("MusicBot")


class WavelinkPlayer(wavelink.Player, nextcord.VoiceProtocol):
    """
    Custom player class that inherits from
    Wavelink's Player and Nextcord's VoiceProtocol.
    """

    pass


class MusicCommands(commands.Cog):
    """
    Cog that contains all slash commands related to music playback,
    queue management, and player controls. This cog also includes a listener
    for application command errors to handle permission issues gracefully.

    **Commands**:
    - **/play**: Play a song or add it to the queue.
    - **/queue**: Show the current music queue.
    - **/nowplaying**: Show details of the currently playing song.
    - **/ping**: Check the bot's latency.
    - **/help**: Show available commands and usage.
    - **/join**: Make the bot join your voice channel.
    - **/clearqueue**: Clear the current music queue.
    - **/shuffle**: Shuffle the current music queue.
    - **/skip**: Skips the current playing song (DJ Only).
    - **/pause**: Pause the currently playing song (DJ Only).
    - **/resume**: Resume the currently paused song (DJ Only).
    - **/remove**: Remove a specific track from the queue by its position (DJ Only).
    - **/stop**: Stop playback and clear the queue (DJ Only).
    - **/volume**: Set the playback volume (0-100) (DJ Only).
    - **/loop**: Toggle looping of the current track (DJ Only).
    - **/autoplay**: Set autoplay mode for continuous music (DJ Only).
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ================= GENERAL COMMAND DECK =================

    @nextcord.slash_command(
        name="play", description="Play a song or add it to the queue."
    )
    async def play(self, interaction: Interaction, song: str):
        """
        Handles the /play command, allowing users to play a song or add it to the queue.
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
            vc.autoplay = GUILD_AUTOPLAY_MODES.get(
                str(interaction.guild_id), wavelink.AutoPlayMode.disabled
            )
        elif voice_channel != vc.channel:
            guild_id = str(interaction.guild_id)

            # Clean up the old player interface before moving to a new channel
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
                    await task
                except asyncio.CancelledError:
                    pass
                vc.queue.clear()
                if vc.playing or vc.paused:
                    vc.ignore_next_cleanup = True
                    await vc.stop()

            try:
                await vc.move_to(voice_channel)
            except Exception:
                try:
                    await vc.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting from voice channel: {e}")
                    pass
                vc = await voice_channel.connect(cls=WavelinkPlayer)

        try:
            tracks = await wavelink.Playable.search(song)
        except wavelink.exceptions.LavalinkLoadException:
            logger.warning(f"Unsupported source or invalid query: {song}")
            await interaction.followup.send(
                "**Unsupported Source:** Currently, this bot only supports "
                "direct YouTube, YouTubeMusic and SoundCloud searches or URLs. "
                "Please provide a valid YouTube or SoundCloud link, or a search term.",
                ephemeral=True,
                delete_after=MESSAGE_DELETE_TIMEOUT,
            )
            return

        if not tracks:
            await interaction.followup.send(
                "No results found.", ephemeral=True, delete_after=MESSAGE_DELETE_TIMEOUT
            )
            return

        extras = {
            "requester": interaction.user.display_name,
            "avatar": interaction.user.avatar.url if interaction.user.avatar else None,
        }

        if isinstance(tracks, wavelink.Playlist):
            for track in tracks:
                track.extras = extras
            await vc.queue.put_wait(tracks)
            message = (
                f"Added playlist **{tracks.name}** ({len(tracks)} tracks) to queue."
            )
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
            text=f"Requested by {interaction.user.display_name}",
            icon_url=extras["avatar"],
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

    @nextcord.slash_command(name="queue", description="Show the current music queue.")
    async def queue(self, interaction: Interaction):
        """
        Handles the /queue command, allowing users to view the
        current music queue and autoplay list.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message(
                "I'm not in a voice channel.", ephemeral=True
            )

        songs_list = []
        for track in vc.queue:
            songs_list.append(
                (track.uri, track.title, get_track_artwork(track), track.length / 1000)
            )

        if vc.autoplay == wavelink.AutoPlayMode.partial and not vc.auto_queue.is_empty:
            for track in list(vc.auto_queue)[:5]:
                songs_list.append(
                    (
                        track.uri,
                        f"✨ {track.title} (Auto-Queue)",
                        get_track_artwork(track),
                        track.length / 1000,
                    )
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

    @nextcord.slash_command(
        name="nowplaying", description="Show details of the currently playing song."
    )
    async def nowplaying(self, interaction: Interaction):
        """
        Handles the /nowplaying command, providing users
        with details about the currently playing track.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        if not vc or not vc.playing:
            return await interaction.response.send_message(
                "Nothing is currently playing.", ephemeral=True
            )

        track = vc.current
        embed = create_now_playing_embed(
            vc, track, is_persistent=False, bot_user=self.bot.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @nextcord.slash_command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: Interaction):
        """Handles the /ping command, allowing users to check the bot's latency."""
        latency_ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"Pong! Latency: {latency_ms}ms", ephemeral=True
        )

    @nextcord.slash_command(
        name="help", description="Show available commands and usage."
    )
    async def help_command(self, interaction: Interaction):
        """QA: Render a line-length safe, explicitly structured help manual."""
        help_text = (
            "**General Commands:**\n"
            "/join - Make the bot join your voice channel.\n"
            "/play [song name or URL] - Play a song or add it to the queue.\n"
            "/queue - Show the current music queue.\n"
            "/nowplaying - Show details of the currently playing song.\n"
            "/shuffle - Shuffle the current music queue.\n"
            "/ping - Check the bot's latency.\n"
            "/help - Show this help message.\n"
            "/voteskip - Vote to skip the current song "
            "(requires 50% majority of listeners).\n\n"
            "**DJ Only Commands:**\n"
            "/volume - Set the playback volume (0-100). (DJ Only)\n"
            "/loop - Toggle looping of the current track. (DJ Only)\n"
            "/autoplay <mode> - Set autoplay mode for continuous music. "
            "(DJ Only)\n"
            "/skip - Skip the currently playing song. (DJ Only)\n"
            "/pause - Pause the currently playing song. (DJ Only)\n"
            "/resume - Resume the currently paused song. (DJ Only)\n"
            "/stop - Stop playback and clear the queue. (DJ Only)\n"
            "/clearqueue - Clear the current music queue. (DJ Only)\n"
            "/remove [position] - Remove a specific track from the queue. "
            "(DJ Only)\n"
        )
        await interaction.response.send_message(help_text, ephemeral=True)

    @nextcord.slash_command(
        name="join", description="Make the bot join your voice channel."
    )
    async def join(self, interaction: Interaction):
        """Handles the /join command, pulling the bot and its UI panels safely."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "You must be in a voice channel to use this command.",
                ephemeral=True,
                delete_after=MESSAGE_DELETE_TIMEOUT,
            )
            return

        voice_channel = interaction.user.voice.channel
        vc: WavelinkPlayer = interaction.guild.voice_client
        guild_id = str(interaction.guild_id)

        if vc and vc.channel == voice_channel:
            await interaction.response.send_message(
                "I'm already in your voice channel.", ephemeral=True
            )
            return

        elif vc and vc.channel != voice_channel:
            # 1. Clean up the old persistent dashboard message from the old channel
            old_msg = ACTIVE_PLAYERS.get(guild_id)
            if old_msg:
                try:
                    await old_msg.delete()
                except Exception:
                    pass
                ACTIVE_PLAYERS[guild_id] = None

            # 2. Shift the connection over to the new channel location cleanly
            await vc.move_to(voice_channel)

            # 3. Drop a fresh now-playing UI panel right where the user just ran /join
            if vc.playing or vc.paused:
                current_track = vc.current
                if current_track:
                    # Construct a pristine visual embed card
                    embed = create_now_playing_embed(
                        vc, current_track, is_persistent=True, bot_user=self.bot.user
                    )
                    
                    # Send it fresh into the new text channel
                    new_msg = await interaction.channel.send(embed=embed)
                    
                    # Re-cache the newly generated message reference globally
                    ACTIVE_PLAYERS[guild_id] = new_msg
        else:
            vc = await voice_channel.connect(cls=WavelinkPlayer)
            vc.autoplay = GUILD_AUTOPLAY_MODES.get(
                guild_id, wavelink.AutoPlayMode.disabled
            )

        await interaction.response.send_message(
            f"Joined **{voice_channel.name}**!", ephemeral=True
        )

    @nextcord.slash_command(
        name="clearqueue", description="Clear the current music queue."
    )
    @has_dj_permissions()
    async def clearqueue(self, interaction: Interaction):
        """
        Handles the /clearqueue command,
        allowing users to clear the current music queue.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        if vc:
            vc.queue.clear()
        await interaction.response.send_message(
            "The music queue has been cleared.", ephemeral=True
        )

    @nextcord.slash_command(
        name="shuffle", description="Shuffle the current music queue."
    )
    async def shuffle(self, interaction: Interaction):
        """
        Handles the /shuffle command,
        allowing users to shuffle the current music queue.
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

    @nextcord.slash_command(
        name="voteskip", description="Vote to skip the current song."
    )
    async def voteskip(self, interaction: Interaction):
        """
        Handles the /voteskip command, allowing users to vote to skip the current song.
        Requires a 50% majority of human members listening in the voice channel.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client

        # 1. Verification: Is the bot active?
        if not vc or not (vc.playing or vc.paused):
            return await interaction.response.send_message(
                "Not playing anything to skip.", ephemeral=True
            )

        # 2. Verification: Is the user in the same voice channel as the bot?
        if not interaction.user.voice or interaction.user.voice.channel != vc.channel:
            return await interaction.response.send_message(
                "You must be in my voice channel to vote to skip.", ephemeral=True
            )

        guild_id = str(interaction.guild_id)
        user_id = interaction.user.id

        # 3. Initialize the vote set for this guild if it doesn't exist
        from ui.embeds import VOTE_SKIPS

        if guild_id not in VOTE_SKIPS:
            VOTE_SKIPS[guild_id] = set()

        # 4. Check for double voting
        if user_id in VOTE_SKIPS[guild_id]:
            return await interaction.response.send_message(
                "You have already voted to skip this song.", ephemeral=True
            )

        # 5. Register the user's vote
        VOTE_SKIPS[guild_id].add(user_id)
        current_votes = len(VOTE_SKIPS[guild_id])

        # 6. Dynamically count active human listeners (excluding bots)
        listeners = [member for member in vc.channel.members if not member.bot]
        total_listeners = len(listeners)

        # 7. Calculate required votes (50% majority, rounded up using integer division)
        # Formula: (total // 2) + 1 guarantees a strict majority threshold
        required_votes = (total_listeners // 2) + 1

        # Edge case bypass: If the user is the only listener, let them skip immediately
        if total_listeners <= 1:
            await vc.skip()
            return await interaction.response.send_message(
                "⏩ You are the only listener. Skipping track immediately!",
                ephemeral=True,
            )

        # 8. Evaluate threshold criteria
        if current_votes >= required_votes:
            await vc.skip()
            # Clear the vote tracking set immediately upon successful skip execution
            VOTE_SKIPS[guild_id] = set()
            await interaction.response.send_message(
                f"⏩ **Vote passed!** ({current_votes}/{total_listeners} votes). "
                f"Skipping to the next track!",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"🗳️ **Vote registered!** Your vote has been added. "
                f"({current_votes}/{required_votes} votes required to skip).",
                ephemeral=True,
            )

    # ================= DJ ONLY COMMAND DECK =================

    @nextcord.slash_command(name="skip", description="Skips the current playing song")
    @has_dj_permissions()
    async def skip(self, interaction: Interaction):
        """
        Handles the /skip command, allowing DJs to skip the currently playing song.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        if vc and (vc.playing or vc.paused):
            await vc.skip()
            await interaction.response.send_message(
                "Skipped the current song.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Not playing anything to skip.", ephemeral=True
            )

    @nextcord.slash_command(
        name="pause", description="Pause the currently playing song."
    )
    @has_dj_permissions()
    async def pause(self, interaction: Interaction):
        """
        Handles the /pause command, allowing DJs to pause the currently playing song.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        if vc is None:
            return await interaction.response.send_message(
                "I'm not in a voice channel.", ephemeral=True
            )
        if not vc.playing:
            return await interaction.response.send_message(
                "Nothing is currently playing.", ephemeral=True
            )

        await vc.pause(True)
        await interaction.response.send_message("Playback paused!", ephemeral=True)

    @nextcord.slash_command(
        name="resume", description="Resume the currently paused song."
    )
    @has_dj_permissions()
    async def resume(self, interaction: Interaction):
        """
        Handles the /resume command, allowing DJs to resume the currently paused song.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        if vc is None:
            return await interaction.response.send_message(
                "I'm not in a voice channel.", ephemeral=True
            )
        if not vc.paused:
            return await interaction.response.send_message(
                "I’m not paused right now.", ephemeral=True
            )

        await vc.pause(False)
        await interaction.response.send_message("Playback resumed!", ephemeral=True)

    @nextcord.slash_command(
        name="stop", description="Stop playback and clear the queue."
    )
    @has_dj_permissions()
    async def stop(self, interaction: Interaction):
        """
        Handles the /stop command, allowing DJs to stop playback and clear the queue.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message(
                "I'm not connected to any voice channel.", ephemeral=True
            )

        guild_id_str = str(interaction.guild_id)
        vc.queue.clear()

        if guild_id_str in ACTIVE_PLAYERS:
            try:
                await ACTIVE_PLAYERS[guild_id_str].delete()
            except Exception:
                pass
            ACTIVE_PLAYERS[guild_id_str] = None

        await vc.disconnect()
        await self.bot.change_presence(activity=None)
        await interaction.response.send_message(
            "Stopped playback and disconnected", ephemeral=True
        )

    @nextcord.slash_command(
        name="volume", description="Set the playback volume (0-100)."
    )
    @has_dj_permissions()
    async def volume(self, interaction: Interaction, value: int):
        """
        Handles the /volume command, allowing DJs to set the playback volume.
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
        await update_player_message(vc, bot_user=self.bot.user)
        await interaction.response.send_message(
            f"Volume set to {value}%.", ephemeral=True
        )

    @nextcord.slash_command(
        name="loop", description="Toggle looping of the current track."
    )
    @has_dj_permissions()
    async def loop(self, interaction: Interaction):
        """
        Handles the /loop command, allowing DJs to toggle looping of the current track.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        if not vc or not vc.playing:
            return await interaction.response.send_message(
                "Nothing is currently playing to loop.", ephemeral=True
            )

        vc.loop = not getattr(vc, "loop", False)
        status = "enabled" if vc.loop else "disabled"
        await update_player_message(vc, bot_user=self.bot.user)
        await interaction.response.send_message(
            f"Looping {status} for the current track.", ephemeral=True
        )

    @nextcord.slash_command(
        name="autoplay", description="Set autoplay mode for continuous music."
    )
    @has_dj_permissions()
    async def autoplay(
        self,
        interaction: Interaction,
        mode: str = SlashOption(
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
        Handles the /autoplay command,
        allowing DJs to set the autoplay mode for continuous music playback.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        mode_map = {
            "enabled": wavelink.AutoPlayMode.enabled,
            "partial": wavelink.AutoPlayMode.partial,
            "disabled": wavelink.AutoPlayMode.disabled,
        }
        if not vc:
            # Store the preference even if not connected, but inform the user
            GUILD_AUTOPLAY_MODES[str(interaction.guild_id)] = mode_map[mode]
            return await interaction.response.send_message(
                "I'm not connected to any voice channel. Autoplay preference saved.",
                ephemeral=True,
            )

        mode_map = {
            "enabled": wavelink.AutoPlayMode.enabled,
            "partial": wavelink.AutoPlayMode.partial,
            "disabled": wavelink.AutoPlayMode.disabled,
        }

        GUILD_AUTOPLAY_MODES[str(interaction.guild_id)] = mode_map[mode]

        if vc:
            vc.autoplay = mode_map[mode]
            await update_player_message(vc, bot_user=self.bot.user)

        await interaction.response.send_message(
            f"Autoplay mode has been set to: **{mode.capitalize()}**", ephemeral=True
        )

    @nextcord.slash_command(
        name="remove",
        description="Remove a specific track from the queue. (DJ Only)",
    )
    @has_dj_permissions()
    async def remove(self, interaction: Interaction, position: int):
        """
        Handles the /remove command, allowing DJs to remove a specific track
        from either the regular queue or the automated recommendations queue.
        """
        vc: WavelinkPlayer = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message(
                "I'm not connected to any voice channel.", ephemeral=True
            )

        # 1. Gather sizes from both containers safely
        regular_queue_len = len(vc.queue)
        auto_queue_list = list(vc.auto_queue) if hasattr(vc, "auto_queue") else []
        auto_queue_len = len(auto_queue_list)

        total_len = regular_queue_len + auto_queue_len

        if total_len == 0:
            return await interaction.response.send_message(
                "The music queue is currently empty.", ephemeral=True
            )

        # 2. Boundary bounds validation check (1-indexed)
        if position < 1 or position > total_len:
            return await interaction.response.send_message(
                f"Invalid position. "
                f"Please choose a track number between 1 and {total_len}.",
                ephemeral=True,
            )

        target_index = position - 1

        # 3. CASE A: Target falls cleanly inside the regular queue tracking list
        if target_index < regular_queue_len:
            removed_track = vc.queue[target_index]
            del vc.queue[target_index]
            queue_type = "Regular Queue"

        # 4. CASE B: Target points past regular queue items into the auto-queue
        else:
            auto_index = target_index - regular_queue_len
            removed_track = auto_queue_list[auto_index]

            # Reconstruct the auto_queue cleanly
            # without modifying it dynamically mid-loop
            updated_tracks = []
            removed_flag = False

            for track in auto_queue_list:
                # FIX: Match by .identifier to guarantee safe container filtering
                if track.identifier == removed_track.identifier and not removed_flag:
                    removed_flag = True  # Skips putting this specific track back
                    continue
                updated_tracks.append(track)

            # Clear old references completely and rebuild the state synchronously
            vc.auto_queue.clear()
            for track in updated_tracks:
                vc.auto_queue.put(track)

            queue_type = "Auto-Queue (Autoplay)"

        # 5. Dynamic visual UI updates to avoid text panel drift
        await update_player_message(vc, bot_user=self.bot.user)

        await interaction.response.send_message(
            f"🗑️ Removed track: **{removed_track.title}** "
            f"from position `{position}` ({queue_type}).",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: Interaction, error):
        """
        Captures decorator permission errors and displays them
        to the user in a user-friendly manner without terminal clutter.
        """
        # FIX: Look for nextcord.ApplicationCheckFailure instead of application_checks
        if isinstance(error, nextcord.ApplicationCheckFailure):
            if not interaction.response.is_done():
                await interaction.response.send_message(str(error), ephemeral=True)
            else:
                await interaction.followup.send(str(error), ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(MusicCommands(bot))
