---
name: blender-scene-audit
description: Audits a Blender scene or .blend file for game-engine readiness and reports problems as JSON - unapplied or negative scale, n-gons, missing UVs, non-manifold edges, loose and degenerate geometry, triangle budgets, empty material slots, missing textures, bad names, unit scale, armature naming. Use before exporting a model to Godot, Unity or Unreal, when a model looks wrong in an engine (inverted normals, wrong size, black textures, broken lighting), or when the user asks to check, clean up or validate a 3D asset. Works headless with the blender CLI or inside a live Blender via MCP.
license: MIT
compatibility: Requires Blender 4.2+ (tested on 5.2). Uses only bpy and bmesh.
metadata:
  author: gamedev-doctor
  version: "0.1.0"
---

# Blender scene audit

The script [scripts/scene_audit.py](scripts/scene_audit.py) is read-only: it never modifies
the scene. It reads the **evaluated** mesh (modifiers applied), which is what an exporter
writes, so triangle counts match the engine.

## Run it

**Headless on a .blend file** (no UI, safe for CI):

```bash
blender -b path/to/model.blend --python scripts/scene_audit.py -- --max-tris 5000
```

Options after `--`: `--selected` (only the selected objects; in a headless file this is
the selection saved in the file), `--max-tris N` (per-object budget), `--json out.json`.
Parse the output between `AUDIT_JSON_BEGIN` and `AUDIT_JSON_END`.

Finding Blender: `blender` on PATH; Windows default
`C:\Program Files\Blender Foundation\Blender <ver>\blender.exe` or the Steam install
`...\steamapps\common\Blender\blender.exe`; macOS `/Applications/Blender.app/Contents/MacOS/Blender`.

**In a live Blender via an MCP server** (for example one with an `execute_blender_code` tool):

```python
import json
exec(open(r"<absolute path>/scripts/scene_audit.py").read())
print(json.dumps(audit(selected_only=False, max_tris=5000), indent=1))
```

## Report format

```json
{
  "summary": {"error": 2, "warning": 4, "info": 4},
  "totals": {"objects": 3, "meshes": 2, "tris": 56, "materials": 0},
  "scene_issues": [{"severity": "error", "code": "missing_texture", "message": "..."}],
  "objects": [{"name": "Crate", "type": "MESH", "stats": {"tris": 12, "ngons": 0, "uv_layers": 1},
               "issues": [{"severity": "warning", "code": "unapplied_scale", "message": "..."}]}]
}
```

## How to present results

1. Lead with the counts: "2 errors, 4 warnings across 3 objects, 56 triangles total."
2. List **errors** first, grouped by code, with object names.
3. For each issue give the one-line fix (below). Offer to apply fixes, **but ask first**:
   the user's .blend is their work and fixes like applying scale change the file.

## Fix table

| Code | Why it matters | Fix (UI / bpy) |
| --- | --- | --- |
| `negative_scale` | Flipped normals, inside-out mesh in engine | Ctrl+A → Scale, then Mesh → Normals → Recalculate Outside / `bpy.ops.object.transform_apply(scale=True)` + `bpy.ops.mesh.normals_make_consistent()` in Edit mode |
| `unapplied_scale` | Colliders, physics, LOD distances wrong | Ctrl+A → Scale / `transform_apply(location=False, rotation=False, scale=True)` |
| `unapplied_rotation` | Instanced assets come in rotated | Ctrl+A → Rotation (only for assets, not placed scene objects) |
| `no_uv` | Textures and baked lighting impossible | Edit mode → U → Smart UV Project / `bpy.ops.uv.smart_project()` |
| `ngons` | Engine triangulation is unpredictable, shading artifacts | Triangulate modifier or Face → Triangulate Faces; better: fix topology to quads |
| `non_manifold` | Bad colliders, lightmap seams | Select → All by Trait → Non Manifold, then fix holes / remove internal faces |
| `loose_verts` | Wasted data, bounding box wrong | Mesh → Clean Up → Delete Loose |
| `degenerate` | Zero-area faces break normals and lightmaps | Mesh → Clean Up → Degenerate Dissolve |
| `missing_texture` | Black/pink materials in engine | File → External Data → Find Missing Files, or pack: File → External Data → Pack Resources |
| `empty_slot` | Faces with no material | Assign a material or remove the slot |
| `unit_scale` | Wrong size in engine | Scene Properties → Units: Metric, Unit Scale 1.0 |
| `armature_name` | Unreal adds an extra root bone for "Armature" | Rename the armature object (e.g. `root` or the character name) |
| `dup_name`, `unsafe_name` | Ugly or broken node names | Rename: ASCII, no spaces, `SM_Crate`, `SK_Hero` style |
| `over_budget` | Too heavy for the target | Decimate modifier, LODs, or retopology |

## Typical budgets (triangles per asset, rough)

Mobile prop 300-3k · PC/console prop 1k-20k · hero character 20k-100k (PC/console),
5k-20k (mobile). With Unreal Nanite, static meshes can be far denser, but skinned and
translucent meshes still need budgets.
