---
name: unity-project-hygiene
description: Checks a Unity project for the version-control problems behind "Missing Script", swapped or lost references and unmergeable scenes - assets without .meta files, orphan .meta files, duplicate or malformed GUIDs, binary scenes and prefabs, wrong Asset Serialization mode, hidden meta files, a bad .gitignore and tracked Library/ folders. Use when references break after a pull or merge, after copying assets between projects outside Unity, before a first commit, when setting up Unity with Git, or when the user asks to audit or clean up a Unity repo. Also gives safe rules for AI agents editing Unity files.
license: MIT
compatibility: Python 3.9+, standard library only. Unity itself is not required. Optional git for tracked-file checks.
metadata:
  author: gamedev-toolkit
  version: "0.1.0"
---

# Unity project hygiene

Unity identifies every asset by the GUID in its `.meta` file, not by path. Almost every
"Missing (Mono Script)", "references disappeared after pull" or "prefab points to the
wrong texture" bug is a `.meta` problem.

## Run the checker

```bash
python scripts/unity_meta_check.py path/to/UnityProject
python scripts/unity_meta_check.py . --json
```

Exit code `0` = clean, `1` = errors, `2` = not a Unity project (needs `Assets/` and
`ProjectSettings/`).

| Code | Severity | Fix |
| --- | --- | --- |
| `missing-meta` | error | Open Unity so it generates the `.meta`, **then commit it**. If a teammate already has the asset, get *their* `.meta` instead, or references break |
| `duplicate-guid` | error | Delete the `.meta` of the copy (not the original), let Unity regenerate it. Check which one other assets reference first: `git grep <guid> -- Assets` |
| `no-guid`, `bad-guid` | error | Restore the `.meta` from git history (`git log -- path.meta`) |
| `hidden-meta`, `gitignore-meta` | error | Meta files must be visible and committed |
| `generated-tracked` | error | `git rm -r --cached Library Temp Logs` and add them to `.gitignore` (the `game-repo-setup` skill can generate one) |
| `orphan-meta` | warning | The asset was deleted but its `.meta` was left, or the asset was never committed. Ask which one |
| `binary-asset`, `serialization-not-text` | warning | Project Settings → Editor → Asset Serialization: Force Text, then re-save |

Unity ignores, and gives no `.meta` to, names that start with `.`, end with `~`, are named
`cvs`, or end with `.tmp`. Folders like `Documentation~` are a valid way to keep files out
of the import.

## Rules for agents editing a Unity project

1. **Never delete or regenerate a `.meta` file to "fix" something** unless the checker found
   a duplicate GUID. A new GUID silently breaks every reference to that asset.
2. **Moving or renaming assets**: do it in the Unity Editor, or move the `.meta` together
   with the asset (`git mv Foo.cs Bar.cs` and `git mv Foo.cs.meta Bar.cs.meta`). For a
   `MonoBehaviour`, the class name must match the new file name.
3. **New C# script files**: create them freely. Unity generates the `.meta` on next focus.
   Remind the user to commit the generated `.meta`.
4. **Don't hand-edit `.unity` / `.prefab` YAML** unless the change is trivial and you know
   the `fileID`/`guid` structure. Prefer editor scripts or have the user do it in the editor.
5. **Never edit files under `Library/`**. It's a cache that Unity rebuilds.
6. After big changes, a reimport can take a long time. Tell the user before suggesting
   `Assets → Reimport All`.

## Merging scenes and prefabs

Configure Unity's Smart Merge so Git can merge YAML scenes. Add to `.git/config` or
`~/.gitconfig` (path varies per Unity version and OS):

```ini
[merge]
    tool = unityyamlmerge
[mergetool "unityyamlmerge"]
    trustExitCode = false
    cmd = '<Unity install>/Editor/Data/Tools/UnityYAMLMerge' merge -p "$BASE" "$REMOTE" "$LOCAL" "$MERGED"
```

Then resolve conflicts with `git mergetool`. To avoid conflicts in the first place, split
big scenes into prefabs and additive scenes so people rarely edit the same file.
