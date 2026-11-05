---
name: game-repo-setup
description: Sets up or repairs version control for a game project - engine-correct .gitignore, .gitattributes with Git LFS for binary assets (textures, audio, models, .uasset/.umap), and line-ending rules. Use when creating a new Godot, Unity, Unreal or Blender project repo, when the user asks to put a game on GitHub, when pushes fail because of large files, or when the repo contains Library/, .godot/, Intermediate/ or other generated folders.
license: MIT
metadata:
  author: gamesmith
  version: "0.1.0"
---

# Game repo setup

Game repositories break in three predictable ways: generated folders get committed
(gigabytes of `Library/` or `DerivedDataCache/`), binary assets go into plain Git
(the repo becomes unclonable, GitHub rejects files over 100 MB), and line endings flip
on text assets. This skill fixes all three.

## Steps

1. **Detect the engine.** Look at the project root:
   - `project.godot` → `godot`
   - `ProjectSettings/ProjectVersion.txt` and `Assets/` → `unity`
   - `*.uproject` → `unreal`
   - only `.blend` files → `blender`

   A repo can mix engines (for example a Unity project plus a `blender/` source folder);
   pass several `--engine` flags.

2. **Preview** the files the script would write:

   ```bash
   python scripts/gen_repo_files.py --engine unity --engine blender --dry-run
   ```

3. **Write them.** The script never overwrites an existing file unless you pass `--force`.
   If a `.gitignore` or `.gitattributes` already exists, use `--merge`: it appends only the
   lines that are missing, under a `# --- added by gamesmith ---` marker.

   ```bash
   python scripts/gen_repo_files.py --engine unity --out . --merge
   ```

4. **Turn on LFS** (once per machine, then per repo):

   ```bash
   git lfs install
   ```

5. **If binaries were already committed without LFS**, they stay in history. Tell the
   user, and only with their explicit go-ahead rewrite history:

   ```bash
   git lfs migrate import --include="*.png,*.wav,*.fbx" --everything
   ```

   This rewrites every commit hash. Anyone else with a clone must re-clone, and the push
   needs `--force`. Never run it without asking.

6. **Remove generated folders that are already tracked** without deleting them on disk:

   ```bash
   git rm -r --cached Library Temp Logs
   ```

## Engine-specific notes

- **Unity**: text serialization and visible meta files must be on, otherwise scenes and
  prefabs are binary and unmergeable. Check `ProjectSettings/EditorSettings.asset` for
  `m_SerializationMode: 2` and `m_ExternalVersionControlSupport: Visible Meta Files`.
  Never ignore `*.meta` files. The `unity-project-hygiene` skill checks this.
- **Unreal**: `.uasset` and `.umap` are binary and unmergeable. The generated
  `.gitattributes` marks them `lockable`, so `git lfs lock Content/Maps/Main.umap`
  prevents two people editing the same map.
- **Godot**: everything under `.godot/` is a regenerable cache. `.import` files next to
  assets *are* source and must be committed (Godot 4 also keeps `*.uid` files beside
  scripts in 4.4+, commit those too).
- **Blender**: `*.blend1`, `*.blend2` are autosave backups; they are ignored.

## GitHub limits worth telling the user

- Files over 100 MB are rejected outright without LFS.
- Free GitHub LFS has a small storage and bandwidth quota; large teams usually buy data
  packs or self-host (Gitea, GitLab) for asset-heavy projects.
