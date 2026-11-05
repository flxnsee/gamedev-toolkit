---
name: unity-batchmode
description: Runs Unity without the editor UI - EditMode and PlayMode tests, player builds through a build script with a proper exit code, and compile checks - and reads the Unity log to report errors. Use when the user wants to build a Unity game from the terminal or CI, run Unity Test Framework tests headless, check whether C# scripts compile after an edit, or set up GitHub Actions for Unity.
license: MIT
compatibility: Unity 2021.3+ (tested commands are the same in Unity 6). A Unity license must be activated on the machine.
metadata:
  author: gamedev-toolkit
  version: "0.1.0"
---

# Unity batchmode

## Find the editor

The project's version is in `ProjectSettings/ProjectVersion.txt` (`m_EditorVersion`).
Use exactly that version from Unity Hub's install folder:

- Windows: `C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe`
- macOS: `/Applications/Unity/Hub/Editor/<version>/Unity.app/Contents/MacOS/Unity`
- Linux: `~/Unity/Hub/Editor/<version>/Editor/Unity`

**The project must not be open in the editor**: Unity locks it, and batchmode fails with
"It looks like another Unity instance is running with this project open." Ask the user to
close it.

## Commands

Always pass `-logFile <file>` and read it afterwards. The exit code alone hides the reason.

| Task | Command (append `-projectPath <dir> -logFile <file>`) |
| --- | --- |
| Compile check (import + compile, then quit) | `Unity -batchmode -nographics -quit` |
| EditMode tests | `Unity -batchmode -nographics -runTests -testPlatform EditMode -testResults results-edit.xml` |
| PlayMode tests | `Unity -batchmode -runTests -testPlatform PlayMode -testResults results-play.xml` |
| Build via script | `Unity -batchmode -nographics -quit -executeMethod GamedevToolkit.BuildScript.BuildFromCommandLine -buildTarget Win64 -target StandaloneWindows64 -out Builds/Win/Game.exe` |

Notes:
- **Don't pass `-quit` with `-runTests`**: the test runner quits by itself, and `-quit` can
  stop it before the tests run.
- `-nographics` breaks PlayMode tests that render or use GPU features. Drop it for those.
- `-testResults` writes NUnit XML. Count `<test-case ... result="Failed">` elements and
  report each failure's `<message>`.
- Filter tests with `-testFilter "Namespace.Class.Method"` or `-testCategory "Fast"`.

## Build script

Copy [assets/BuildScript.cs](assets/BuildScript.cs) to `Assets/Editor/BuildScript.cs` (it
must be in an `Editor` folder). It reads `-target` (a `BuildTarget` enum name such as `StandaloneWindows64`, `StandaloneLinux64`, `Android`, `WebGL`) and `-out`, builds every scene
enabled in Build Settings, and exits with code 1 on failure, so CI fails properly.

## Reading the log

Search the log file for, in order:
1. `error CS` — C# compile errors (file, line, message). Fix these first; nothing else runs.
2. `Scripts have compiler errors.` — confirms the build stopped at compilation.
3. `Build Finished, Result: Failed` / `Error building Player` — build failures.
4. `Exception` — runtime errors in editor scripts.
5. `[Licensing]` — license or activation problems (common in CI).

Report the first real error with its file and line, not the whole log.

## CI

For GitHub Actions the community **GameCI** actions (`game-ci/unity-test-runner`,
`game-ci/unity-builder`) handle Docker images and license activation. They need the
`UNITY_LICENSE` (or `UNITY_SERIAL` for Pro), `UNITY_EMAIL` and `UNITY_PASSWORD` repository
secrets. Point the user to game.ci's activation docs for their license type. Never put
credentials in the workflow file.
