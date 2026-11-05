# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/); each plugin carries its own version in
`plugin.json`.

## [0.1.0] - 2026-11-05

### Added
- **core**: `game-repo-setup` (gitignore/LFS generator with merge mode),
  `game-feel`, `game-perf-budget`.
- **blender**: `blender-scene-audit` (read-only JSON audit),
  `blender-export-to-engine` (Godot/glTF/Unity/Unreal presets, version-tolerant options).
- **godot**: `godot4-gdscript`, `godot-project-lint` (Godot 3 leftovers, missing
  and case-mismatched `res://` paths, UID-rescued stale paths), `godot-headless-ci` with a
  GitHub Actions template.
- **unity**: `unity-project-hygiene` (meta/GUID/serialization checker),
  `unity-batchmode` with a build script.
- **unreal**: `unreal-cpp-gameplay`, `unreal-project-hygiene` (uproject, modules,
  targets, header lint, Git LFS).
- Skill validator, fixture-based tests, CI on Linux/Windows/macOS (Python 3.10+), Blender
  smoke test on Blender 4.2 LTS and 5.2 LTS.
- README demo image rendered from real linter output and a social preview image.
