import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from collections import deque
import nextcord

# Import the bot and view modules
import bot
from views import QueueView

class TestMusicBot(unittest.IsolatedAsyncioTestCase):
    """
    Unit tests for the Music Bot functionality, mocking Discord interactions.
    """

    def setUp(self):
        # Mocking basic song data: (url, title, thumbnail, duration)
        self.songs = [
            ("https://link1.com", "Song Alpha", None, 125),
            ("https://link2.com", "Song Beta", None, 300),
            ("https://link3.com", "Song Gamma", None, 45)
        ]
        self.mock_user = MagicMock(spec=nextcord.User)
        self.mock_user.id = 12345
        self.mock_user.display_name = "TestUser"
        self.mock_user.avatar = None
        self.guild_id = "987654321"

    async def test_queue_view_pagination_logic(self):
        """Tests that the QueueView correctly calculates pages and button states."""
        # Page size 2, 3 songs total -> 2 pages
        view = QueueView(self.songs, self.mock_user, self.guild_id, per_page=2)
        
        # Page 0 (First page)
        self.assertTrue(view.prev_page.disabled, "Previous button should be disabled on page 1")
        self.assertFalse(view.next_page.disabled, "Next button should be enabled on page 1")
        
        embed = view.get_embed()
        self.assertIn("Song Alpha", embed.description)
        self.assertIn("Song Beta", embed.description)
        self.assertNotIn("Song Gamma", embed.description)
        self.assertEqual(embed.footer.text, "Total Songs: 3")

    async def test_skip_command_playing(self):
        """Tests the /skip command when music is playing."""
        interaction = AsyncMock(spec=nextcord.Interaction)
        interaction.response.send_message = AsyncMock()
        interaction.guild.voice_client.is_playing.return_value = True
        interaction.guild.voice_client.is_paused.return_value = False
        
        # Access the callback of the slash command directly
        await bot.skip.callback(interaction)
        
        interaction.guild.voice_client.stop.assert_called_once()
        interaction.response.send_message.assert_called_with("Skipped the current song.", ephemeral=True)

    async def test_pause_command_success(self):
        """Tests the /pause command when music is playing."""
        interaction = AsyncMock(spec=nextcord.Interaction)
        interaction.response.send_message = AsyncMock()
        interaction.guild.voice_client.is_playing.return_value = True
        
        await bot.pause.callback(interaction)
        
        interaction.guild.voice_client.pause.assert_called_once()
        interaction.response.send_message.assert_called_with("Playback paused!", ephemeral=True)

    async def test_clearqueue_command(self):
        """Tests the /clearqueue command resets the queue for the guild."""
        interaction = AsyncMock(spec=nextcord.Interaction)
        interaction.response.send_message = AsyncMock()
        interaction.guild_id = self.guild_id
        
        # Populate global dictionary
        bot.SONG_QUEUES[self.guild_id] = deque(self.songs)
        
        await bot.clearqueue.callback(interaction)
        
        self.assertEqual(len(bot.SONG_QUEUES[self.guild_id]), 0)
        interaction.response.send_message.assert_called_with("The music queue has been cleared.", ephemeral=True)

    async def test_ping_command(self):
        """Tests the /ping command returns latency."""
        interaction = AsyncMock(spec=nextcord.Interaction)
        interaction.response.send_message = AsyncMock()
        with patch("nextcord.Client.latency", new_callable=PropertyMock) as mock_latency:
            mock_latency.return_value = 0.05  # 50ms
            await bot.ping.callback(interaction)
            interaction.response.send_message.assert_called_with("Pong! Latency: 50ms", ephemeral=True)

if __name__ == '__main__':
    unittest.main()