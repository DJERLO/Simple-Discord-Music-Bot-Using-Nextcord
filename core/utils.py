"""
core/utils.py

This module contains helper functions for the music system.

Functions
---------
get_tracks(vc: wavelink.Player) -> list[wavelink.Playable]
    Helper function to get the current queue and auto-queue tracks

shuffle_queue(vc: wavelink.Player) -> None
    Helper function to shuffle the queue including
    the recommended tracks (auto-queue) if AutoPlay is enabled

clear_queue(vc: wavelink.Player) -> None
    Resets the queue and auto-queue to empty

repeat_queue(vc: wavelink.Player, button: nextcord.ui.Button | None) -> None
    Helper function to toggle loop modes
"""

import random

import nextcord
import wavelink


async def get_tracks(vc: wavelink.Player) -> list[wavelink.Playable]:
    """
    Helper function to get the current queue and auto-queue tracks

    Parameters
    ----------
    vc : :class:`wavelink.Player`:
        The voice client of the guild

    Returns
    -------
    list[wavelink.Playable]
        The current queue and auto-queue tracks
    """
    from ui import embeds

    songs = [
        (track.uri, track.title, embeds.get_track_artwork(track), track.length / 1000)
        for track in vc.queue
    ]

    # Append auto-queue tracks if enabled
    if vc.autoplay == wavelink.AutoPlayMode.enabled:
        songs.extend(
            [
                (
                    track.uri,
                    f"✨ {track.title} (Auto-Queue)",
                    embeds.get_track_artwork(track),
                    track.length / 1000,
                )
                for track in list(vc.auto_queue)[:10]
            ]
        )

    return songs


async def shuffle_queue(vc: wavelink.Player) -> None:
    """
    Helper function to shuffle the queue including
    the recommended tracks (auto-queue) if AutoPlay is enabled

    Parameters
    ----------
    vc : :class:`wavelink.Player`:
        The voice client of the guild
    """
    if not vc.queue.is_empty:
        vc.queue.shuffle()

    if not vc.auto_queue.is_empty:
        auto_tracks = list(vc.auto_queue)

        random.shuffle(auto_tracks)

        vc.auto_queue.clear()
        for track in auto_tracks:
            vc.auto_queue.put(track)


async def clear_queue(vc: wavelink.Player) -> None:
    """
    Resets the queue and auto-queue to empty

    Parameters
    ----------
    vc : :class:`wavelink.Player`:
        The voice client of the guild
    """
    track = list(vc.auto_queue)

    if not vc.queue.is_empty:
        vc.queue.clear()

    if not vc.auto_queue.is_empty:
        vc.auto_queue.clear()

    if track and vc.autoplay.enabled:
        vc.auto_queue.put(track[0])


def repeat_queue(vc: wavelink.Player, button: nextcord.ui.Button | None) -> None:
    """
    Helper function to toggle loop modes

    Toggles between Normal, loop, and loop_all

    Parameters
    ----------
    vc : :class:`wavelink.Player`:
        The voice client of the guild
    """
    if vc.queue.mode == wavelink.QueueMode.loop:
        # Move to Queue Loop
        vc.queue.mode = wavelink.QueueMode.loop_all
        if button:
            button.emoji = "🔁"
            button.style = nextcord.ButtonStyle.primary
    elif vc.queue.mode == wavelink.QueueMode.normal:
        # Move to Track Loop
        vc.queue.mode = wavelink.QueueMode.loop
        if button:
            button.emoji = "🔂"
            button.style = nextcord.ButtonStyle.primary
    else:
        # Move to Normal
        vc.queue.mode = wavelink.QueueMode.normal
        if button:
            button.emoji = "🔂"
            button.style = nextcord.ButtonStyle.secondary
