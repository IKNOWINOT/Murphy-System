# Goldenpath Generator (Self-Contained Bot Folder)
Drop this folder at `src/clockwork/bots/goldenpath_generator/` and add to the registry. No global files required; all shims are local under `internal/`.
Register:
- name: `goldenpath_generator`
- run: `src/clockwork/bots/goldenpath_generator/goldenpath_generator.ts::run`
- ping: `src/clockwork/bots/goldenpath_generator/rollcall.ts::ping`
