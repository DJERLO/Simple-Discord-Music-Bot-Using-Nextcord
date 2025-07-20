import nextcord
from nextcord import Interaction, Embed, ButtonStyle
from nextcord.ui import View, Button

class QueueView(View):
    """ A view for displaying and navigating through a music queue.
    This view allows users to see the current music queue and navigate through it using buttons.
    It supports pagination, allowing users to view a limited number of songs per page.
    
    Attributes:
        songs (list): The list of songs in the queue.
        per_page (int): The number of songs to display per page.
        page (int): The current page number.
        guild_id (str): The ID of the guild this queue belongs to.
        interaction_user (nextcord.User): The user who initiated the interaction.
    """
    def __init__(self, songs, interaction_user, guild_id, per_page=10):
        super().__init__(timeout=60)
        self.songs = songs
        self.per_page = per_page
        self.page = 0
        self.guild_id = guild_id
        self.interaction_user = interaction_user

    def get_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        queue_slice = self.songs[start:end]

        embed = Embed(
            title=f"🎶 Music Queue (Page {self.page + 1}/{(len(self.songs) - 1) // self.per_page + 1})",
            description="",
            color=nextcord.Color.green()
        )
        for idx, (_, title, *_rest) in enumerate(queue_slice, start=start + 1):
            embed.description += f"**{idx}.** {title}\n"
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.interaction_user.id

    @nextcord.ui.button(label="⬅️ Prev", style=ButtonStyle.primary, row=0)
    async def prev_page(self, button: Button, interaction: Interaction):
        self.page -= 1
        await self.update_buttons_and_embed(interaction)

    @nextcord.ui.button(label="Next ➡️", style=ButtonStyle.primary, row=0)
    async def next_page(self, button: Button, interaction: Interaction):
        self.page += 1
        await self.update_buttons_and_embed(interaction)

    async def update_buttons_and_embed(self, interaction: Interaction):
        max_page = (len(self.songs) - 1) // self.per_page

        # Enable/Disable buttons based on page
        self.children[0].disabled = self.page <= 0
        self.children[1].disabled = self.page >= max_page

        await interaction.response.edit_message(embed=self.get_embed(), view=self)