# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/); each plugin carries its own version in
`plugin.json`.

## [0.1.0] - 2026-11-05

### Added
- **gamedev-core**: `game-repo-setup` (gitignore/LFS generator with merge mode),
  `game-feel`, `game-perf-budget`.
- **blender-doctor**: `blender-scene-audit` (read-only JSON audit),
  `blender-export-to-engine` (Godot/glTF/Unity/Unreal presets, version-tolerant options).
- **godot-doctor**: `godot4-gdscript`, `godot-project-lint` (Godot 3 leftovers, missing
  and case-mismatched `res://` paths, UID-rescued stale paths), `godot-headless-ci` with a
  GitHub Actions template.
- **unity-doctor**: `unity-project-hygiene` (meta/GUID/serialization checker),
  `unity-batchmode` with a build script.
- **unreal-doctor**: `unreal-cpp-gameplay`, `unreal-project-hygiene` (uproject, modules,
  targets, header lint, Git LFS).
- Skill validator, fixture-based tests, Blender smoke test, CI on Linux/Windows/macOS.
