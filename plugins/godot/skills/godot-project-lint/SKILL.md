---
name: godot-project-lint
description: Lints a Godot 4 project without opening the editor - finds Godot 3 GDScript that breaks in Godot 4 (onready, export, yield, setget, old connect, KinematicBody2D, move_and_slide with arguments, renamed functions), res:// paths to missing files, stale paths rescued by UID, and path letter-case mismatches that work on Windows but break exported builds. Use after porting from Godot 3, after AI-generated or copy-pasted GDScript, before exporting a build, when the editor shows "parse error" or "failed to load resource", or as a CI check.
license: MIT
compatibility: Python 3.9+, standard library only. Godot itself is not required.
metadata:
  author: gamedev-toolkit
  version: "0.1.0"
---

# Godot project lint

[scripts/godot_lint.py](scripts/godot_lint.py) is a static checker. It does not run Godot,
so it is fast and safe to run anywhere, including CI.

## Run

```bash
python scripts/godot_lint.py path/to/project            # human-readable
python scripts/godot_lint.py path/to/project --json     # for parsing
python scripts/godot_lint.py . --include-addons         # also check res://addons
```

Exit code `0` = no errors, `1` = errors, `2` = no `project.godot` found.
`addons/` is skipped by default because it is usually third-party code.

## What it reports

| Code | Severity | Meaning |
| --- | --- | --- |
| `gd3-*` | error | Godot 3 syntax or API in a Godot 4 project. The message names the Godot 4 replacement |
| `missing-resource` | error | `res://` path in a scene, resource, `preload`/`load`, autoload or main scene doesn't exist |
| `path-case` | error | Path exists only with different letter case. Windows/macOS editor loads it; exported `.pck` and Linux don't |
| `stale-path` | warning | Path is gone but the UID is known, so Godot loads the moved file. Re-save the scene to refresh the path |
| `godot3-project` | info | `config_version=4`: this is a Godot 3 project, so Godot 3→4 rules are skipped |

Only literal string paths are checked; `load("res://levels/%s.tscn" % name)` can't be
verified statically.

## Fixing findings

1. **Fix errors file by file**, top to bottom. The message names the Godot 4 replacement.
   For the Godot 3→4 API, use the `godot4-gdscript` skill's migration table if available.
2. **Don't hand-edit `.tscn` paths for `stale-path`.** Open the scene in the editor and save
   it, or run `godot --headless --path . --import` if Godot is installed. Godot then rewrites
   the paths itself.
3. **`path-case`**: change the reference to the exact on-disk case. Renaming the file instead
   breaks other references, and Git on Windows/macOS needs `git mv -f old New` to record a
   case-only rename.
4. Re-run the linter until it exits 0, then (if Godot is installed) confirm with
   `godot --headless --path . --quit` (see `godot-headless-ci`).

## Large Godot 3 ports

If the project still has `config_version=4`, don't fix scripts by hand: tell the user to back
up or commit, then open it in Godot 4 (Project Manager offers conversion) or run
`godot --headless --path . --convert-3to4`. Then run this linter to catch what the converter
missed. It usually misses `yield` patterns, `setget`, and `connect()` with bind arrays.
