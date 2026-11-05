---
name: unreal-project-hygiene
description: Checks an Unreal Engine 5 project folder without opening the editor - .uproject and .uplugin JSON, modules missing their Build.cs, missing Editor/Game Target.cs, headers where .generated.h is not the last include or GENERATED_BODY is missing, raw UObject pointers without UPROPERTY that the garbage collector can free, and Git setup (.gitignore, LFS for .uasset/.umap, tracked Binaries/Intermediate). Use when an Unreal project fails to open or compile, "modules are missing or built with a different engine version", random crashes from dangling pointers, before committing an Unreal project to Git, or when auditing an Unreal repo.
license: MIT
compatibility: Python 3.10+, standard library only. Unreal itself is not required. Optional git for tracked-file checks.
metadata:
  author: gamedev-toolkit
  version: "0.1.0"
---

# Unreal project hygiene

## Run

```bash
python scripts/ue_project_check.py path/to/ProjectFolder        # folder containing the .uproject
python scripts/ue_project_check.py . --json
```

Exit code `0` = no errors, `1` = errors, `2` = no `.uproject` found.

## Findings and fixes

| Code | Severity | Fix |
| --- | --- | --- |
| `uproject-json`, `uplugin-json` | error | Fix the JSON (usually a trailing comma after hand edits) |
| `module-missing` | error | Remove the module from `.uproject` or create `Source/<Name>/<Name>.Build.cs` |
| `no-editor-target` | error | Add `Source/<Project>Editor.Target.cs` (`Type = TargetType.Editor`) |
| `no-game-target` | warning | Add `Source/<Project>.Target.cs` (`Type = TargetType.Game`) |
| `generated-include-order` | error | Move `#include "X.generated.h"` to be the last include |
| `missing-generated-include` / `missing-generated-body` | error | Add the include / `GENERATED_BODY()` as the first line of the class or struct body |
| `raw-uobject-member` | warning | `UPROPERTY() TObjectPtr<UFoo> Foo;`. Use `TWeakObjectPtr<UFoo>` for references that must not keep the object alive. Heuristic: check before changing |
| `no-lfs`, `no-gitignore`, `gitignore-incomplete` | warning | Run the `game-repo-setup` skill with `--engine unreal` |
| `generated-tracked` | error | `git rm -r --cached Binaries Intermediate Saved DerivedDataCache` |
| `plugin-unbuilt` | info | Fine for programmers. Artists without Visual Studio need prebuilt plugin Binaries or a packaged editor build |
| `source-engine` | info | Project is tied to a source-built engine |

## "Modules are missing or built with a different engine version"

This dialog on open means the C++ binaries are stale. In order:
1. Close the editor.
2. Build from the command line (Windows):
   `"<UE>/Engine/Build/BatchFiles/Build.bat" <Project>Editor Win64 Development -Project="<abs path>/<Project>.uproject" -WaitMutex`
3. If it still fails, delete `Binaries/` and `Intermediate/` (generated, safe to delete),
   regenerate project files (right-click the `.uproject` → Generate Visual Studio project files),
   and build again.
4. Read the first `error C` / `error LNK` / UHT error in the output. That's the real cause.

Ask before deleting folders, even generated ones, if the user has uncommitted work there
(for example a `Saved/` folder holding their only autosaves).
