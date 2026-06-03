# Simple Discord Music Bot Using Nextcord

A high-performance Discord music bot built with [Nextcord](https://github.com/nextcord/nextcord) and [Wavelink](https://github.com/PythonistaGuild/Wavelink). 
This bot leverages **Lavalink** for industry-standard audio processing, ensuring stability and low resource usage.

This project was heavily inspired by [CreepyD](https://www.youtube.com/watch?v=U5CUkxUh2CQ), who made a similar bot using [discord.py](https://github.com/Rapptz/discord.py) in Python.
For my version, I used **Nextcord** as the main Discord API wrapper.

---

## Features

* **Lavalink Powered:** Offloads audio decoding and streaming to a dedicated Java node for crystal clear audio.
* **Dynamic UI:** Displays interactive "Now Playing" rich embeds that automatically clean up when playback stops.
* **Paginated Navigation:** View deep music tracks using an organized, session-locked pagination view.
* **Automated Presence:** Synchronizes the bot's status with the current track, including live timestamps.

---

## ⚡ Prerequisites & Setup

### 1. Lavalink Server (Docker)
This bot requires a Lavalink node. We use Docker to manage this easily.
```bash
docker-compose up -d
```
*Note: Local FFmpeg binaries are no longer required as Lavalink handles audio processing internally.*

### 2. Python Environment
Install the necessary dependencies:
```bash
pip install -r requirements.txt
```

---

## 🧪 Testing & Development

We maintain high code quality using `pytest`. We've implemented a "watchdog" system to ensure that new changes don't break the bot's core functionality.

### Running Tests
Run the test suite once:
```bash
pytest
```

### Development Watchdog
To prevent breaking the bot during active development, use `pytest-watch`. This will monitor your files and automatically re-run tests every time you save a change:
```bash
ptw
```

This workflow ensures that:
1. **Pytest** validates logic.
2. **Pytest-Asyncio** handles our asynchronous Discord commands.
3. **Pytest-Watch** catches bugs the moment they are written.

---

## Slash Commands

* `/play <song>` — Searches and plays a song or adds it to the queue.
* `/nowplaying` — Displays detailed information about the current track.
* `/skip` — Skips the track currently active in the channel.
* `/pause` — Pauses current audio playback.
* `/resume` — Resumes paused music tracking.
* `/queue` — Launches a paginated interactive embed panel to browse the active song queue.
* `/shuffle` — Shuffles the current music queue.
* `/clearqueue` — Clears all songs from the current queue.
* `/stop` — Safely halts active audio, clears internal arrays, and cleanly drops voice server gateway connections.
* `/ping` — Checks the bot's latency.
* `/help` — Shows available commands and usage.

---

## Usage

Run the bot with:

```bash
python bot.py
```
## License

This project is licensed under the [MIT License](LICENSE).

---
