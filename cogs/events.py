import asyncio
import logging
import time

import nextcord
import wavelink
from nextcord.ext import commands

from ui.embeds import (
    ACTIVE_PLAYERS,
    AUTO_DISCONNECT_TASKS,
    MESSAGE_DELETE_TIMEOUT,
    VOICE_DISCONNECT_TIMEOUT,
    VOTE_SKIPS,
    create_now_playing_embed,
)

logger = logging.getLogger("MusicBot")


class AudioEvents(commands.Cog):
    """
    Cog dedicated to handling all audio-related events,
    including voice state updates for auto-disconnect logic and
    Wavelink track lifecycle events for dynamic player interface management.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
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
                    """
                    Waits for the specified timeout and disconnects the bot
                    if still alone.

                    This function re-checks the channel state after the sleep to
                    ensure that

                    the bot is still alone before disconnecting, preventing
                    race conditions.
                    """
                    try:
                        await asyncio.sleep(VOICE_DISCONNECT_TIMEOUT)
                        # Re-verify the current state of the voice client
                        current_vc = member.guild.voice_client
                        if (
                            current_vc
                            and current_vc.channel
                            and sum(1 for m in current_vc.channel.members if not m.bot)
                            == 0
                        ):
                            logger.info(
                                f"Inactivity timer expired for guild {guild_id}."
                            )
                            # Clear state data before leaving
                            if hasattr(current_vc, "queue"):
                                current_vc.queue.clear()

                            await self.bot.change_presence(activity=None)

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
                        logger.info(
                            f"Disconnect timer for guild {guild_id} was cancelled."
                        )
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

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """
        Handles the logic for when a new track starts playing,
        including updating the player interface and bot presence.
        """
        player = payload.player
        track = payload.track
        guild_id = str(player.guild.id)
        VOTE_SKIPS[guild_id] = set()  # Reset vote skips for the new track

        embed = create_now_playing_embed(
            player, track, is_persistent=True, bot_user=self.bot.user
        )

        from ui.embeds import format_time

        await self.bot.change_presence(
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

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """
        Handles the logic for when a track finishes playing, including queue management,
        autoplay transitions, and cleanup of the player interface.
        """
        player = payload.player
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

        # 4. Determine the next track to play
        # (checking user queue, then partial auto_queue)
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
                # BUG FIX:
                # auto_queue is empty because it was skipped early or hadn't filled yet!
                logger.info(
                    f"Guild {guild_id}: Auto-queue empty on track end. "
                    f"Force populating recommendations."
                )
                kwargs["populate"] = True
                kwargs["max_populate"] = 5
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
            await self.bot.change_presence(activity=None)


def setup(bot: commands.Bot):
    bot.add_cog(AudioEvents(bot))
