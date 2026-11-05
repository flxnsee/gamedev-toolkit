# Contributing to gamedev-toolkit

Thanks for helping! New skills, fixes to engine facts, and new checks are all welcome.

## Layout

```
.claude-plugin/marketplace.json      # lists every plugin
plugins/<engine>/                    # or plugins/core/ (engine-agnostic)
  .claude-plugin/plugin.json         # name must match the marketplace entry
  skills/<skill-name>/
    SKILL.md                         # frontmatter + instructions (< 500 lines)
    scripts/                         # runnable checks (stdlib Python preferred)
    assets/                          # templates the agent copies into projects
    references/                      # long docs loaded only when needed
tests/                               # unittest + fixture projects with planted bugs
tools/validate_skills.py             # spec + manifest validator (runs in CI)
```

## What makes a good skill

1. **One job.** "Lint a Godot project", not "everything about Godot".
2. **The description decides when it triggers.** State what it does *and* when to use it,
   with the words users actually type ("parse error", "references broke", "floaty jump").
   Max 1024 characters.
3. **Prefer a script over prose** whenever the check is deterministic. Scripts must:
   - use only the Python standard library (Blender scripts may use `bpy`/`bmesh`);
   - never modify the user's project unless the skill says so and the agent asks first;
   - print human-readable output and support `--json`;
   - exit 0 / 1 (problems found) / 2 (wrong input).
4. **Tell the agent how to present results and fix them**, including what to ask the user
   before doing anything destructive.
5. **Be precise about versions.** If something changed in Godot 4.4 or Unity 6, say so.
   Don't guess engine facts: link the docs in your PR.

## Adding a skill

1. Create `plugins/<engine>/skills/<skill-name>/SKILL.md`. The `name` must equal
   the folder name (lowercase, digits, single hyphens).
2. If it has a script, add a fixture under `tests/fixtures/` with planted problems *and*
   clean files, and tests in `tests/` that assert both.
3. Run:
   ```bash
   python tools/validate_skills.py
   python -m unittest discover tests -v
   ```
4. Add the skill to the table in `README.md` and to `CHANGELOG.md`.
5. Bump `version` in the plugin's `plugin.json` (minor for new skills, patch for fixes).

## Adding an engine

Create `plugins/<engine>/` with a `plugin.json` and add it to
`.claude-plugin/marketplace.json`. The validator fails if a plugin folder isn't listed.
