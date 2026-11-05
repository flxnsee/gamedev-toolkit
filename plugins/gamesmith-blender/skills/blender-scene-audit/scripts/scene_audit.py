"""Game-readiness audit for the open Blender scene. Read-only: changes nothing.

Run headless:
  blender -b model.blend --python scene_audit.py -- [--selected] [--max-tris N] [--json out.json]

Run inside a live Blender (MCP, Text Editor):
  exec(open(r"/path/to/scene_audit.py").read()); print(json.dumps(audit(), indent=1))

Prints a JSON report between AUDIT_JSON_BEGIN / AUDIT_JSON_END markers.
"""
from __future__ import annotations

import json
import os
import re
import sys

import bmesh
import bpy

DUP_SUFFIX = re.compile(r"\.\d{3}$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-.]+$")


def _issue(issues, severity, code, msg):
    issues.append({"severity": severity, "code": code, "message": msg})


def _is_identity_rot(obj, eps=1e-4):
    if obj.rotation_mode == "QUATERNION":
        q = obj.rotation_quaternion
        return abs(abs(q.w) - 1.0) < eps
    if obj.rotation_mode == "AXIS_ANGLE":
        return abs(obj.rotation_axis_angle[0]) < eps
    return all(abs(a) < eps for a in obj.rotation_euler)


def _mesh_stats(obj, depsgraph):
    """Stats on the evaluated mesh (modifiers applied), i.e. what an exporter sees."""
    ev = obj.evaluated_get(depsgraph)
    me = ev.to_mesh()
    try:
        bm = bmesh.new()
        bm.from_mesh(me)
        tris = sum(len(f.verts) - 2 for f in bm.faces)
        ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
        loose_verts = sum(1 for v in bm.verts if not v.link_edges)
        non_manifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
        boundary = sum(1 for e in bm.edges if e.is_boundary)
        zero_faces = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
        stats = {
            "verts": len(bm.verts),
            "faces": len(bm.faces),
            "tris": tris,
            "ngons": ngons,
            "loose_verts": loose_verts,
            "non_manifold_edges": non_manifold,
            "boundary_edges": boundary,
            "zero_area_faces": zero_faces,
            "uv_layers": len(me.uv_layers),
        }
        bm.free()
        return stats
    finally:
        ev.to_mesh_clear()


def audit(selected_only: bool = False, max_tris: int | None = None) -> dict:
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    report = {
        "file": bpy.data.filepath or "(unsaved)",
        "blender": bpy.app.version_string,
        "scene": scene.name,
        "scene_issues": [],
        "objects": [],
        "totals": {"objects": 0, "meshes": 0, "tris": 0, "materials": 0},
        "summary": {"error": 0, "warning": 0, "info": 0},
    }
    si = report["scene_issues"]

    us = scene.unit_settings
    if us.system != "METRIC" or abs(us.scale_length - 1.0) > 1e-6:
        _issue(si, "warning", "unit_scale",
               f"Unit system {us.system}, scale {us.scale_length}. Engines expect metric with scale 1.0 "
               "(1 Blender unit = 1 m) unless you deliberately work in centimetres for Unreal.")

    for img in bpy.data.images:
        if img.source != "FILE" or img.packed_file is not None or not img.filepath:
            continue
        path = bpy.path.abspath(img.filepath)
        if not os.path.exists(path):
            _issue(si, "error", "missing_texture", f"Image '{img.name}' points to missing file {img.filepath}")

    objs = list(bpy.context.selected_objects) if selected_only else list(scene.objects)
    used_materials = set()

    for obj in objs:
        entry = {"name": obj.name, "type": obj.type, "issues": []}
        iss = entry["issues"]
        report["totals"]["objects"] += 1

        if DUP_SUFFIX.search(obj.name):
            _issue(iss, "info", "dup_name", "Name ends in .001-style suffix; rename for clean engine node names.")
        if not SAFE_NAME.match(obj.name):
            _issue(iss, "warning", "unsafe_name",
                   "Name has spaces or non-ASCII characters; some engines and file systems mangle these.")

        if obj.type in {"MESH", "ARMATURE"}:
            sc = obj.scale
            if any(s < 0 for s in sc):
                _issue(iss, "error", "negative_scale",
                       f"Negative scale {tuple(round(s, 3) for s in sc)} flips normals in engines. Apply scale (Ctrl+A).")
            elif any(abs(s - 1.0) > 1e-4 for s in sc):
                _issue(iss, "warning", "unapplied_scale",
                       f"Scale {tuple(round(s, 3) for s in sc)} not applied. Apply scale (Ctrl+A) so colliders and physics match.")
            if not _is_identity_rot(obj):
                _issue(iss, "info", "unapplied_rotation",
                       "Rotation not applied. Fine for placed props; apply it for assets meant to be instanced.")

        if obj.type == "MESH":
            report["totals"]["meshes"] += 1
            st = _mesh_stats(obj, depsgraph)
            entry["stats"] = st
            report["totals"]["tris"] += st["tris"]
            if st["uv_layers"] == 0:
                _issue(iss, "error", "no_uv", "No UV map: textures and lightmaps cannot work.")
            if st["ngons"]:
                _issue(iss, "warning", "ngons",
                       f"{st['ngons']} n-gons; engines triangulate them unpredictably. Triangulate or fix topology.")
            if st["loose_verts"]:
                _issue(iss, "warning", "loose_verts", f"{st['loose_verts']} loose vertices (Mesh > Clean Up > Delete Loose).")
            if st["non_manifold_edges"]:
                _issue(iss, "warning", "non_manifold",
                       f"{st['non_manifold_edges']} non-manifold edges; bad for physics colliders, lightmaps and 3D printing.")
            if st["zero_area_faces"]:
                _issue(iss, "warning", "degenerate",
                       f"{st['zero_area_faces']} zero-area faces (Mesh > Clean Up > Degenerate Dissolve).")
            if max_tris is not None and st["tris"] > max_tris:
                _issue(iss, "warning", "over_budget", f"{st['tris']} tris exceeds budget {max_tris}.")
            if not obj.material_slots:
                _issue(iss, "info", "no_material", "No material; engine will use its default.")
            for slot in obj.material_slots:
                if slot.material is None:
                    _issue(iss, "warning", "empty_slot", "Empty material slot; faces assigned to it get no material.")
                else:
                    used_materials.add(slot.material.name)
            if len(obj.material_slots) > 4:
                _issue(iss, "info", "many_materials",
                       f"{len(obj.material_slots)} material slots = at least that many draw calls per instance.")
            for mod in obj.modifiers:
                if not mod.show_render and mod.show_viewport:
                    _issue(iss, "info", "modifier_viewport_only",
                           f"Modifier '{mod.name}' is viewport-only; exporters may skip or include it differently.")

        if obj.type == "ARMATURE":
            bones = obj.data.bones
            entry["stats"] = {"bones": len(bones)}
            if obj.name == "Armature" or obj.data.name == "Armature":
                _issue(iss, "info", "armature_name",
                       "Armature named 'Armature': Unreal's FBX importer treats it specially; give it a unique name.")
            if len(bones) > 255:
                _issue(iss, "warning", "bone_count", f"{len(bones)} bones; many mobile pipelines cap at 75-255.")

        if iss or obj.type == "MESH":
            report["objects"].append(entry)

    report["totals"]["materials"] = len(used_materials)
    for group in [si] + [o["issues"] for o in report["objects"]]:
        for i in group:
            report["summary"][i["severity"]] += 1
    return report


def _main(argv):
    import argparse

    args = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser(prog="scene_audit.py")
    ap.add_argument("--selected", action="store_true")
    ap.add_argument("--max-tris", type=int, default=None)
    ap.add_argument("--json", default=None, help="also write the report to this file")
    ns = ap.parse_args(args)
    rep = audit(ns.selected, ns.max_tris)
    text = json.dumps(rep, indent=1)
    if ns.json:
        with open(ns.json, "w", encoding="utf-8") as fh:
            fh.write(text)
    print("AUDIT_JSON_BEGIN")
    print(text)
    print("AUDIT_JSON_END")


if __name__ == "__main__" and "--" in sys.argv:
    _main(sys.argv)
