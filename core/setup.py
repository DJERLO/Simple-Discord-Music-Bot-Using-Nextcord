"""
core/setup.py

This module contains functions for setting up the music system.

Functions
---------
create_node() -> wavelink.Node
    Creates and returns a configured Wavelink node.

recover_lavalink_session(bot: commands.Bot, players: list[wavelink.Player])
    Establish a fresh node and migrate orphaned players to it.

get_diagnostic_message(error: Exception) -> str
    Generates a standardized diagnostic message for the music system.
"""

import os

import wavelink
from nextcord.ext import commands

from core.logging import get_logger

logger = get_logger(__name__)

LAVALINK_URI = os.getenv("LAVALINK_URI", "http://127.0.0.1:2333")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")


def create_node() -> wavelink.Node:
    """
    Creates and returns a configured Wavelink node.

    Returns
    -------
    :class:`wavelink.Node`
        A configured Wavelink node
    """
    return wavelink.Node(
        uri=LAVALINK_URI,
        password=LAVALINK_PASSWORD,
        retries=10,
        heartbeat=60,
    )


async def recover_lavalink_session(bot: commands.Bot, players: list[wavelink.Player]):
    """
    Establish a fresh node and migrate orphaned players to it.

    Attributes
    ----------
    bot : :class:`commands.Bot`
        The bot instance.
    players : list[ :class:`wavelink.Player`]
        The players to migrate.

    Returns
    -------
    None

    """
    connected_node = None
    if wavelink.Pool.nodes:
        connected_node = next(
            (
                node
                for node in wavelink.Pool.nodes.values()
                if node.status == wavelink.NodeStatus.CONNECTED
            ),
            None,
        )

    if connected_node is None:
        new_node = create_node()
        await wavelink.Pool.connect(nodes=[new_node], client=bot)
        connected_node = new_node

    for player in players:
        try:
            await player.switch_node(connected_node)
            logger.info(f"Migrated guild {player.guild.id} to new node.")
        except Exception as e:
            logger.error(f"Migration failed for {player.guild.id}: {e}. Disconnecting.")
            await player.disconnect(force=True)


def get_diagnostic_message(error: Exception) -> str:
    """
    Generates a standardized diagnostic message for the music system.

    Attributes
    ----------
    error : :class:`Exception`
        The error that triggered the diagnostic message.

    Returns
    -------
    str
        The generated diagnostic message.
    """
    nodes = wavelink.Pool.nodes
    connected_node = wavelink.Pool.get_node()

    node_status = (
        f"Nodes Found: {len(nodes)}" if nodes else "No nodes in `CONNECTED` state!"
    )
    status_str = connected_node.status if connected_node else "OFFLINE"

    return (
        "⚠️ **The music system is currently unavailable.**\n"
        f"Error: `{type(error).__name__}`\n"
        f"Diagnostic: `{node_status}`\n"
        f"Node Status: `{status_str}`\n"
        "Please report this to the support team."
    )
