---
name: godot-headless-ci
description: Runs Godot 4 from the command line without the editor UI - importing assets, checking scripts for parse errors, running GUT or gdUnit4 tests, and exporting builds - and sets up GitHub Actions CI that exports Windows, Linux, macOS and Web builds on every push or tag. Use when the user wants automated builds, CI/CD, itch.io or GitHub Releases deployment, headless tests, or asks how to export a Godot game from the terminal.
license: MIT
compatibility: Godot 4.3+ for --import; other commands work on all Godot 4 versions.
metadata:
  author: gamedev-toolkit
  version: "0.1.0"
---

# Godot headless and CI

## Find the binary

`godot` on PATH, otherwise ask the user. Common names: `Godot_v4.x-stable_win64.exe`
(use the `_console.exe` variant on Windows to see output), `godot4`, or
`/Applications/Godot.app/Contents/MacOS/Godot`. Check the version matches the project
(`config/features=PackedStringArray("4.x")` in `project.godot`).

## Core commands

All take `--headless --path <project dir>`.

| Task | Command |
| --- | --- |
| Import all assets (needed on a fresh clone before export or tests) | `godot --headless --path . --import` |
| Load project, then quit (shows script parse errors) | `godot --headless --path . --quit` |
| Check one script | `godot --headless --path . --check-only --script res://player.gd` |
| Run a scene for N frames | `godot --headless --path . res://scenes/test.tscn --quit-after 300` |
| Export release | `godot --headless --path . --export-release "Windows Desktop" build/win/game.exe` |
| Export debug | `godot --headless --path . --export-debug "Linux" build/linux/game.x86_64` |
| Export only the .pck | `godot --headless --path . --export-pack "Linux" build/game.pck` |

The quoted name is the preset name from `export_presets.cfg`; it must exist (create presets
once in the editor: Project → Export). Create the output folder first, or the export fails.
A nonzero exit code means failure; grep the output for `ERROR:` and `SCRIPT ERROR:` too,
because some failures still exit 0.

Exports need **export templates** matching the exact Godot version:
`<user data>/export_templates/4.x.stable/` (Linux: `~/.local/share/godot/export_templates/`,
Windows: `%APPDATA%\Godot\export_templates\`, macOS: `~/Library/Application Support/Godot/export_templates/`).

## Tests

- **GUT**: `godot --headless --path . -s addons/gut/gut_cmdln.gd -gdir=res://test -ginclude_subdirs -gexit`
- **gdUnit4**: `addons/gdUnit4/runtest.sh -a res://test` (Windows: `runtest.cmd`), with the
  `GODOT_BIN` environment variable pointing at the Godot binary.

## GitHub Actions template

Copy [assets/godot-ci.yml](assets/godot-ci.yml) to `.github/workflows/godot-ci.yml`, then:

1. Set `GODOT_VERSION` to the project's exact version (for example `4.5.1`) and keep
   `GODOT_RELEASE` as `stable` unless the project uses a beta/rc build.
2. Make sure `export_presets.cfg` is committed and that preset names match the matrix
   (`Windows Desktop`, `Linux`, `macOS`, `Web`), or edit the matrix.
3. Check the `.gitignore` doesn't exclude `export_presets.cfg`. Recent Godot 4 versions
   keep signing passwords and the encryption key in a separate `export_credentials.cfg`
   (under `.godot/`), which must never be committed. Pass secrets to CI through GitHub
   Secrets instead.
4. Optional: copy `godot_lint.py` from the `godot-project-lint` skill to `tools/` to make CI
   fail on broken `res://` paths and Godot 3 leftovers.

The workflow imports, runs the lint step, exports each preset, and uploads the builds as
artifacts. On a `v*` tag it attaches zips to a GitHub Release.

## Common failures

| Symptom | Cause / fix |
| --- | --- |
| `No export template found` | Template version doesn't match the binary; folder must be `4.x.stable` exactly |
| Export works locally, CI build missing resources | Assets never imported: run `--import` first |
| Textures missing only in CI | `.import` files not committed, or path case mismatch (run `godot-project-lint`) |
| `Invalid export preset name` | Typo or preset not in committed `export_presets.cfg` |
| Web build blank page | Threaded web builds need cross-origin isolation headers; on hosts like itch.io turn "Thread Support" off in the Web preset (or enable itch's SharedArrayBuffer option) |
