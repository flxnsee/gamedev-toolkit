#!/usr/bin/env python3
"""Check a Unity project for .meta / GUID / serialization problems. Standard library only.

Checks:
  * assets or folders under Assets/ (and embedded packages) without a .meta file
  * orphan .meta files whose asset is gone
  * duplicate or malformed GUIDs (the cause of "references swapped / missing script" bugs)
  * scenes, prefabs and materials stored as binary instead of text YAML
  * Asset Serialization mode and meta-file visibility in EditorSettings.asset
  * .gitignore missing Library/ etc., and (if git is available) generated folders tracked

Usage:
  python unity_meta_check.py [PROJECT_DIR] [--json] [--max N]
Exit code: 0 = no errors, 1 = errors, 2 = not a Unity project.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

GUID_RE = re.compile(r"^guid:\s*(\S+)\s*$", re.M)
TEXT_YAML_EXT = {".unity", ".prefab", ".mat", ".anim", ".controller", ".overrideController", ".physicMaterial"}
GENERATED = ["Library", "Temp", "Obj", "Logs", "UserSettings", "Build", "Builds"]


@dataclass
class Finding:
    severity: str
    code: str
    path: str
    message: str


def unity_hidden(name: str) -> bool:
    """Unity's import rules: these files/folders are ignored and get no .meta."""
    low = name.lower()
    return name.startswith(".") or name.endswith("~") or low == "cvs" or low.endswith(".tmp")


def asset_roots(root: Path) -> list[Path]:
    roots = [root / "Assets"]
    pk = root / "Packages"
    if pk.is_dir():
        for d in sorted(pk.iterdir()):
            if d.is_dir() and (d / "package.json").is_file():
                roots.append(d)  # embedded package: needs .meta files like Assets/
    return roots


def walk_assets(base: Path):
    """Yield (path, is_dir) for every importable entry under base (not base itself)."""
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not unity_hidden(d))
        for d in dirnames:
            yield Path(dirpath) / d, True
        for f in sorted(filenames):
            if not unity_hidden(f):
                yield Path(dirpath) / f, False


def check(root: Path) -> dict:
    root = root.resolve()
    if not (root / "Assets").is_dir() or not (root / "ProjectSettings").is_dir():
        raise FileNotFoundError(f"{root} has no Assets/ and ProjectSettings/ - not a Unity project")
    findings: list[Finding] = []

    def rel(p: Path) -> str:
        return p.relative_to(root).as_posix()

    version = None
    pv = root / "ProjectSettings" / "ProjectVersion.txt"
    if pv.is_file():
        m = re.search(r"m_EditorVersion:\s*(\S+)", pv.read_text(encoding="utf-8", errors="replace"))
        version = m.group(1) if m else None

    guids: dict[str, list[str]] = {}
    stats = {"assets": 0, "metas": 0}
    for base in asset_roots(root):
        for path, is_dir in walk_assets(base):
            name = path.name
            if name.endswith(".meta"):
                stats["metas"] += 1
                target = path.with_name(name[:-5])
                if not target.exists():
                    findings.append(Finding("warning", "orphan-meta", rel(path),
                                            "Asset for this .meta is gone. Delete the .meta, or the asset was not committed."))
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    findings.append(Finding("error", "unreadable-meta", rel(path), str(e)))
                    continue
                gm = GUID_RE.search(text)
                if not gm:
                    findings.append(Finding("error", "no-guid", rel(path), ".meta has no guid line; Unity will regenerate it and break references."))
                elif not re.fullmatch(r"[0-9a-f]{32}", gm.group(1)):
                    findings.append(Finding("error", "bad-guid", rel(path), f"Malformed GUID '{gm.group(1)}'."))
                else:
                    guids.setdefault(gm.group(1), []).append(rel(path))
                continue
            stats["assets"] += 1
            meta = path.with_name(name + ".meta")
            if not meta.exists():
                kind = "Folder" if is_dir else "Asset"
                findings.append(Finding("error", "missing-meta", rel(path),
                                        f"{kind} has no .meta. Unity will create one with a NEW GUID on import, so references to it from other machines break. Commit the .meta."))
            if not is_dir and path.suffix in TEXT_YAML_EXT:
                try:
                    with path.open("rb") as fh:
                        head = fh.read(5)
                    if head and head != b"%YAML":
                        findings.append(Finding("warning", "binary-asset", rel(path),
                                                "Stored as binary, so Git can't diff or merge it. Set Asset Serialization to Force Text and re-save."))
                except OSError:
                    pass

    for guid, paths in guids.items():
        if len(paths) > 1:
            findings.append(Finding("error", "duplicate-guid", paths[0],
                                    f"GUID {guid} is shared by {len(paths)} files: {', '.join(paths)}. Usually from copying files with their .meta outside Unity. Delete the copy's .meta so Unity generates a new GUID."))

    es = root / "ProjectSettings" / "EditorSettings.asset"
    if es.is_file():
        text = es.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("%YAML"):
            findings.append(Finding("warning", "serialization-not-text", rel(es), "EditorSettings.asset is binary; Asset Serialization is not Force Text."))
        else:
            m = re.search(r"m_SerializationMode:\s*(\d+)", text)
            if m and m.group(1) != "2":
                findings.append(Finding("warning", "serialization-not-text", rel(es),
                                        f"m_SerializationMode is {m.group(1)}, not 2 (Force Text). Edit > Project Settings > Editor > Asset Serialization > Force Text."))
            m = re.search(r"m_ExternalVersionControlSupport:\s*(.+)", text)
            if m and "Hidden" in m.group(1):
                findings.append(Finding("error", "hidden-meta", rel(es), "Meta files are hidden; set Version Control mode to Visible Meta Files."))

    gi = None
    for cand in (root / ".gitignore", root.parent / ".gitignore"):
        if cand.is_file():
            gi = cand
            break
    if gi is None:
        findings.append(Finding("warning", "no-gitignore", ".gitignore", "No .gitignore: Library/, Temp/ and Logs/ will be committed."))
    else:
        gtext = gi.read_text(encoding="utf-8", errors="replace").lower()
        if "library" not in gtext:
            findings.append(Finding("warning", "gitignore-library", rel(gi) if gi.is_relative_to(root) else str(gi),
                                    ".gitignore does not mention Library/."))
        if re.search(r"^\s*\*\.meta\s*$", gtext, re.M):
            findings.append(Finding("error", "gitignore-meta", str(gi), ".gitignore excludes *.meta files. Never ignore .meta files."))

    tracked_generated = []
    if (shutil.which("git") and subprocess.run(["git", "-C", str(root), "rev-parse"], capture_output=True).returncode == 0):
        r = subprocess.run(["git", "-C", str(root), "ls-files", "--", *GENERATED], capture_output=True, text=True)
        tracked_generated = [l for l in r.stdout.splitlines() if l.strip()]
        if tracked_generated:
            top = sorted({l.split("/")[0] for l in tracked_generated})
            findings.append(Finding("error", "generated-tracked", ", ".join(top),
                                    f"{len(tracked_generated)} generated files are tracked by git. Run: git rm -r --cached {' '.join(top)}"))

    order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code, f.path))
    summary = {s: sum(1 for f in findings if f.severity == s) for s in ("error", "warning", "info")}
    return {"project": str(root), "unity_version": version, "stats": stats,
            "summary": summary, "findings": [asdict(f) for f in findings]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max", type=int, default=200)
    a = ap.parse_args(argv)
    try:
        rep = check(Path(a.project))
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        s = rep["summary"]
        print(f"Unity {rep['unity_version'] or '?'}: {rep['stats']['assets']} assets, {rep['stats']['metas']} .meta files")
        print(f"{s['error']} errors, {s['warning']} warnings")
        for f in rep["findings"][: a.max]:
            print(f"  [{f['severity']}] {f['code']}: {f['path']} - {f['message']}")
        if len(rep["findings"]) > a.max:
            print(f"  ... {len(rep['findings']) - a.max} more (use --json)")
    return 1 if rep["summary"]["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
