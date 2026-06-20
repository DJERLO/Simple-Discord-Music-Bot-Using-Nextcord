import os

import wavelink

from core.logging import get_logger

logger = get_logger(__name__)

LAVALINK_URI = os.getenv("LAVALINK_URI", "http://127.0.0.1:2333")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")


def create_node() -> wavelink.Node:
    """Creates and returns a configured Wavelink node."""
    return wavelink.Node(
        uri=LAVALINK_URI,
        password=LAVALINK_PASSWORD,
        retries=10,
        heartbeat=60,
    )


async def recover_lavalink_session(bot, players: list):
    """
    Establish a fresh node and migrate orphaned players to it.
    """

    if wavelink.Pool.nodes:
        # If we already have nodes, don't keep spamming connections
        if any(
            n.status == wavelink.NodeStatus.CONNECTED
            for n in wavelink.Pool.nodes.values()
        ):
            logger.info("Node already exists and is healthy. Skipping recovery.")
            return

    new_node = create_node()
    await wavelink.Pool.connect(nodes=[new_node], client=bot)

    for player in players:
        try:
            await player.switch_node(new_node)
            logger.info(f"Migrated guild {player.guild.id} to new node.")
        except Exception as e:
            logger.error(f"Migration failed for {player.guild.id}: {e}. Disconnecting.")
            await player.disconnect(force=True)


def get_diagnostic_message(error: Exception) -> str:
    """Generates a standardized diagnostic message for the music system."""
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
