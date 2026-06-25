# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-06-25 (In Progress)

### Added
- **Loop Modes**: Integrated `loop_all` functionality to the queue system.
- **Slash Options**: Migrated `/play`, `/volume`, `/loop`, and `/remove` commands to structured slash options, improving UI consistency and user experience.
- **Testing**: Expanded the high-fidelity test suite to 67+ cases, achieving 100% logic coverage for audio event lifecycle transitions.

### Changed
- **Loop Logic**: Overhauled `/loop` command from a binary toggle to a multi-mode selection system (None/Track/Queue).
- **Playback Architecture**: Implemented "Autoplay-first" logic, prioritizing native Wavelink event handling and eliminating redundant manual cleanup tasks.
- **UI/UX**: Added state-based color coding to embed generators for improved visual feedback.

### Fixed
- **Duplicate Tracks**: Resolved a critical race condition causing duplicate entries in the queue during `loop_all` transitions.
- **Stability**: Neutralized Wavelink's default inactivity limits (token bucket/track limits) to prevent phantom disconnects during rapid track skips.
- **Voice Logic**: Fixed inactivity timer bugs; the bot now correctly performs live `channel.members` verification (ignoring bots) before enforcing disconnects.
- **Race Conditions**: Resolved `/skip` logic errors where the bot would repeat the previous track instead of loading the next item from the queue.

---

## [1.1.0] - 2026-06-14

### Added
- **Autoplay Engine**: Global per-guild memory registers for persistent user preferences.
- **Navigation**: `/previous` track command and unified history tracking.
- **Governance**: Implemented `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, and standardized repository licensing.
- **Documentation**: Overhauled docs with dedicated guides for VPS deployment, Linting (Ruff), and Testing (Pytest) via Mintlify.
- **Testing**: Scaled test suite to 38 high-fidelity cases with 100% logic verification.

### Changed
- **Architecture**: Modularized codebase from monolith into domain-specific Cogs.
- **Infrastructure**: Integrated parallel multi-version CI pipeline (Python 3.12–3.14-dev) and automated dependency tracking (Dependabot).
- **Security**: Restricted GitHub Action permissions to `contents: read` (Principle of Least Privilege).

### Fixed
- Resolved `/skip` autoplay race conditions and UI "ghost" data issues during channel moves.

---

## [1.0.1] - 2026-06-09

### Changed
- **Security**: Hardened GitHub Action pipeline security.

### Fixed
- **Stability**: Implemented auto-disconnect logic for empty voice channels to prevent bandwidth leakage.
- **Maintenance**: Automated dependency tracking via Dependabot for pip and docker-compose.

---

## [1.0.0-beta.1] - 2026-06-03

### Added
- **Engine Migration**: Shifted audio streaming from local FFmpeg/yt-dlp to Lavalink/Wavelink.
- **CI/CD**: Implemented parallel build matrix and automated Ruff linting pipeline.
- **Testing**: Initialized full asynchronous unit test suite using pytest.

---

## [0.1.0] - 2025-07-21

### Added
- Initial project foundation (Music bot prototype).
- Basic song playback notifications.