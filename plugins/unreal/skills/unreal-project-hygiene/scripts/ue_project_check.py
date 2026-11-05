#!/usr/bin/env python3
"""Sanity-check an Unreal Engine project folder without opening the editor. Stdlib only.

Checks:
  * .uproject is valid JSON; engine association; modules have Source/<Module>/<Module>.Build.cs
  * Target.cs files exist for C++ projects (Game + Editor)
  * project plugins: enabled plugins that exist in Plugins/ have a .uplugin; local plugins
    with Source/ but no prebuilt Binaries/ (teammates without a compiler can't open them)
  * each *.Build.cs / *.h quick lint: .generated.h must be the last include; UCLASS/USTRUCT
    without GENERATED_BODY; raw UObject* members without UPROPERTY (GC can free them)
  * .gitignore covers Binaries/Intermediate/Saved/DerivedDataCache; .gitattributes puts
    .uasset/.umap in Git LFS; (if git available) generated folders tracked

Usage:
  python ue_project_check.py [PROJECT_DIR] [--json] [--max N]
Exit code: 0 = no errors, 1 = errors, 2 = no .uproject found.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

GENERATED = ["Binaries", "Intermediate", "Saved", "DerivedDataCache"]
UOBJECT_PTR = re.compile(r"^\s*(?:class\s+)?([AU][A-Z]\w*)\s*\*\s*(\w+)\s*(?:=\s*[^;]+)?;")
TOBJECTPTR = re.compile(r"^\s*TObjectPtr<\s*(?:class\s+)?\w+\s*>\s*\w+")
UPROP = re.compile(r"^\s*UPROPERTY\s*\(")
TYPE_MACRO = re.compile(r"^\s*(UCLASS|USTRUCT|UINTERFACE)\s*\(")


@dataclass
class Finding:
    severity: str
    code: str
    path: str
    line: int
    message: str


def lint_header(path: Path, rel: str, out: list[Finding]) -> None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    includes = [(i, l) for i, l in enumerate(lines, 1) if l.strip().startswith("#include")]
    gen = [(i, l) for i, l in includes if ".generated.h" in l]
    if gen and includes[-1][0] != gen[-1][0]:
        out.append(Finding("error", "generated-include-order", rel, gen[-1][0],
                           "The .generated.h include must be the last #include in the header (UHT error otherwise)."))
    has_type_macro = any(TYPE_MACRO.match(l) for l in lines)
    if has_type_macro and gen == []:
        out.append(Finding("error", "missing-generated-include", rel, 1,
                           f"Header declares a UCLASS/USTRUCT but doesn't include \"{path.stem}.generated.h\"."))
    # GENERATED_BODY after each UCLASS/USTRUCT
    for i, l in enumerate(lines):
        if TYPE_MACRO.match(l):
            window = "\n".join(lines[i:i + 12])
            if "GENERATED_BODY" not in window and "GENERATED_UCLASS_BODY" not in window and "GENERATED_USTRUCT_BODY" not in window:
                out.append(Finding("error", "missing-generated-body", rel, i + 1,
                                   "UCLASS/USTRUCT without GENERATED_BODY() in its body."))
    # raw UObject pointers without UPROPERTY inside class bodies (heuristic)
    depth = 0
    in_type = False
    for i, l in enumerate(lines):
        s = l.strip()
        if TYPE_MACRO.match(l):
            in_type = True
        if in_type and depth >= 1 and not s.startswith(("//", "*", "/*")):
            m = UOBJECT_PTR.match(l)
            prev = next((lines[j] for j in range(i - 1, max(i - 4, -1), -1) if lines[j].strip()), "")
            if m and not UPROP.match(prev) and "(" not in l and "static" not in l and "friend" not in l:
                out.append(Finding("warning", "raw-uobject-member", rel, i + 1,
                                   f"`{m.group(1)}* {m.group(2)}` has no UPROPERTY(): the garbage collector does not see it and may free the object. Use `UPROPERTY() TObjectPtr<{m.group(1)}> {m.group(2)};` (or TWeakObjectPtr if it must not keep it alive)."))
        depth += l.count("{") - l.count("}")
        if depth <= 0:
            depth = 0
            if in_type and "}" in l:
                in_type = False


def check(root: Path) -> dict:
    root = root.resolve()
    ups = sorted(root.glob("*.uproject"))
    if not ups:
        raise FileNotFoundError(f"no .uproject in {root}")
    up = ups[0]
    findings: list[Finding] = []

    def rel(p: Path) -> str:
        return p.relative_to(root).as_posix()

    try:
        data = json.loads(up.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        findings.append(Finding("error", "uproject-json", up.name, e.lineno, f"Invalid JSON: {e.msg}"))
        data = {}

    engine = data.get("EngineAssociation", "")
    if engine and re.fullmatch(r"\{[0-9A-Fa-f-]+\}", engine):
        findings.append(Finding("info", "source-engine", up.name, 0,
                                f"EngineAssociation {engine} is a source-built engine GUID; teammates need the same engine build."))

    modules = data.get("Modules", [])
    for mod in modules:
        name = mod.get("Name", "")
        bc = root / "Source" / name / f"{name}.Build.cs"
        if not bc.is_file():
            findings.append(Finding("error", "module-missing", up.name, 0, f"Module '{name}' listed but {rel(bc) if bc.is_relative_to(root) else bc} is missing."))
    if modules:
        targets = list((root / "Source").glob("*.Target.cs"))
        names = {t.name for t in targets}
        if not any(n.endswith("Editor.Target.cs") for n in names):
            findings.append(Finding("error", "no-editor-target", "Source", 0, "C++ project has no <Name>Editor.Target.cs; the editor can't be built."))
        if not any(not n.endswith("Editor.Target.cs") and not n.endswith("Server.Target.cs") and not n.endswith("Client.Target.cs") for n in names):
            findings.append(Finding("warning", "no-game-target", "Source", 0, "No game <Name>.Target.cs; packaging will fail."))

    plugins_dir = root / "Plugins"
    local_plugins = {p.stem: p for p in plugins_dir.rglob("*.uplugin")} if plugins_dir.is_dir() else {}
    for pl in data.get("Plugins", []):
        name = pl.get("Name")
        if pl.get("Enabled") and name in local_plugins:
            pdir = local_plugins[name].parent
            if (pdir / "Source").is_dir() and not (pdir / "Binaries").is_dir():
                findings.append(Finding("info", "plugin-unbuilt", rel(pdir), 0,
                                        f"Plugin '{name}' has Source/ but no Binaries/; it compiles on first open (needs a C++ toolchain)."))
    for name, upl in local_plugins.items():
        try:
            json.loads(upl.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            findings.append(Finding("error", "uplugin-json", rel(upl), e.lineno, f"Invalid JSON: {e.msg}"))

    stats = {"modules": len(modules), "headers": 0, "local_plugins": len(local_plugins)}
    for src in [root / "Source"] + [p.parent / "Source" for p in local_plugins.values()]:
        if not src.is_dir():
            continue
        for h in src.rglob("*.h"):
            if "ThirdParty" in h.parts:
                continue
            stats["headers"] += 1
            lint_header(h, rel(h), findings)

    gi = root / ".gitignore"
    if not gi.is_file():
        findings.append(Finding("warning", "no-gitignore", ".gitignore", 0, "No .gitignore: Binaries/, Intermediate/, Saved/, DerivedDataCache/ would be committed."))
    else:
        t = gi.read_text(encoding="utf-8", errors="replace")
        missing = [g for g in GENERATED if g.lower() not in t.lower()]
        if missing:
            findings.append(Finding("warning", "gitignore-incomplete", ".gitignore", 0, f".gitignore doesn't mention: {', '.join(missing)}"))
    ga = root / ".gitattributes"
    ga_text = ga.read_text(encoding="utf-8", errors="replace") if ga.is_file() else ""
    for ext in ("uasset", "umap"):
        if not re.search(rf"\*\.{ext}\b[^\n]*filter=lfs", ga_text):
            findings.append(Finding("warning", "no-lfs", ".gitattributes", 0,
                                    f"*.{ext} is not tracked by Git LFS. Binary assets bloat the repo and GitHub rejects files over 100 MB."))

    if shutil.which("git") and subprocess.run(["git", "-C", str(root), "rev-parse"], capture_output=True).returncode == 0:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "--", *GENERATED], capture_output=True, text=True)
        tracked = [l for l in r.stdout.splitlines() if l.strip()]
        if tracked:
            top = sorted({l.split("/")[0] for l in tracked})
            findings.append(Finding("error", "generated-tracked", ", ".join(top), 0,
                                    f"{len(tracked)} generated files tracked. Run: git rm -r --cached {' '.join(top)}"))

    order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (order[f.severity], f.path, f.line))
    summary = {s: sum(1 for f in findings if f.severity == s) for s in ("error", "warning", "info")}
    return {"project": str(up), "engine": engine or None, "stats": stats,
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
        print(f"{Path(rep['project']).name} (engine {rep['engine'] or '?'}): {rep['stats']['modules']} modules, "
              f"{rep['stats']['headers']} headers, {rep['stats']['local_plugins']} local plugins")
        print(f"{s['error']} errors, {s['warning']} warnings, {s['info']} info")
        for f in rep["findings"][: a.max]:
            loc = f"{f['path']}:{f['line']}" if f["line"] else f["path"]
            print(f"  [{f['severity']}] {loc} {f['code']}: {f['message']}")
    return 1 if rep["summary"]["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
