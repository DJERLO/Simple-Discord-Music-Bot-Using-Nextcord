"""
core/decorators.py

This module contains custom decorators for Nextcord application commands.

Functions
---------
has_dj_permissions()
    A custom Nextcord application command check decorator.
"""

from functools import wraps

from core.permissions import is_dj


def has_dj_permissions():
    """
    A decorator that checks if the user has the DJ role or Administrator
    permissions.

    Returns:
        A Nextcord application command check decorator.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract the interaction from the arguments
            # (Slash commands pass interaction as the second argument)
            interaction = args[1] if len(args) > 1 else None

            if interaction and not await is_dj(interaction):
                return await interaction.response.send_message(
                    "❌ **Access Denied:** "
                    "You need the **DJ** role or **Administrator** "
                    "permissions to use this command.",
                    ephemeral=True,
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
