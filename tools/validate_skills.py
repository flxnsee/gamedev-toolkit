#!/usr/bin/env python3
"""Validate the gamedev-doctor repo: marketplace, plugin manifests and every SKILL.md.

Checks the Agent Skills spec (https://agentskills.io/specification): name format and
directory match, description length, compatibility length, body under 500 lines, and that
relative links and scripts/ / assets/ / references/ paths mentioned in SKILL.md exist.
Standard library only. Exit 1 on any error.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\]\(([^)#\s]+)\)")
PATH_RE = re.compile(r"`((?:scripts|assets|references)/[^`\s]+)`")


def parse_frontmatter(text: str) -> tuple[dict, str, list[str]]:
    errs: list[str] = []
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, text, ["missing YAML frontmatter (file must start with ---)"]
    lines = text.splitlines()
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return {}, text, ["frontmatter not closed with ---"]
    fm: dict = {}
    current_map: dict | None = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indented = raw.startswith((" ", "\t"))
        m = re.match(r"^\s*([A-Za-z0-9_-]+):\s*(.*)$", raw)
        if not m:
            errs.append(f"unparseable frontmatter line: {raw!r}")
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if indented and current_map is not None:
            current_map[key] = val
        elif val == "":
            current_map = fm.setdefault(key, {})
        else:
            current_map = None
            fm[key] = val
    body = "\n".join(lines[end + 1:])
    return fm, body, errs


def validate_skill(skill_md: Path) -> list[str]:
    errs: list[str] = []
    d = skill_md.parent
    fm, body, perrs = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    errs += perrs
    name = fm.get("name", "")
    if not name:
        errs.append("missing name")
    else:
        if len(name) > 64 or not NAME_RE.match(name):
            errs.append(f"invalid name {name!r} (lowercase, digits, single hyphens, max 64)")
        if name != d.name:
            errs.append(f"name {name!r} does not match directory {d.name!r}")
    desc = fm.get("description", "")
    if not desc:
        errs.append("missing description")
    elif len(desc) > 1024:
        errs.append(f"description is {len(desc)} chars (max 1024)")
    elif len(desc) < 80:
        errs.append("description is too short to trigger reliably (< 80 chars); say what AND when")
    comp = fm.get("compatibility")
    if comp is not None and not (1 <= len(comp) <= 500):
        errs.append("compatibility must be 1-500 chars")
    meta = fm.get("metadata")
    if meta is not None and not isinstance(meta, dict):
        errs.append("metadata must be a map")
    n_lines = body.count("\n") + 1
    if n_lines > 500:
        errs.append(f"body is {n_lines} lines (keep SKILL.md under 500; move detail to references/)")
    for target in LINK_RE.findall(body) + PATH_RE.findall(body):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if not (d / target).exists():
            errs.append(f"referenced file does not exist: {target}")
    return errs


def main() -> int:
    errors: list[str] = []
    mp_path = ROOT / ".claude-plugin" / "marketplace.json"
    mp = json.loads(mp_path.read_text(encoding="utf-8"))
    for field in ("name", "owner", "plugins"):
        if field not in mp:
            errors.append(f"marketplace.json: missing {field}")
    listed = set()
    for i, entry in enumerate(mp.get("plugins", [])):
        src = entry.get("source", "")
        where = f"marketplace.json plugins[{i}] ({entry.get('name')})"
        if ".." in src:
            errors.append(f"{where}: source must not contain '..'")
            continue
        pdir = (ROOT / src).resolve()
        listed.add(pdir)
        manifest = pdir / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            errors.append(f"{where}: {manifest.relative_to(ROOT)} missing")
            continue
        pj = json.loads(manifest.read_text(encoding="utf-8"))
        if pj.get("name") != entry.get("name"):
            errors.append(f"{where}: plugin.json name {pj.get('name')!r} != entry name")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(pj.get("version", ""))):
            errors.append(f"{where}: plugin.json version must be semver")
        if not list((pdir / "skills").glob("*/SKILL.md")):
            errors.append(f"{where}: no skills/*/SKILL.md")

    for pdir in sorted((ROOT / "plugins").iterdir()):
        if pdir.is_dir() and pdir.resolve() not in listed:
            errors.append(f"plugins/{pdir.name} is not listed in marketplace.json")

    seen: dict[str, Path] = {}
    count = 0
    for skill_md in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        count += 1
        rel = skill_md.relative_to(ROOT).as_posix()
        for e in validate_skill(skill_md):
            errors.append(f"{rel}: {e}")
        name = skill_md.parent.name
        if name in seen:
            errors.append(f"{rel}: duplicate skill name, also in {seen[name].relative_to(ROOT)}")
        seen[name] = skill_md

    if errors:
        print(f"FAILED: {len(errors)} problem(s)")
        for e in errors:
            print("  - " + e)
        return 1
    print(f"OK: {len(mp.get('plugins', []))} plugins, {count} skills valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
