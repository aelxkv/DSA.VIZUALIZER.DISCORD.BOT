# Changelog

Format: [Keep a Changelog](https://keepachangelog.com). Versions follow [SemVer](https://semver.org).

## [2.0.0-alpha.1] - 2026-11-11

First milestone of 2.0 (the rest of 2.0: `/ds`, hashing lab, memory lab).

### Added
- `/help`: overview, per-category pages, per-command pages and reference topics (algorithms, limits, colors, FAQ). Option tables are generated from the real command definitions, so they cannot go stale. Private by default (`public:true` to share). 3 s cooldown.
- `/about`: description, version, uptime, servers, library versions, invite/support buttons.
- `/stats`: runs, top algorithms, commands used. The bot owner also gets health details (memory, render time, errors) privately.
- Rotating bot status (version, algorithm count, run count, `/help`).
- Complexity line (time, space, stable, in-place) in every run summary.
- Invite button (built from the bot's own ID) and optional support button (`SUPPORT_URL`).
- Every user-facing error now ends with `Need help? /help command:<name>`.
- Activity counters saved to a JSON file (`STATS_PATH`). Counts only: no user names, messages or inputs.
- Golden-file test: run lines written by v1.0.0 must keep working with `/step`.

### Changed
- The bot now needs the **Embed Links** permission (invite permission number is `309237763072`). Existing servers: grant it to the bot's role.

## [1.0.0] - 2026-11-10

### Added
- `/visualize` for 14 algorithms (7 sorts, 2 searches, BFS, DFS, 3 tree traversals) with GIF, thread, numbered step log.
- `/step` to render any single step of a run from the thread's first message (no database).
