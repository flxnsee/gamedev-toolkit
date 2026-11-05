#!/usr/bin/env python3
"""Static linter for Godot 4 projects. No Godot install needed; standard library only.

Checks:
  * GDScript written for Godot 3 that breaks in Godot 4 (onready, export, yield, setget,
    old connect(), renamed classes and functions, move_and_slide(args), rect_* ...)
  * res:// references (ext_resource, preload/load, autoloads, main scene) that point to
    missing files, with UID fallback detection
  * res:// paths whose letter case differs from the file on disk (works in the editor on
    Windows/macOS, breaks in exported .pck builds and on Linux)

Usage:
  python godot_lint.py [PROJECT_DIR] [--json] [--include-addons] [--max N]
Exit code: 0 = no errors, 1 = errors found, 2 = not a Godot project.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SKIP_DIRS = {".godot", ".import", ".git", ".svn", "android", "build", "builds", ".vs", ".vscode"}


@dataclass
class Finding:
    severity: str  # error | warning | info
    code: str
    file: str
    line: int
    message: str


# ---------------------------------------------------------------- GDScript tokenizing

def split_code(line: str, in_triple: str | None):
    """Return (code_with_strings, code_with_blanked_strings, in_triple_after).

    Comments are removed. Inside the blanked version string contents become 'x' so
    regexes can still see that a string literal exists without matching its text.
    """
    kept, blank = [], []
    i, n = 0, len(line)
    quote = in_triple
    while i < n:
        ch = line[i]
        if quote:
            if quote in ('"""', "'''"):
                if line.startswith(quote, i):
                    kept.append(quote); blank.append(quote); i += 3; quote = None
                    continue
            elif ch == "\\" and i + 1 < n:
                kept.append(line[i:i + 2]); blank.append("xx"); i += 2
                continue
            elif ch == quote:
                kept.append(ch); blank.append(ch); i += 1; quote = None
                continue
            kept.append(ch); blank.append("x"); i += 1
            continue
        if ch == "#":
            break
        if line.startswith('"""', i) or line.startswith("'''", i):
            quote = line[i:i + 3]; kept.append(quote); blank.append(quote); i += 3
            continue
        if ch in "\"'":
            quote = ch; kept.append(ch); blank.append(ch); i += 1
            continue
        kept.append(ch); blank.append(ch); i += 1
    after = quote if quote in ('"""', "'''") else None
    return "".join(kept), "".join(blank), after


# ---------------------------------------------------------------- Godot 3 -> 4 rules

RULES: list[tuple[str, re.Pattern, str]] = []


def rule(code: str, pattern: str, message: str) -> None:
    RULES.append((code, re.compile(pattern), message))


rule("gd3-onready", r"^\s*onready\s+var\b", "`onready var` is Godot 3. Use `@onready var`.")
rule("gd3-export", r"^\s*export(\s*\(.*?\))?\s+var\b", "`export var` is Godot 3. Use `@export var` (typed: `@export var speed: float = 5.0`).")
rule("gd3-tool", r"^\s*tool\s*$", "`tool` is Godot 3. Use `@tool` on the first line.")
rule("gd3-yield", r"\byield\s*\(", "`yield()` was removed. Use `await obj.signal_name` or `await get_tree().create_timer(t).timeout`.")
rule("gd3-setget", r"\bsetget\b", "`setget` was removed. Use `var x: int: set = _set_x, get = _get_x` or inline `set(value):` blocks.")
rule("gd3-connect", r"\bconnect\(\s*\"[^\"]*\"\s*,\s*self\s*,", "Old `connect(\"sig\", self, \"method\")`. Use `sig.connect(_method)`.")
rule("gd3-rpc", r"^\s*(remote|master|puppet|remotesync|mastersync|puppetsync)\s+func\b", "RPC keywords were replaced by the `@rpc(...)` annotation.")
rule("gd3-move-and-slide", r"\bmove_and_slide\(\s*[^)\s]", "Godot 4 `move_and_slide()` takes no arguments: set the `velocity` property, then call `move_and_slide()`.")
rule("gd3-instance", r"\.instance\(\s*\)", "`PackedScene.instance()` was renamed to `instantiate()`.")
rule("gd3-change-scene", r"\bchange_scene\(", "`change_scene()` was renamed to `change_scene_to_file()`.")
rule("gd3-rect", r"\brect_(position|size|min_size|rotation|scale|pivot_offset|global_position|clip_content)\b", "Control `rect_*` properties lost the prefix in Godot 4 (`position`, `size`, `custom_minimum_size`, ...).")
rule("gd3-empty", r"\.empty\(\s*\)", "`.empty()` was renamed to `.is_empty()`.")
rule("gd3-file", r"\b(File|Directory)\.new\(\s*\)", "`File`/`Directory` were replaced by `FileAccess.open()` / `DirAccess.open()`.")
rule("gd3-tween-node", r"\bTween\.new\(\s*\)", "Tween is no longer a Node. Use `var t := create_tween()`.")
rule("gd3-funcref", r"\bfuncref\(", "`funcref()` was removed. Use a Callable: `Callable(obj, \"method\")` or just `obj.method`.")
rule("gd3-json", r"\b(to_json|parse_json)\(", "Use `JSON.stringify()` / `JSON.parse_string()`.")
rule("gd3-ticks", r"\bOS\.(get_ticks_msec|get_ticks_usec|get_unix_time|get_datetime|get_system_time_msecs)\b", "Time functions moved from `OS` to `Time` (e.g. `Time.get_ticks_msec()`).")
rule("gd3-pool", r"\bPool(Byte|Int|Real|String|Vector2|Vector3|Color)Array\b", "`Pool*Array` types were renamed to `Packed*Array` (PoolRealArray -> PackedFloat32Array).")
rule("gd3-mouse", r"\bBUTTON_(LEFT|RIGHT|MIDDLE|WHEEL_UP|WHEEL_DOWN)\b", "Mouse constants are now `MOUSE_BUTTON_*`.")
rule("gd3-key", r"\bKEY_CONTROL\b", "`KEY_CONTROL` is now `KEY_CTRL`.")

FUNC_RENAMES = {
    "rand_range": "randf_range", "deg2rad": "deg_to_rad", "rad2deg": "rad_to_deg",
    "stepify": "snapped", "range_lerp": "remap", "str2var": "str_to_var", "var2str": "var_to_str",
    "bytes2var": "bytes_to_var", "var2bytes": "var_to_bytes", "linear2db": "linear_to_db",
    "db2linear": "db_to_linear", "polar2cartesian": "Vector2.from_angle / polar math",
    "cartesian2polar": "angle()/length()", "dict2inst": "dict_to_inst", "inst2dict": "inst_to_dict",
}
rule("gd3-func", r"\b(" + "|".join(FUNC_RENAMES) + r")\s*\(", "Renamed global function (see message suffix).")

CLASS_RENAMES = {
    "KinematicBody2D": "CharacterBody2D", "KinematicBody": "CharacterBody3D", "Spatial": "Node3D",
    "RigidBody": "RigidBody3D", "StaticBody": "StaticBody3D", "Area": "Area3D",
    "CollisionShape": "CollisionShape3D", "CollisionPolygon": "CollisionPolygon3D",
    "MeshInstance": "MeshInstance3D", "Camera": "Camera3D", "Position2D": "Marker2D",
    "Position3D": "Marker3D", "Particles": "GPUParticles3D", "Particles2D": "GPUParticles2D",
    "CPUParticles": "CPUParticles3D", "Light": "Light3D", "DirectionalLight": "DirectionalLight3D",
    "OmniLight": "OmniLight3D", "SpotLight": "SpotLight3D", "RayCast": "RayCast3D",
    "VisibilityNotifier2D": "VisibleOnScreenNotifier2D", "VisibilityNotifier": "VisibleOnScreenNotifier3D",
    "YSort": "Node2D (y_sort_enabled = true)", "Navigation2D": "NavigationServer2D / NavigationRegion2D",
    "TextureRect": None, "ToolButton": "Button (flat = true)", "Path": "Path3D", "PathFollow": "PathFollow3D",
    "GIProbe": "VoxelGI", "BakedLightmap": "LightmapGI", "ARVROrigin": "XROrigin3D", "ARVRCamera": "XRCamera3D",
}
CLASS_RENAMES = {k: v for k, v in CLASS_RENAMES.items() if v}
_cls = "|".join(sorted(CLASS_RENAMES, key=len, reverse=True))
CLASS_RE = re.compile(r"(?:\bextends\s+|\bis\s+|\bas\s+|:\s*|->\s*)(" + _cls + r")\b(?!\s*\()|\b(" + _cls + r")\.new\(")


def lint_gdscript(path: Path, rel: str, out: list[Finding]) -> list[tuple[int, str]]:
    """Return list of (line_no, res_path) literal load/preload references."""
    refs: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        out.append(Finding("error", "read-failed", rel, 0, str(e)))
        return refs
    triple = None
    for no, raw in enumerate(text.splitlines(), 1):
        kept, blank, triple_after = split_code(raw, triple)
        was_in_triple = triple is not None
        triple = triple_after
        if was_in_triple and triple is not None:
            continue
        for code, pat, msg in RULES:
            target = kept if code == "gd3-connect" else blank
            if code == "gd3-func":
                for m in pat.finditer(target):
                    out.append(Finding("error", code, rel, no,
                                       f"`{m.group(1)}()` was renamed to `{FUNC_RENAMES[m.group(1)]}`."))
            elif pat.search(target):
                out.append(Finding("error", code, rel, no, msg))
        for m in CLASS_RE.finditer(blank):
            old = m.group(1) or m.group(2)
            out.append(Finding("error", "gd3-class", rel, no, f"`{old}` is a Godot 3 class. Godot 4 name: `{CLASS_RENAMES[old]}`."))
        for m in re.finditer(r"\b(?:preload|load)\(\s*[\"'](res://[^\"']+)[\"']\s*\)", kept):
            refs.append((no, m.group(1)))
    return refs


# ---------------------------------------------------------------- res:// resolution

class Resolver:
    def __init__(self, root: Path):
        self.root = root
        self._dir_cache: dict[Path, dict[str, str]] = {}

    def _listing(self, d: Path) -> dict[str, str]:
        if d not in self._dir_cache:
            try:
                self._dir_cache[d] = {n.lower(): n for n in os.listdir(d)}
            except OSError:
                self._dir_cache[d] = {}
        return self._dir_cache[d]

    def check(self, res_path: str) -> tuple[str, str | None]:
        """Return (status, actual_case_path). status: ok | missing | case."""
        rel = res_path[len("res://"):].split("::", 1)[0]
        if not rel:
            return "ok", None
        parts = [p for p in rel.split("/") if p not in ("", ".")]
        cur = self.root
        actual = []
        case_bad = False
        for p in parts:
            if p == "..":
                cur = cur.parent; actual.append(p); continue
            listing = self._listing(cur)
            real = listing.get(p.lower())
            if real is None:
                return "missing", None
            if real != p:
                case_bad = True
            actual.append(real)
            cur = cur / real
        return ("case" if case_bad else "ok"), "res://" + "/".join(actual)


UID_RE = re.compile(r"uid=\"(uid://[a-z0-9]+)\"")
EXT_RES_RE = re.compile(r"^\[ext_resource\b(.*)\]\s*$")
ATTR_RE = re.compile(r"(\w+)=\"([^\"]*)\"")


def build_uid_index(root: Path, files: list[Path]) -> set[str]:
    uids: set[str] = set()
    for f in files:
        suf = f.suffix.lower()
        try:
            if suf == ".uid":
                uids.add(f.read_text(encoding="utf-8", errors="replace").strip())
            elif suf in (".import", ".tscn", ".tres"):
                with f.open(encoding="utf-8", errors="replace") as fh:
                    head = fh.read(4096) if suf != ".import" else fh.read()
                for m in UID_RE.finditer(head if suf == ".import" else head.split("\n", 1)[0]):
                    uids.add(m.group(1))
        except OSError:
            pass
    return uids


def iter_project_files(root: Path, include_addons: bool):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
                       and (include_addons or not (rel_dir == Path(".") and d == "addons"))]
        # A nested project.godot means a separate project: skip it.
        if rel_dir != Path(".") and "project.godot" in filenames:
            dirnames[:] = []
            continue
        for fn in filenames:
            yield Path(dirpath) / fn


def lint_project(root: Path, include_addons: bool = False) -> dict:
    root = root.resolve()
    findings: list[Finding] = []
    pg = root / "project.godot"
    if not pg.is_file():
        raise FileNotFoundError(f"{root} has no project.godot")

    pg_text = pg.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^config_version=(\d+)", pg_text, re.M)
    config_version = int(m.group(1)) if m else None
    godot_major = 4 if config_version == 5 else (3 if config_version == 4 else None)
    if godot_major == 3:
        findings.append(Finding("info", "godot3-project", "project.godot", 0,
                                "config_version=4 means a Godot 3 project. Godot 3->4 rules skipped; use the editor's Project > Tools > Upgrade Project or run Godot 4 with --convert-3to4."))

    files = list(iter_project_files(root, include_addons))
    resolver = Resolver(root)
    uids = build_uid_index(root, files)
    refs: list[tuple[str, int, str, str | None]] = []  # (file, line, res_path, uid)

    # project.godot references: main scene, autoloads, icon
    in_autoload = False
    for no, line in enumerate(pg_text.splitlines(), 1):
        s = line.strip()
        if s.startswith("["):
            in_autoload = s == "[autoload]"
            continue
        if in_autoload or s.startswith(("run/main_scene=", "config/icon=")):
            for mm in re.finditer(r"\"\*?(res://[^\"]+)\"", s):
                refs.append(("project.godot", no, mm.group(1), None))

    stats = {"gd_files": 0, "scenes": 0, "resources": 0}
    for f in files:
        rel = f.relative_to(root).as_posix()
        suf = f.suffix.lower()
        if suf == ".gd":
            stats["gd_files"] += 1
            local: list[Finding] = []
            file_refs = lint_gdscript(f, rel, local)
            if godot_major != 3:
                findings.extend(local)
            refs.extend((rel, no, p, None) for no, p in file_refs)
        elif suf in (".tscn", ".tres"):
            stats["scenes" if suf == ".tscn" else "resources"] += 1
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for no, line in enumerate(lines, 1):
                em = EXT_RES_RE.match(line.strip())
                if not em:
                    continue
                attrs = dict(ATTR_RE.findall(em.group(1)))
                if "path" in attrs and attrs["path"].startswith("res://"):
                    refs.append((rel, no, attrs["path"], attrs.get("uid")))

    for rel, no, res_path, uid in refs:
        status, actual = resolver.check(res_path)
        if status == "missing":
            if uid and uid in uids:
                findings.append(Finding("warning", "stale-path", rel, no,
                                        f"{res_path} does not exist, but {uid} is known so Godot will load the moved file by UID. Open and re-save this file to refresh the path."))
            else:
                findings.append(Finding("error", "missing-resource", rel, no, f"{res_path} does not exist."))
        elif status == "case":
            findings.append(Finding("error", "path-case", rel, no,
                                    f"{res_path} differs in letter case from {actual}. Works in the editor on Windows/macOS, fails in exported builds and on Linux."))

    sev_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda x: (sev_order[x.severity], x.file, x.line))
    summary = {s: sum(1 for x in findings if x.severity == s) for s in ("error", "warning", "info")}
    return {
        "project": str(root),
        "godot_major": godot_major,
        "stats": stats,
        "references_checked": len(refs),
        "summary": summary,
        "findings": [asdict(x) for x in findings],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--include-addons", action="store_true", help="also lint res://addons (third-party code)")
    ap.add_argument("--max", type=int, default=200, help="max findings to print in text mode")
    a = ap.parse_args(argv)
    try:
        rep = lint_project(Path(a.project), a.include_addons)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        s = rep["summary"]
        print(f"Godot {rep['godot_major'] or '?'} project: {rep['stats']['gd_files']} scripts, "
              f"{rep['stats']['scenes']} scenes, {rep['stats']['resources']} resources, "
              f"{rep['references_checked']} res:// references checked")
        print(f"{s['error']} errors, {s['warning']} warnings, {s['info']} info")
        for f in rep["findings"][: a.max]:
            loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
            print(f"  [{f['severity']}] {loc} {f['code']}: {f['message']}")
        if len(rep["findings"]) > a.max:
            print(f"  ... {len(rep['findings']) - a.max} more (use --json for all)")
    return 1 if rep["summary"]["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
