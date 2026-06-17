# Documentation Overview

This folder contains the Mintlify documentation for the Simple Discord Music Bot project.

## What lives here

- `docs.json` defines the site navigation and theme.
- The `.mdx` pages in this folder describe setup, commands, architecture, and contributor workflows.
- The project-specific docs should stay aligned with the current bot code in `cogs/`, `core/`, and `ui/`.

## Recommended workflow

1. Update the relevant page in `docs/` whenever a command, setting, or workflow changes.
2. Validate docs locally with `npm run docs:validate`.
3. Check links with `npm run docs:links` before opening a pull request.

## Helpful starting points

- `/` for the landing page
- `/quickstart` for local setup
- `/configuration` for environment and Lavalink settings
- `/development/contribution` for contribution guidance

Use the existing Mintlify pages as the source of truth for project documentation, and keep any new content focused on the actual bot behavior rather than repeating the same setup steps in multiple places.
