import os
import asyncio
import time
from dotenv import load_dotenv 
import nextcord
from nextcord.ext import commands
from nextcord import Interaction
import yt_dlp
from collections import deque
from views import QueueView as QueueSongList

# Load variables from the .env file
load_dotenv()
bot_token = os.getenv('BOT_TOKEN')

# Function to search for a song using yt-dlp
async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)

# Set up the bot with the necessary intents
intents = nextcord.Intents.default()
intents.message_content = True  # Enables the message content intent

bot = commands.Bot(command_prefix='/', intents=intents)

# Create the structure for queueing songs - Dictionary of queues
SONG_QUEUES = {}
# Track the active music player message per guild
ACTIVE_PLAYERS = {}

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    print('Syncing slash commands...')
    await bot.sync_application_commands()
    print('Slash commands synced.')

# Slash Command to skip the current song
@bot.slash_command(name="skip", description="Skips the current playing song")
async def skip(interaction: Interaction):
    """
    Skips the currently playing song in the voice channel. 
    If no song is playing, it informs the user.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped the current song.", ephemeral=True)
    else:
        await interaction.response.send_message("Not playing anything to skip.")

# Slash Command to pause the currently playing song
@bot.slash_command(name="pause", description="Pause the currently playing song.")
async def pause(interaction: Interaction):
    """
    Pauses the currently playing song in the voice channel.
    If no song is playing, it informs the user.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None    
    """
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)

    # Check if something is actually playing
    if not voice_client.is_playing():
        return await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)
    
    # Pause the track
    voice_client.pause()
    await interaction.response.send_message("Playback paused!", ephemeral=True)

# Slash Command to resume the currently paused song
@bot.slash_command(name="resume", description="Resume the currently paused song.")
async def resume(interaction: Interaction):
    """
    Resumes the currently paused song in the voice channel.
    If no song is paused, it informs the user.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)

    # Check if it's actually paused
    if not voice_client.is_paused():
        return await interaction.response.send_message("I’m not paused right now.", ephemeral=True)
    
    # Resume playback
    voice_client.resume()
    await interaction.response.send_message("Playback resumed!", ephemeral=True)

# Slash Command to stop playback and clear the queue
@bot.slash_command(name="stop", description="Stop playback and clear the queue.")
async def stop(interaction: Interaction):
    """
    Stops playback and clears the queue for the current guild.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    voice_client = interaction.guild.voice_client

    if not voice_client or not voice_client.is_connected():
        return await interaction.response.send_message("I'm not connected to any voice channel.", ephemeral=True)

    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    # Dynamic Cleanup of Persistent Voice Channel Embed Interface
    if guild_id_str in ACTIVE_PLAYERS and ACTIVE_PLAYERS[guild_id_str]:
        try:
            await ACTIVE_PLAYERS[guild_id_str].delete()
        except Exception:
            pass
        ACTIVE_PLAYERS[guild_id_str] = None

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    await voice_client.disconnect()
    await bot.change_presence(activity=None)
    await interaction.response.send_message("Stopped playback and disconnected", ephemeral=True)

@bot.slash_command(name="play", description="Play a song or add it to the queue.")
async def play(interaction: Interaction, song_query: str):
    """
    Plays a song or adds it to the queue.
    Args:
        interaction (Interaction): The interaction object from the slash command.
        song_query (str): The song to play or add to the queue.
    returns:
        None
    """
    await interaction.response.defer()

    guild_id = str(interaction.guild_id)

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You must be in a voice channel.", ephemeral=True)
        return

    voice_channel = interaction.user.voice.channel
    user = interaction.user
    voice_client = interaction.guild.voice_client 

    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    # Base configuration options for yt-dlp
    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "quiet": True,                
        "no_warnings": True,          
        "logtostderr": False,         
        "ignoreerrors": True,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
    }

    # Evaluate input pattern: URL vs Search Keywords
    is_url = song_query.startswith("http://") or song_query.startswith("https://")
    is_playlist = "youtube.com/playlist" in song_query or "&list=" in song_query
    
    if is_playlist:
        ydl_options["extract_flat"] = "in_playlist"
        query = song_query  
    elif is_url:
        query = song_query
    else:
        query = f"ytsearch1:{song_query}"  

    results = await search_ytdlp_async(query, ydl_options)
    
    if not results:
        await interaction.followup.send("No results found.", ephemeral=True, delete_after=5.0)
        return

    # Handle multi-source structural formatting differences
    if "entries" in results:
        tracks = [t for t in results["entries"] if t is not None]
    else:
        tracks = [results]

    if not tracks:
        await interaction.followup.send("No playable items found.", ephemeral=True, delete_after=5.0)
        return
    
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

    for track in tracks:
        video_url = track.get("webpage_url") or track.get("url") or (f"https://www.youtube.com/watch?v={track.get('id')}" if track.get('id') else song_query)
        title = track.get("title", "Untitled Track")
        thumbnail = track.get("thumbnail")
        duration = track.get("duration")

        SONG_QUEUES[guild_id].append((video_url, title, thumbnail, duration))

    if voice_client.is_playing() or voice_client.is_paused():
        first_track = tracks[0]
        embed = nextcord.Embed(
            title="Added to Queue",
            description=(
                f"Added a playlist with **{len(tracks)}** tracks." if len(tracks) > 1 
                else f"**{first_track.get('title', 'Untitled Track')}**"
            ),
            color=nextcord.Color.orange()
        )
        if first_track.get("thumbnail"):
            embed.set_image(url=first_track.get("thumbnail"))
        embed.set_footer(
            text=f"Requested by {interaction.user.display_name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send(f"Processing playback...", ephemeral=True, delete_after=2.0)
        await play_next_song(voice_client, guild_id, interaction.channel, user)


async def play_next_song(voice_client, guild_id, channel, user):
    """
    Plays the next song in the queue for the specified guild. 
    If the queue is empty, 
    it disconnects the bot and clears the presence.

    Args:
        voice_client (nextcord.VoiceClient): The voice client connected to the guild.
        guild_id (str): The ID of the guild.
        channel (nextcord.TextChannel): The text channel to send updates to.
        user (nextcord.User): The user who requested the song.

    Returns:
        None
    """
    if guild_id in SONG_QUEUES and SONG_QUEUES[guild_id]:
        video_url, title, thumbnail, duration = SONG_QUEUES[guild_id].popleft()

        ydl_options = {
            "format": "bestaudio[abr<=96]/bestaudio",
            "quiet": True,
            "no_warnings": True,
        }
        
        try:
            track_info = await search_ytdlp_async(video_url, ydl_options)
            if "entries" in track_info and track_info["entries"]:
                track_info = track_info["entries"][0]
            
            audio_url = track_info.get("url")
            webpage_url = track_info.get("webpage_url", video_url)

            if not thumbnail:
                thumbnail = track_info.get("thumbnail")
            if not duration:
                duration = track_info.get("duration")
        except Exception as e:
            print(f"Error extracting {title}: {e}")
            asyncio.create_task(channel.send(f"Could not play **{title}**, skipping...", delete_after=5.0))
            await play_next_song(voice_client, guild_id, channel, user)
            return

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 96k", 
        }

        ffmpeg_path = os.path.join("bin", "ffmpeg", "ffmpeg.exe")
        source = nextcord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable=ffmpeg_path)

        # Gateway-safe Presence Mapping
        is_valid_stream_domain = any(domain in webpage_url for domain in ["youtube.com", "youtu.be", "twitch.tv"])
        presence_url = webpage_url if is_valid_stream_domain else "https://www.youtube.com"

        await bot.change_presence(
            activity=nextcord.Streaming(
                name=title,
                url=str(presence_url),
                platform="Twitch" if "twitch.tv" in webpage_url else "YouTube"
            ),
            status=nextcord.Status.online
        )

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel, user), bot.loop)

        if voice_client and voice_client.is_connected():
            voice_client.play(source, after=after_play)
        else:
            return
        
        embed = nextcord.Embed(
            title="💿 Now Playing",
            description=f"[{title}]({webpage_url})",
            color=nextcord.Color.green()
        )
        if thumbnail:
            embed.set_image(url=thumbnail)
        embed.set_footer(
            text=f"Requested by {user.display_name} | In Voice Channel",
            icon_url=user.avatar.url if user.avatar else None
        )

        v_channel = voice_client.channel

        try:
            if guild_id in ACTIVE_PLAYERS and ACTIVE_PLAYERS[guild_id]:
                try:
                    await ACTIVE_PLAYERS[guild_id].edit(embed=embed)
                except Exception:
                    ACTIVE_PLAYERS[guild_id] = await v_channel.send(embed=embed)
            else:
                ACTIVE_PLAYERS[guild_id] = await v_channel.send(embed=embed)
        except Exception as e:
            print(f"Could not send to voice channel text: {e}")
            if guild_id in ACTIVE_PLAYERS and ACTIVE_PLAYERS[guild_id]:
                try:
                    await ACTIVE_PLAYERS[guild_id].edit(embed=embed)
                except Exception:
                    ACTIVE_PLAYERS[guild_id] = await channel.send(embed=embed)
            else:
                ACTIVE_PLAYERS[guild_id] = await channel.send(embed=embed)

    else:
        if guild_id in ACTIVE_PLAYERS and ACTIVE_PLAYERS[guild_id]:
            try:
                await ACTIVE_PLAYERS[guild_id].delete()
            except Exception:
                pass
            ACTIVE_PLAYERS[guild_id] = None

        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
        await bot.change_presence(activity=None)
        SONG_QUEUES[guild_id] = deque()

@bot.slash_command(name="queue", description="Show the current music queue.")
async def queue(interaction: Interaction):
    """
    Displays the current music queue for the guild in a paginated embed view.
    Only the user who invoked the command can interact with the pagination buttons.
    
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    guild_id = str(interaction.guild_id)
    if guild_id not in SONG_QUEUES or not SONG_QUEUES[guild_id]:
        await interaction.response.send_message("The queue is currently empty.", ephemeral=True)
        return

    songs_list = list(SONG_QUEUES[guild_id])  # Make a copy
    view = QueueSongList(songs_list, interaction.user, guild_id)
    await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)

@bot.slash_command(name="restart", description="Gracefully clean up and restart the bot session (Admin only).")
@commands.has_permissions(administrator=True)
async def restart(interaction: Interaction):
    """
    Gracefully disconnects from voice channels, cleans up data, and restarts the bot script.
    This command is intended for administrators to reset the bot without needing to manually stop and start the script.
    Args:
        interaction (Interaction): The interaction object from the slash command.
    returns:
        None
    """
    await interaction.response.send_message("🔄 Disconnecting from voice channels and restarting system...", ephemeral=True)
    
    guild_id_str = str(interaction.guild_id)
    
    # 1. Clear out internal queue references so memory is flushed
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    # 2. Safely wipe out the persistent music player display message if it exists
    if guild_id_str in ACTIVE_PLAYERS and ACTIVE_PLAYERS[guild_id_str]:
        try:
            await ACTIVE_PLAYERS[guild_id_str].delete()
        except Exception:
            pass
        ACTIVE_PLAYERS[guild_id_str] = None

    # 3. Disconnect cleanly from the voice channel to prevent leaving ghost connections
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_connected():
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        await voice_client.disconnect()

    # 4. Clear streaming presence indicator
    await bot.change_presence(activity=None)

    # 5. Let the background event loops settle for a brief moment before shutting down connection
    await asyncio.sleep(1)
    await bot.close()

    # 6. Re-execute the python script instance using current environment boundaries
    import sys
    os.execv(sys.executable, [sys.executable] + sys.argv)

# Run the bot with your token
bot.run(bot_token)