# gamesmith

**Game-dev skills for AI coding agents that run real checks on your project.**

Claude Code, Codex, Cursor and other agents write Godot 3 code in Godot 4 projects, lose
Unity `.meta` files, forget `UPROPERTY` on pointers, and export Blender models rotated
-90°. gamesmith gives them engine-specific instructions **plus tested scripts** that
inspect your actual project and report problems as JSON. No role-play agents, no
"you are a senior game designer" prompts: just checks that run.

```text
$ python godot_lint.py my-game
Godot 4 project: 48 scripts, 31 scenes, 12 resources, 214 res:// references checked
6 errors, 1 warnings, 0 info
  [error] scenes/main.tscn:4 path-case: res://art/hero.png differs in letter case from res://Art/hero.png.
          Works in the editor on Windows/macOS, fails in exported builds and on Linux.
  [error] scripts/player.gd:17 gd3-move-and-slide: Godot 4 `move_and_slide()` takes no arguments ...
  [error] scripts/player.gd:18 gd3-yield: `yield()` was removed. Use `await obj.signal_name` ...
```

## Skills

| Plugin | Skill | What it does | Runs a script |
| --- | --- | --- | :---: |
| **core** | `game-repo-setup` | Engine-correct `.gitignore` + Git LFS `.gitattributes` (lockable `.uasset`/`.umap`), merge-safe | ✅ |
| | `game-feel` | Coyote time, jump buffer, hit stop, trauma screen shake, frame-rate independent smoothing (GDScript, C#, UE notes) | |
| | `game-perf-budget` | Frame budgets, CPU vs GPU bound, profiler workflow and fixes per engine | |
| **blender** | `blender-scene-audit` | Game-readiness audit: n-gons, negative/unapplied scale, missing UVs, non-manifold, tri budgets, missing textures | ✅ |
| | `blender-export-to-engine` | One command export with the right settings for Godot (.glb), Unity (.fbx, no -90° rotation), Unreal (.fbx) | ✅ |
| **godot** | `godot4-gdscript` | Typed, idiomatic Godot 4 GDScript + full Godot 3 → 4 migration table | |
| | `godot-project-lint` | Static linter: Godot 3 leftovers, missing `res://` files, UID-rescued stale paths, path letter-case bugs | ✅ |
| | `godot-headless-ci` | Headless import/test/export + GitHub Actions template that releases on tags | ✅ |
| **unity** | `unity-project-hygiene` | Missing/orphan `.meta`, duplicate GUIDs, binary scenes, serialization mode, tracked `Library/` | ✅ |
| | `unity-batchmode` | Headless tests and builds with a build script that sets a real exit code | ✅ |
| **unreal** | `unreal-cpp-gameplay` | UE5 C++ that compiles first time: GC rules, `TObjectPtr`, Enhanced Input, Build.cs modules, replication | |
| | `unreal-project-hygiene` | `.uproject`/modules/targets check, `.generated.h` order, raw `UObject*` without `UPROPERTY`, LFS | ✅ |

The scripts use only the Python standard library (Blender scripts use `bpy`). The Godot,
Unity and Unreal checkers **don't need the engine installed**, so they run in CI too.

## Install

### Claude Code

```bash
claude plugin marketplace add OWNER/gamesmith
claude plugin install gamesmith-godot@gamesmith      # or -core, -blender, -unity, -unreal
```

Inside a session: `/plugin marketplace add OWNER/gamesmith`, then `/plugin`.
Install only the engines you use. Skills trigger automatically from their descriptions.

### Any agent that supports Agent Skills (Codex, Cursor, Gemini CLI, ...)

```bash
npx skills add OWNER/gamesmith
```

Or copy a skill folder (for example `plugins/gamesmith-godot/skills/godot-project-lint`)
into your agent's skills directory. For Claude Code without plugins that's
`~/.claude/skills/<skill-name>/`. Every skill follows the open
[Agent Skills specification](https://agentskills.io/specification).

### Just the scripts

```bash
python plugins/gamesmith-godot/skills/godot-project-lint/scripts/godot_lint.py path/to/project
python plugins/gamesmith-unity/skills/unity-project-hygiene/scripts/unity_meta_check.py path/to/project
python plugins/gamesmith-unreal/skills/unreal-project-hygiene/scripts/ue_project_check.py path/to/project
blender -b model.blend --python plugins/gamesmith-blender/skills/blender-scene-audit/scripts/scene_audit.py
```

## Try asking your agent

- "Check this Godot project before I export it"
- "My Unity references broke after pulling, find out why"
- "Export the selected Blender objects for Unreal"
- "Set up Git LFS for this Unreal project"
- "The jump feels floaty, fix it"
- "Why does my game drop to 40 FPS when enemies spawn?"

## Works with MCP servers

The Blender skills run headless with the `blender` CLI **or** inside a live Blender through
any MCP server that can execute Python (`execute_blender_code`-style tools). They tell the
agent how to do both.

## Quality bar

Every skill is checked in CI on Linux, Windows and macOS:

- `tools/validate_skills.py` validates every `SKILL.md` against the Agent Skills spec
  (name, description, size, referenced files exist) and the plugin manifests.
- `tests/` has fixture projects with planted bugs for Godot, Unity and Unreal. Each
  checker must find every one and report nothing on the clean files.
- The Blender audit and all four export presets run against a real Blender in CI.

## Roadmap

- [ ] `godot-scene-builder`: create scenes and node trees from a spec through Godot's headless API
- [ ] `unity-addressables-audit`, `unity-asmdef-graph`
- [ ] `unreal-blueprint-audit` via editor Python
- [ ] `blender-lod-generator`, `blender-collision-from-mesh`, texture baking presets
- [ ] `game-localization` (CSV/PO pipelines for Godot, Unity Localization, UE String Tables)
- [ ] `game-save-system`, `game-input-remapping`, `steam-release-checklist`
- [ ] Bevy, Defold, Roblox (Luau), Phaser, MonoGame plugins
- [ ] Evals: with-skill vs without-skill benchmark on real tasks

Ideas and requests: open an issue. Skills that help most people come first.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: one skill = one focused job, a
description that says *what and when*, and a script with fixture tests whenever the check
can be automated.

## License

[MIT](LICENSE)
