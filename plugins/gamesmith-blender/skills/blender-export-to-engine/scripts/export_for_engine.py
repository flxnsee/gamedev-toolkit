"""Export the scene (or selection) with settings tuned for a target game engine.

Headless:
  blender -b model.blend --python export_for_engine.py -- --engine godot --out build/model.glb [--selected]

Live Blender (MCP / Text Editor):
  exec(open(r"/path/export_for_engine.py").read()); export(engine="unity", out=r"C:/proj/Assets/Models/model.fbx")

Engines:
  godot  -> .glb  (glTF binary, Y-up, modifiers applied)
  unity  -> .fbx  (transform baked so objects import without the -90 deg X rotation, scale 1)
  unreal -> .fbx  (smoothing groups, no leaf bones, tangent space)
  gltf   -> .glb  (generic glTF for three.js / Babylon / Unreal Interchange / Unity glTFast)

Options are filtered against the installed exporter, so unknown keys from newer or older
Blender versions are skipped with a note instead of crashing. Does not modify the scene.
"""
from __future__ import annotations

import json
import os
import sys

import bpy

GLTF_BASE = {
    "export_format": "GLB",
    "export_yup": True,
    "export_apply": True,          # apply modifiers (shape keys block this; see SKILL.md)
    "export_texcoords": True,
    "export_normals": True,
    "export_tangents": False,
    "export_materials": "EXPORT",
    "export_animations": True,
    "export_skins": True,
    "export_morph": True,
    "export_cameras": False,
    "export_lights": False,
}

FBX_BASE = {
    "object_types": {"MESH", "ARMATURE", "EMPTY"},
    "use_mesh_modifiers": True,
    "mesh_smooth_type": "FACE",     # writes smoothing groups; avoids "no smoothing group" warnings
    "add_leaf_bones": False,        # leaf bones add junk end bones in engines
    "primary_bone_axis": "Y",
    "secondary_bone_axis": "X",
    "use_armature_deform_only": True,
    "bake_anim": True,
    "bake_anim_use_all_actions": False,
    "bake_anim_use_nla_strips": True,
    "bake_anim_simplify_factor": 0.0,
    "path_mode": "COPY",
    "embed_textures": False,
    "axis_forward": "-Z",
    "axis_up": "Y",
}

PRESETS = {
    "godot": ("gltf", ".glb", {}),
    "gltf": ("gltf", ".glb", {"export_tangents": True}),
    "unity": ("fbx", ".fbx", {
        "apply_scale_options": "FBX_SCALE_ALL",
        "apply_unit_scale": True,
        "bake_space_transform": True,   # "Apply Transform": no -90 X rotation / 100 scale in Unity
    }),
    "unreal": ("fbx", ".fbx", {
        "apply_scale_options": "FBX_SCALE_NONE",
        "apply_unit_scale": True,
        "bake_space_transform": False,
        "use_tspace": True,
    }),
}


def _supported(op, opts: dict, skipped: list) -> dict:
    props = {p.identifier for p in op.get_rna_type().properties}
    out = {}
    for k, v in opts.items():
        if k in props:
            out[k] = v
        else:
            skipped.append(k)
    return out


def export(engine: str, out: str, selected: bool = False) -> dict:
    engine = engine.lower()
    if engine not in PRESETS:
        raise ValueError(f"engine must be one of {sorted(PRESETS)}")
    kind, ext, extra = PRESETS[engine]
    out = os.path.abspath(bpy.path.abspath(out))
    if not out.lower().endswith(ext):
        out = os.path.splitext(out)[0] + ext
    os.makedirs(os.path.dirname(out), exist_ok=True)

    if selected and not bpy.context.selected_objects:
        raise RuntimeError("--selected given but nothing is selected")

    skipped: list = []
    if kind == "gltf":
        op = bpy.ops.export_scene.gltf
        opts = dict(GLTF_BASE, **extra, filepath=out, use_selection=selected)
    else:
        op = bpy.ops.export_scene.fbx
        opts = dict(FBX_BASE, **extra, filepath=out, use_selection=selected)
    opts = _supported(op, opts, skipped)

    # Exporters need Object mode.
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    result = op(**opts)
    ok = "FINISHED" in result
    report = {
        "ok": ok,
        "engine": engine,
        "file": out,
        "bytes": os.path.getsize(out) if ok and os.path.exists(out) else 0,
        "selected_only": selected,
        "skipped_options": skipped,
        "blender": bpy.app.version_string,
    }
    return report


def _main(argv):
    import argparse

    args = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser(prog="export_for_engine.py")
    ap.add_argument("--engine", required=True, choices=sorted(PRESETS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--selected", action="store_true")
    ns = ap.parse_args(args)
    rep = export(ns.engine, ns.out, ns.selected)
    print("EXPORT_JSON_BEGIN")
    print(json.dumps(rep, indent=1, default=list))
    print("EXPORT_JSON_END")
    if not rep["ok"]:
        sys.exit(1)


if __name__ == "__main__" and "--" in sys.argv:
    _main(sys.argv)
