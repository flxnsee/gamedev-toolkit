---
name: blender-export-to-engine
description: Exports models from Blender with the correct per-engine settings in one command - .glb for Godot and web, .fbx tuned for Unity (no -90 degree rotation, scale 1) and for Unreal (smoothing groups, no leaf bones). Use when the user wants to get a Blender model, character or animation into Godot, Unity, Unreal, three.js or another engine, when an imported model is rotated, 100x too big or small, has extra bones, missing smoothing or missing animations, or when setting up an automated asset export pipeline.
license: MIT
compatibility: Requires Blender 4.2+ (tested on 5.2) with the bundled glTF and FBX exporters enabled.
metadata:
  author: gamedev-doctor
  version: "0.1.0"
---

# Blender export to engine

## Workflow

1. **Audit first.** Run the `blender-scene-audit` skill if it is available. Exporting a mesh
   with negative scale or no UVs just moves the bug into the engine.
2. **Pick the engine preset** and run [scripts/export_for_engine.py](scripts/export_for_engine.py).
3. **Check the JSON report**: `ok`, file size, and `skipped_options` (options your Blender
   version doesn't have; usually harmless, mention them).
4. **Tell the user how to verify** in the engine (section below).

```bash
blender -b model.blend --python scripts/export_for_engine.py -- --engine godot --out exports/model.glb
blender -b model.blend --python scripts/export_for_engine.py -- --engine unity --out ../MyGame/Assets/Models/model.fbx --selected
```

Live Blender (MCP `execute_blender_code` or Text Editor):

```python
exec(open(r"<absolute path>/scripts/export_for_engine.py").read())
print(export(engine="unreal", out=r"C:/Exports/SM_Crate.fbx", selected=True))
```

The script does not change the scene. It switches to Object mode if needed.

## Presets

| `--engine` | Format | Key settings | Why |
| --- | --- | --- | --- |
| `godot` | `.glb` | Y-up, modifiers applied, skins, morphs, animations | glTF is Godot's native and best-supported format |
| `gltf` | `.glb` | Same plus tangents | three.js, Babylon, Unreal Interchange, Unity glTFast |
| `unity` | `.fbx` | Apply Scalings = FBX All, Apply Transform (bake space), -Z forward / Y up, no leaf bones | Imports at scale 1 with zero rotation instead of (-90, 0, 0) and 100x |
| `unreal` | `.fbx` | Smoothing = Face, tangent space, no leaf bones, deform bones only | Avoids "no smoothing group" warnings and junk end bones |

## Engine-side notes

**Godot 4**
- Drop the `.glb` into the project; Godot imports it as a scene. Double-click it for the
  Advanced Import Settings (physics colliders, LODs, animation loops, material extraction).
- Name suffixes in Blender create colliders automatically on import: `-col` (static body +
  collider), `-colonly` (collider only), `-convcolonly`, `-rigid`, `-navmesh`, `-noimp`.
- Godot can also import `.blend` files directly when the Blender path is set in Editor
  Settings → FileSystem → Import. That's fine for solo work; the `.glb` keeps teammates
  from needing Blender.

**Unity**
- In the model's Import Settings check Scale Factor 1 and "Convert Units" on. With the
  preset, the root has rotation (0,0,0).
- For characters: Rig tab → Humanoid or Generic; Animation tab → set loop time on clips.
- Unity 6 can import glTF only through a package (glTFast); FBX is the default path.

**Unreal Engine 5**
- Static meshes: import as-is. Blender's 1 m = Unreal's 100 cm conversion is handled by
  the FBX unit header, so a 2 m Blender cube imports as 200 uu.
- Skeletal meshes: rename the armature object (not "Armature") so Unreal doesn't add an
  extra root. If animations come in at 100x scale or with a 0.01 root, the reliable fix
  is: Blender Scene Units → Unit Scale 0.01, scale the rig ×100, apply scale, re-export.
- UE 5.x also imports `.glb` through Interchange; FBX remains the more battle-tested
  path for skeletal animation.

## Shape keys and "apply modifiers"

Blender can't apply modifiers to a mesh with shape keys, so on such a mesh the exporters
either skip the modifiers or lose the shape keys. If the user has both, warn them and suggest
applying the modifiers manually before adding shape keys, or an add-on that applies
modifiers while keeping shape keys.

## Batch export pattern

For one file per object (common for prop kits), loop over objects, select one at a time,
and call `export(..., selected=True)` with `out=f"exports/{obj.name}.glb"`. Move each
object to the origin first if the engine expects pivot-at-origin assets, and move it
back afterwards so the user's scene is unchanged.
