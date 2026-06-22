import time

import nextcord
import wavelink
from nextcord.ext import commands

from cogs.music_commands import WavelinkPlayer
from core.logging import get_logger
from core.setup import recover_lavalink_session
from ui.embeds import (
    ACTIVE_PLAYERS,
    AUTO_DISCONNECT_TASKS,
    MESSAGE_DELETE_TIMEOUT,
    VOTE_SKIPS,
    create_now_playing_embed,
)

logger = get_logger(__name__)


class AudioEvents(commands.Cog):
    """
    Cog dedicated to handling all audio-related events,
    including voice state updates for auto-disconnect logic and
    Wavelink track lifecycle events for dynamic player interface management.

    Attributes
    ----------
    bot : Instance of :class:`nextcord.ext.commands.Bot`
        The main bot instance.
    inactive_timeout : int
        The number of seconds to wait before automatically disconnecting
        from an inactive voice channel.
    inactive_channel_tokens : int
        The number of songs to play before automatically disconnecting
        from an inactive voice channel.

    Methods
    -------
    on_voice_state_update (member, before, after) :
        Handles voice state updates for auto-disconnect logic.
    on_wavelink_track_start(payload):
        Handles the logic for when a new track starts playing.
    on_wavelink_track_end(payload):
        Handles the logic for when a track finishes playing.
    on_wavelink_track_stuck(payload):
        Handles tracks that fail to play, preventing the player
        from hanging indefinitely in the voice channel.
    on_wavelink_track_exception(payload):
        Handles tracks that encounter exceptions during playback.
    on_wavelink_websocket_closed(payload):
        Called when the websocket to the voice server is closed.
    on_wavelink_node_ready(payload):
        Called when the Node you are connecting to has initialised and successfully
        connected to Lavalink.
    on_wavelink_node_closed(node, disconnected):
        Called when a node has been closed and cleaned up.
    on_wavelink_node_disconnected(payload):
        Called when the playerUpdate OP is received from Lavalink.
    on_wavelink_stats_update(payload):
        Called when the stats OP is received by Lavalink.
    on_wavelink_inactive_player(player):
        - Triggered when the inactive_timeout countdown expires or
        - Triggered when the inactive_channel_tokens limit is reached to 0.
    on_wavelink_player_update(payload):
        Called when the playerUpdate OP is received from Lavalink.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.inactive_timeout = 300
        self.inactive_channel_tokens = 3

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: nextcord.Member,
        before: nextcord.VoiceState,
        after: nextcord.VoiceState,
    ):
        """
        Monitors voice channel activity to manage the Wavelink player's
        inactivity timeout.

        This listener automatically triggers when a member joins
        or leaves a voice channel.
        It adjusts the 'inactive_timeout' property of the WavelinkPlayer
        to ensure the bot disconnects automatically when the channel
        is empty, and cancels any pending disconnection
        if a human joins the channel.

        Attributes
        ----------
        member : nextcord.Member
            The member whose voice state changed.
        before : nextcord.VoiceState
            The voice state of the member prior to the change.
        after : nextcord.VoiceState
            The voice state of the member after the change.
        """
        if member.id == self.bot.user.id:
            return

        vc: WavelinkPlayer = member.guild.voice_client

        if not vc or not vc.channel:
            return

        # 2. Check if a human joined the bot's channel
        if after.channel == vc.channel and before.channel != vc.channel:
            # HUMAN JOINED: Cancel the timeout immediately
            vc.inactive_timeout = None
            vc.inactive_channel_tokens = None
            logger.info(f"Human joined {vc.channel.name}. Inactivity timer cancelled.")

        # 3. Check if a human left the bot's channel
        elif before.channel == vc.channel and after.channel != vc.channel:
            human_members = [m for m in vc.channel.members if not m.bot]

            # If the channel is now empty: Start the timeout
            if not human_members:
                vc.inactive_timeout = self.inactive_timeout
                vc.inactive_channel_tokens = self.inactive_channel_tokens
                logger.info(
                    f"Channel {vc.channel.name} emptied. "
                    f"Inactivity timer set to {self.inactive_timeout}."
                )

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """
        Handles the logic for when a new track starts playing,
        including updating the player interface and bot presence.

        Attributes
        ----------
        payload : :class:`wavelink.TrackStartEventPayload`
            See Also: :class:`wavelink.TrackStartEventPayload`
        """
        player = payload.player
        track: wavelink.Playable = payload.track
        guild_id = str(player.guild.id)
        VOTE_SKIPS[guild_id] = set()  # Reset vote skips for the new track
        embed = create_now_playing_embed(
            player, track, is_persistent=True, bot_user=self.bot.user
        )

        # Put all songs to history to allow history playback
        player.queue.history.put(track)
        logger.info(f"Now Playing: {track.title} by {track.author}")

        activity = nextcord.Activity(
            application_id=self.bot.user.id,
            type=nextcord.ActivityType.listening,
            name=f"{track.title}",
            state=f"{track.author}",
            timestamps={
                "start": int(time.time()),
                "end": int(time.time() + (track.length // 1000)),
            },
        )

        await self.bot.change_presence(
            activity=activity,
            status=nextcord.Status.online,
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

        Attributes
        ----------
        payload : :class:`wavelink.TrackEndEventPayload`
            See Also: :class:`wavelink.TrackEndEventPayload`
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
        next_track = None
        kwargs = {}

        # If autoplay is enabled, just play the next track from the auto-queue.
        if player.autoplay == wavelink.AutoPlayMode.enabled:
            logger.info(
                f"Guild {guild_id}: playing next track from auto-queue.\n"
                f"Current track: {payload.track.title} by {payload.track.author}"
            )
            return

        # If autoplay is disabled, check if the queue is empty.
        if player.autoplay == wavelink.AutoPlayMode.disabled:
            # If the queue is empty, set the inactivity timeout
            if player.queue.is_empty:
                logger.info(f"Queue empty in guild {guild_id}. Player is now idling.")
                logger.info(
                    f"No songs left in queue. "
                    f"Inactivity timer set to {self.inactive_timeout}."
                )
                player.inactive_timeout = self.inactive_timeout
                await self.bot.change_presence(
                    activity=None, status=nextcord.Status.idle
                )

                msg = ACTIVE_PLAYERS.get(guild_id)
                if msg:
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                    ACTIVE_PLAYERS[guild_id] = None

                return
            # If the queue is not empty, play the next track
            if not player.queue.is_empty:
                next_track = player.queue.get()
                kwargs["populate"] = True
                kwargs["max_populate"] = 10
                logger.info(f"Playing next track: {next_track.title}")
                await player.play(next_track, **kwargs)
                return

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload):
        """
        Handles tracks that fail to play, preventing the player
        from hanging indefinitely in the voice channel.

        Atributes
        ---------
        payload : :class:`wavelink.TrackStuckEventPayload`
            See Also: :class:`wavelink.TrackStuckEventPayload`
        """
        player = payload.player
        logger.warning(
            f"Track {payload.track.title} stuck in guild {player.guild.id}. "
            f"Threshold: {payload.threshold}ms"
        )

        # Action: Immediately skip the stuck track to keep the music flowing
        try:
            await player.skip()
        except Exception as e:
            logger.error(f"Failed to auto-skip stuck track: {e}")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(
        self, payload: wavelink.TrackExceptionEventPayload
    ):
        """
        Handles tracks that encounter exceptions during playback, ensuring the player
        doesn't get stuck and provides feedback on the issue.

        Attributes
        ----------
        payload : :class:`wavelink.TrackExceptionEventPayload`
            See Also: :class:`wavelink.TrackExceptionEventPayload`
        """
        logger.error(f"Track {payload.track.title} failed: {payload.exception.message}")
        await payload.player.skip()

    @commands.Cog.listener()
    async def on_wavelink_websocket_closed(
        self, payload: wavelink.WebsocketClosedEventPayload
    ):
        """
        Called when the websocket to the voice server is closed.
        """
        code = payload.code.value if hasattr(payload.code, "value") else payload.code

        # 1. Check for intentional "Normal" closures (1000)
        if code == 1000:
            logger.info("WebSocket closed normally.")
            return

        # 2. Log others
        log_message = (
            f"Voice WebSocket Closed | Code: {payload.code} | Reason: {payload.reason}"
        )

        # Now this won't trigger for the 1000/CLOSE_NORMAL case
        if code in [4006, 4014]:
            logger.warning(log_message)
        else:
            logger.error(f"CRITICAL: {log_message}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(
        self, payload: wavelink.NodeReadyEventPayload
    ) -> None:
        """
        Called when the Node you are connecting to has initialised and successfully
        connected to Lavalink.
        This event can be called many times throughout your bots lifetime,
        as it will be called when Wavelink successfully reconnects to your node
        in the event of a disconnect.

        Payload received in the :func:`on_wavelink_node_ready` event.

        Attributes
        ----------
        payload : :class:`wavelink.NodeReadyEventPayload`
            See Also: :class:`wavelink.NodeReadyEventPayload`
        """
        logger.info(f"Lavalink {payload.node!r} is back online and ready!")

    @commands.Cog.listener()
    async def on_wavelink_node_disconnected(
        self,
        payload: wavelink.NodeDisconnectedEventPayload,
    ):
        """
        Called when the playerUpdate OP is received from Lavalink.
        This event contains information about a specific connected player on the node.

        The default behaviour is for wavelink to attempt
        to reconnect a disconnected Node.

        This event can change that behaviour.

        If you want to close this node completely see: Node.close()

        This event can be used to manage
        the currrently connected players to this Node. See: Player.switch_node()

        Payload received in the :func:`on_wavelink_node_disconnected` event.

        Attributes
        ----------
        payload : :class:`wavelink.NodeDisconnectedEventPayload`
            See Also: :class:`wavelink.NodeDisconnectedEventPayload`
        """
        logger.info(f"{payload.node} is disconnected")

    @commands.Cog.listener()
    async def on_wavelink_node_closed(
        self, node: wavelink.Node, disconnected: list[wavelink.Player]
    ):
        """
        Called when a node has been closed and cleaned up.

        Attributes
        ----------
        node : :class:`wavelink.Node`
            See Also: :class:`wavelink.Node`
        disconnected : list[ :class:`wavelink.Player`]
            See Also: list[ :class:`wavelink.Player`]
        """
        # 1. Log the failure for infrastructure monitoring

        logger.info(f"Node {node.identifier} closed.")
        await recover_lavalink_session(self.bot, disconnected)

    @commands.Cog.listener()
    async def on_wavelink_stats_update(self, payload: wavelink.StatsEventPayload):
        """
        Called when the stats OP is received by Lavalink.
        Payload received in the :func:`on_wavelink_stats_update` event.

        Attributes
        ----------
        payload : :class:`wavelink.StatsEventPayload`
            See Also: :class:`wavelink.StatsEventPayload`
        """
        logger.debug(
            "Lavalink Stats Update "
            f"| Players: {payload.players} "
            f"| Playing: {payload.playing} "
            f"| Uptime: {payload.uptime}ms "
            f"| Memory: {payload.memory} "
            f"| CPU: {payload.cpu} "
            f"| Frames: {payload.frames}"
        )

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: WavelinkPlayer):
        """
        Triggered when the inactive_timeout countdown expires for the specific Player.

        Attributes
        ----------
        player : :class:`wavelink.Player`
            See Also: :class:`wavelink.Player`
        """
        guild_id = str(player.guild.id)
        logger.info(
            f"Guild {player.guild.id} timed out after {player.inactive_timeout}s."
        )

        # 1. Clean up active player message/dashboard if it exists
        player_msg = ACTIVE_PLAYERS.get(guild_id)
        if player_msg:
            try:
                await player_msg.delete()
            except Exception:
                pass
            ACTIVE_PLAYERS.pop(guild_id, None)

        # 2. Clear state, queue, and auto_queue
        player.queue.clear()
        if hasattr(player, "auto_queue"):
            player.auto_queue.clear()

        # 3. Send goodbye message to the voice channel's text chat
        try:
            if player.channel:
                channel_name = player.channel.name
                human_count = sum(1 for m in player.channel.members if not m.bot)
                if human_count == 0:
                    msg_text = (
                        f"I've left **{channel_name}** because "
                        "it's been empty for too long."
                    )
                else:
                    msg_text = (
                        f"I've left **{channel_name}** because "
                        "it's been inactive for too long."
                    )

                await player.channel.send(
                    msg_text,
                    delete_after=MESSAGE_DELETE_TIMEOUT,
                )
        except Exception as e:
            logger.error(f"Error sending inactivity leave message: {e}")

        # 4. Cancel any pending custom empty-channel task
        task = AUTO_DISCONNECT_TASKS.pop(guild_id, None)
        if task:
            task.cancel()

        # 5. Disconnect and clear presence
        try:
            await player.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting player: {e}")

        await self.bot.change_presence(activity=None)

    @commands.Cog.listener()
    async def on_wavelink_player_update(
        self, payload: wavelink.PlayerUpdateEventPayload
    ):
        """
        Called when the playerUpdate OP is received from Lavalink.
        This event contains information about a specific connected player on the node.

        Payload received in the :func:`on_wavelink_player_update` event.

        Attributes
        ----------
        payload : :class:`wavelink.PlayerUpdateEventPayload`
            See Also: :class:`wavelink.PlayerUpdateEventPayload`
        """
        logger.debug(
            f"Lavalink Player Update | "
            f"Player: {payload.player} | "
            f"Time: {payload.time} | "
            f"Position: {payload.position} | "
            f"Connected: {payload.connected} | "
            f"Ping: {payload.ping}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(AudioEvents(bot))
