# Documentation project instructions

## About this project
- This is the documentation site for **Simple-Discord-Music-Bot-Using-Nextcord**.
- Architecture: Modular, cog-based structure.
- Pages are MDX files with YAML frontmatter.
- Configuration lives in `docs.json`.

## Terminology
- Use "module" or "cog" when referring to bot functionality sections.
- Use "bot" or "application" when referring to the codebase.
- Use "user" when referring to Discord members.
- Use "workspace" when referring to the local development environment.

## Style preferences
- Use active voice and second person ("you").
- Keep sentences concise — one idea per sentence.
- Use sentence case for headings.
- Bold for UI elements: Click **Settings**.
- Code formatting for file names, commands, paths, and code references[cite: 3].
- Strictly avoid marketing language ("seamless", "powerful") and filler phrases ("it's important to note")[cite: 2].

## Content boundaries
- Document all user-facing commands, setup instructions, and contribution guidelines.
- Do not document experimental internal logic or temporary debug snippets.
- Ensure all environment variables are documented in `docs/setup/environment-variables.mdx`.
- Ensure all testing procedures are documented in `docs/development/testing.mdx`.

## Workflow
- Always verify changes with `mint validate` and `mint broken-links`.
- Ensure new pages are added to the navigation in `docs.json`.
- Always consult the Mintlify skill for component syntax.