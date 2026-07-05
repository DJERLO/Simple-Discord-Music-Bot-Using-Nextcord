"""
ui/views.py
-----------
A view for displaying and navigating through a music queue.
This view allows users to see the current music queue and
navigate through it using buttons.
It supports pagination, allowing users to view
a limited number of songs per page.

Origin:
- Author: Jerlo De Leon
- Date: 2026-06-30

This module defines the QueueView class, which subclasses
nextcord.ui.View.

The QueueView class is responsible for displaying the music queue
and allowing users to navigate through it using buttons.
It supports pagination, allowing users to view a limited number
of songs per page.

The QueueView class has the following attributes:
- songs: The list of songs in the queue.
- per_page: The number of songs to display per page.
- page: The current page number.
- guild_id: The ID of the guild this queue belongs to.
- interaction_user: The user who initiated the interaction.

The QueueView class has the following methods:
- get_embed: Returns the embed object for the current page of the queue.
- update_button_states: Updates the state of the pagination buttons.
- next_page: Navigates to the next page of the queue.
- prev_page: Navigates to the previous page of the queue.
- interaction_check: Checks if the interaction
is from the user who initiated the interaction.
- on_timeout: Disables the buttons after the timeout.

The HelpView class is a subclass of nextcord.ui.View that
displays and navigates through a list of commands.

The HelpView class has the following attributes:
- all_commands: The list of commands to display.
- page_size: The number of commands to display per page.
- page: The current page number.
- current_page: The current page number.
- max_pages: The maximum number of pages.

The HelpView class has the following methods:
- create_embed: Returns the embed object for the current page of commands.
- update_button_states: Updates the state of the pagination buttons.
- prev_button: Navigates to the previous page of commands.
- next_button: Navigates to the next page of commands.
"""

import inspect

import nextcord
from nextcord import ButtonStyle, Embed, Interaction
from nextcord.ext import commands
from nextcord.ui import Button, View


class QueueView(View):
    """
    A view for displaying and navigating through a music queue.
    This view allows users to see the current music queue and
    navigate through it using buttons.
    It supports pagination, allowing users to view
    a limited number of songs per page.

    Attributes:
    ----------
        songs (list): The list of songs in the queue.
        per_page (int): The number of songs to display per page.
        page (int): The current page number.
        guild_id (str): The ID of the guild this queue belongs to.
        interaction_user (nextcord.User): The user who initiated the interaction.
        message (nextcord.Message): The message containing the queue view.
        update_button_states(self): Updates the state of the pagination buttons.

    Methods:
    -------
        get_embed(self): Returns the embed object for the current page of the queue.
        update_button_states(self): Updates the state of the pagination buttons.
        next_page(self, button, interaction): Navigates to the next page of the queue.
        prev_page(self, button, interaction):
        Navigates to the previous page of the queue.
        interaction_check(self, interaction):
        Checks if the interaction is from the user who initiated the interaction.
        on_timeout(self): Disables the buttons after the timeout.
    """

    def __init__(self, songs, interaction_user, guild_id, per_page=10):
        super().__init__(timeout=60)
        self.songs = songs
        self.per_page = per_page
        self.page = 0
        self.guild_id = guild_id
        self.interaction_user = interaction_user
        # Store a reference to the view's message container for later editing
        self.message = None
        self.update_button_states()

    def get_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        queue_slice = self.songs[start:end]
        max_pages = max(1, (len(self.songs) - 1) // self.per_page + 1)

        embed = Embed(
            title=f"🎶 Music Queue (Page {self.page + 1}/{max_pages})",
            description="",
            color=nextcord.Color.green(),
        )

        if not queue_slice:
            embed.description = "*No items on this page.*"
            return embed

        for idx, (_, title, _, duration) in enumerate(queue_slice, start=start + 1):
            time_str = (
                f" ({int(duration // 60)}:{int(duration % 60):02d})" if duration else ""
            )
            embed.description += f"**{idx}.** {title}{time_str}\n"

        embed.set_footer(text=f"Total Songs: {len(self.songs)}")
        return embed

    def update_button_states(self):
        max_page = max(0, (len(self.songs) - 1) // self.per_page)
        self.prev_page.disabled = self.page <= 0
        self.next_page.disabled = self.page >= max_page

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.interaction_user.id:
            await interaction.response.send_message(
                "Only the user who requested the queue menu can look through pages.",
                ephemeral=True,
            )
            return False
        return True

    @nextcord.ui.button(label="⬅️ Prev", style=ButtonStyle.primary, row=0)
    async def prev_page(self, button: Button, interaction: Interaction):
        self.page -= 1
        self.update_button_states()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @nextcord.ui.button(label="Next ➡️", style=ButtonStyle.primary, row=0)
    async def next_page(self, button: Button, interaction: Interaction):
        self.page += 1
        self.update_button_states()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def on_timeout(self):
        # Visually gray out interaction buttons on the server when the menu expires
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class HelpView(View):
    """
    A view for displaying and navigating through a list of commands.

    Attributes:
    ----------
        all_commands (list): The list of commands to display.
        page_size (int): The number of commands to display per page.
        page (int): The current page number.
        current_page (int): The current page number.
        max_pages (int): The maximum number of pages.

    Methods:
    -------
        create_embed(self): Returns the embed object for the current page of commands.
        update_button_states(self): Updates the state of the pagination buttons.
        prev_button(self, button, interaction): Navigates to the previous page of
        commands.
        next_button(self, button, interaction): Navigates to the next page of commands.
    """

    def __init__(self, all_commands: list, bot: None | commands.Bot, page_size=5):
        super().__init__(timeout=60)
        self.all_commands = list(all_commands)
        self.bot = bot
        self.page = 0
        self.page_size = page_size
        self.current_page = 0
        self.max_pages = (len(self.all_commands) - 1) // page_size
        self.update_button_states()

    def create_embed(self):
        start = self.current_page * self.page_size
        end = start + self.page_size
        embed = nextcord.Embed(
            title="Bot Help Index",
            description="Use the buttons below to navigate through the commands.",
            color=0xFC0404,
        )

        embed.set_thumbnail(url=self.bot.user.avatar.url)

        for cmd in self.all_commands[start:end]:
            desc = inspect.cleandoc(cmd.callback.__doc__ or "No description").split(
                "\n"
            )[0]
            embed.add_field(name=f"/{cmd.name}", value=desc, inline=False)

        embed.set_footer(text=f"Page {self.current_page + 1} / {self.max_pages + 1}")
        return embed

    def update_button_states(self):
        max_page = self.max_pages
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= max_page

    @nextcord.ui.button(label="Previous", style=nextcord.ButtonStyle.secondary)
    async def prev_button(
        self, button: nextcord.ui.Button, interaction: nextcord.Interaction
    ):
        self.page -= 1
        self.current_page = self.page
        self.update_button_states()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @nextcord.ui.button(label="Next", style=nextcord.ButtonStyle.secondary)
    async def next_button(
        self, button: nextcord.ui.Button, interaction: nextcord.Interaction
    ):
        self.page += 1
        self.current_page = self.page
        self.update_button_states()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
