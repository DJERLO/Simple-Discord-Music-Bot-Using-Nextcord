# Simple Discord Music Bot Using Nextcord

[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Python Support](https://img.shields.io/badge/python-3.12%20--%203.14-blue.svg)](https://www.python.org/)
[![Documentation](https://img.shields.io/badge/docs-Mintlify-24b47e?style=flat&logo=bookstack&logoColor=white)](https://mintlify.wiki/DJERLO/Simple-Discord-Music-Bot-Using-Nextcord/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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

## Quickstart: Run the Simple Discord Music Bot Locally

Clone the repo, install dependencies, start Lavalink via Docker, and play your first song in Discord — all in under ten minutes.

### 📋 Prerequisites

Make sure the following are installed and available in your system terminal before continuing:

* **Python 3.12 to 3.14** — Older versions of Python (like 3.10 or lower) will cause the bot to crash on startup.
* **Docker & Docker Compose** — Required to run the local Lavalink audio node container.
* **Git** — Used to clone the project files to your machine.
* **Discord Bot Token** — You need to create an application and bot user inside the [Discord Developer Portal](https://discord.com/developers/applications), then copy your secret token from the **Bot** settings tab.

---

## ⚡ Getting Started

### 1. Clone the Repository

Clone the project from GitHub and navigate into the project directory:
```bash
git clone https://github.com/DJERLO/Simple-Discord-Music-Bot-Using-Nextcord.git

cd Simple-Discord-Music-Bot-Using-Nextcord
```

### 2. Configure Environment Variables

Create a file named .env in the root directory of the project and add your secret token as shown below:

```bash
BOT_TOKEN=your_discord_bot_token_here
```
> [!WARNING]
> Never commit the .env file to version control. It is already listed in .gitignore for your protection — do not remove it from that list.

How to get your token:
1. Go to the [ Discord Developer Portal](https://discord.com/developers/applications).
2. Select your application (or create one) and open the Bot tab
3. Click Reset Token to reveal a fresh token, then copy it immediately
4. Paste it into your .env file as shown below

### 3. Lavalink Server (Docker)

The bot streams audio through Lavalink, which runs as a Docker container. Start it in the background with:

```bash
docker-compose up -d
```

This pulls the official [ghcr.io/lavalink-devs/lavalink:4.2.2](ghcr.io/lavalink-devs/lavalink:4.2.2) image, mounts your local application.yml as its configuration file, and exposes port 2333 so the bot can connect. The unless-stopped restart policy means Lavalink will come back up automatically after a system reboot.

Confirm it is running:
```bash
docker ps
```

You should see a container named lavalink_node with status Up.

### 4. Python Environment
Install the necessary dependencies:
```bash
pip install -r requirements.txt
```
*This installs the following core packages:*

| **Package**           | **Purpose**                                                |
|-----------------------|-------------------------------------------------------------|
| **nextcord**          | Discord API wrapper for Python                              |
| **nextcord\[voice\]** | Adds voice connection support to Nextcord                   |
| **python\-dotenv**    | Loads environment variables from \.env                      |
| **wavelink**          | Async Lavalink client for audio control                     |
| **pytest**            | Test runner for the project’s test suite                    |
| **pytest\-asyncio**   | Async support for pytest \(used by Discord command tests\)  |
| **pytest\-watch**     | File watcher that re\-runs tests on save                    |
-------------------------------------------------------
> [!TIP]
> During development, run ptw (pytest-watch) instead of pytest. It watches your source files and automatically re-runs the test suite every time you save a change — catching regressions the moment they’re introduced.

### 5. Bot Invite & Permissions
To maintain maximum security for self-hosters and public server deployments, this bot follows the **Principle of Least Privilege**. It runs completely on native Slash Commands and does **not** require `Administrator` overrides. 

When generating your bot invite link via the **OAuth2 URL Generator** in the Discord Developer Portal, select the `bot` and `applications.commands` scopes, and check only these **5 essential permissions**:

| Permission           | Category | Reason                                                  |
|----------------------|----------|---------------------------------------------------------|
| Connect              | Voice    | Join voice channels to stream audio                     |
| Speak                | Voice    | Transmit audio through the voice connection             |
| Send Messages        | Text     | Post now-playing embeds and command responses           |
| Embed Links          | Text     | Render rich embeds with artwork and track details       |
| Read Message History | Text     | Allow the bot to edit its own persistent player message |

---
> [!IMPORTANT]
>  You must also enable Message Content Intent in the Discord Developer Portal under your application’s Bot → Privileged Gateway Intents section, otherwise Discord will silently deny the intent and certain bot behaviors may not function correctly.

### 6. Run the Bot
With Lavalink running and your .env file in place, start the bot:

```bash
python bot.py
```
> [!NOTE]
> Lavalink must be running before you start bot.py. The bot connects to the Lavalink node during its on_ready event — if the node is unreachable at startup, the bot will fail to initialize audio playback.

On startup the bot will:
1. Load BOT_TOKEN from .env
2. Connect to the Lavalink node at http://127.0.0.1:2333
3. Sync all slash commands with Discord
4. Log in and display its tag in the terminal

You should see no connection errors in the terminal output if Lavalink is healthy.

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
> [!TIP]
> Run `ptw` in a separate terminal while you work. It monitors all Python files in the project and re-runs the full test suite the moment you save a change, giving you continuous pass/fail feedback without switching windows.

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
## License

This project is licensed under the [MIT License](LICENSE).

---
