#!/usr/bin/env python3
"""Generate .gitignore and .gitattributes (with Git LFS rules) for game projects.

Usage:
  python gen_repo_files.py --engine godot [--engine blender] [--out DIR]
                           [--dry-run] [--force | --merge]

Without --force or --merge an existing file is left untouched and reported.
--merge appends only lines that are missing. Standard library only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MARKER = "# --- added by gamedev-doctor ---"

COMMON_IGNORE = [
    "# OS / editor junk",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    ".vscode/*",
    "!.vscode/settings.json",
    "!.vscode/extensions.json",
    ".idea/",
    "*.swp",
    "*.tmp",
]

IGNORE = {
    "godot": [
        "# Godot 4",
        ".godot/",
        "/android/",
        "*.translation",
        "export.cfg",
        "export_credentials.cfg",
        "# Builds",
        "/build/",
        "/builds/",
    ],
    "unity": [
        "# Unity generated",
        "/[Ll]ibrary/",
        "/[Tt]emp/",
        "/[Oo]bj/",
        "/[Bb]uild/",
        "/[Bb]uilds/",
        "/[Ll]ogs/",
        "/[Uu]ser[Ss]ettings/",
        "/[Mm]emoryCaptures/",
        "/[Rr]ecordings/",
        "/Assets/Plugins/Editor/JetBrains*",
        "# IDE generated",
        ".vs/",
        ".consulo/",
        "*.csproj",
        "*.unityproj",
        "*.sln",
        "*.suo",
        "*.user",
        "*.userprefs",
        "*.pidb",
        "*.booproj",
        "*.svd",
        "*.pdb",
        "*.mdb",
        "*.opendb",
        "*.VC.db",
        "*.pidb.meta",
        "*.pdb.meta",
        "*.mdb.meta",
        "# Crash reports and build artifacts",
        "sysinfo.txt",
        "*.apk",
        "*.aab",
        "*.unitypackage",
        "crashlytics-build.properties",
        "/[Aa]ssets/[Aa]ddressable[Aa]ssets[Dd]ata/*/*.bin*",
        "/[Aa]ssets/[Ss]treamingAssets/aa.meta",
        "/[Aa]ssets/[Ss]treamingAssets/aa/*",
    ],
    "unreal": [
        "# Unreal generated",
        "Binaries/",
        "DerivedDataCache/",
        "Intermediate/",
        "Saved/",
        "Build/*/",
        "!Build/*/Resources/",
        "Plugins/*/Binaries/",
        "Plugins/*/Intermediate/",
        "Plugins/**/Binaries/",
        "Plugins/**/Intermediate/",
        "# IDE generated",
        ".vs/",
        "*.sln",
        "*.suo",
        "*.opensdf",
        "*.sdf",
        "*.VC.db",
        "*.VC.opendb",
        "*.xcodeproj",
        "*.xcworkspace",
        ".vsconfig.user",
        "# Packaged builds (DLLs under Source/ThirdParty stay tracked on purpose)",
        "*.ipa",
        "*.apk",
        "*.aab",
    ],
    "blender": [
        "# Blender autosaves",
        "*.blend[0-9]",
        "*.blend[0-9][0-9]",
        "*.blend@",
        "/renders/",
    ],
}

# Binary extensions that belong in LFS for every engine.
LFS_COMMON = [
    # images
    "png", "jpg", "jpeg", "tga", "bmp", "gif", "psd", "psb", "tif", "tiff",
    "exr", "hdr", "dds", "ktx", "ktx2", "webp", "kra", "xcf", "ase", "aseprite",
    # audio
    "wav", "ogg", "mp3", "flac", "aif", "aiff", "bank",
    # video
    "mp4", "mov", "webm", "avi",
    # 3D
    "fbx", "obj", "blend", "glb", "dae", "3ds", "max", "ma", "mb", "abc", "usdc", "usdz", "vox",
    # fonts
    "ttf", "otf",
    # archives / misc binaries
    "zip", "7z", "pdf",
]

LFS_EXTRA = {
    "godot": ["res", "scn", "ctex"],
    "unity": ["cubemap", "unitypackage", "so"],
    "unreal": [],  # uasset/umap are added as lockable below
    "blender": [],
}

LOCKABLE = {"unreal": ["uasset", "umap"]}


def build_gitignore(engines: list[str]) -> list[str]:
    lines = list(COMMON_IGNORE)
    for e in engines:
        lines.append("")
        lines.extend(IGNORE[e])
    return lines


def build_gitattributes(engines: list[str]) -> list[str]:
    lines = [
        "# Normalize line endings for text files",
        "* text=auto eol=lf",
        "*.bat text eol=crlf",
        "*.cmd text eol=crlf",
        "*.ps1 text eol=crlf",
    ]
    if "unity" in engines:
        lines += [
            "",
            "# Unity YAML: merge with UnityYAMLMerge if configured",
            "*.unity text merge=unityyamlmerge eol=lf",
            "*.prefab text merge=unityyamlmerge eol=lf",
            "*.asset text merge=unityyamlmerge eol=lf",
            "*.meta text eol=lf",
        ]
    exts: list[str] = []
    for ext in LFS_COMMON + [x for e in engines for x in LFS_EXTRA[e]]:
        if ext not in exts:
            exts.append(ext)
    lines += ["", "# Git LFS: binary assets"]
    for ext in exts:
        lines.append(f"*.{ext} filter=lfs diff=lfs merge=lfs -text")
        upper = ext.upper()
        if upper != ext:
            lines.append(f"*.{upper} filter=lfs diff=lfs merge=lfs -text")
    for e in engines:
        if e in LOCKABLE:
            lines += ["", f"# Git LFS: {e} binary assets, lockable (git lfs lock <file>)"]
            for ext in LOCKABLE[e]:
                lines.append(f"*.{ext} filter=lfs diff=lfs merge=lfs -text lockable")
    return lines


def write(path: Path, lines: list[str], *, dry: bool, force: bool, merge: bool) -> str:
    content = "\n".join(lines).rstrip() + "\n"
    if dry:
        print(f"===== {path} =====")
        print(content)
        return "preview"
    if not path.exists() or force:
        path.write_text(content, encoding="utf-8", newline="\n")
        return "written"
    if not merge:
        return "exists (skipped; use --merge or --force)"
    existing = path.read_text(encoding="utf-8", errors="replace").splitlines()
    have = {l.strip() for l in existing}
    missing = [l for l in lines if l.strip() and not l.startswith("#") and l.strip() not in have]
    if not missing:
        return "already complete"
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        if existing and existing[-1].strip():
            fh.write("\n")
        fh.write(MARKER + "\n" + "\n".join(missing) + "\n")
    return f"merged ({len(missing)} lines added)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", action="append", choices=sorted(IGNORE), required=True)
    ap.add_argument("--out", default=".", help="project root (default: current dir)")
    ap.add_argument("--dry-run", action="store_true", help="print instead of writing")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--force", action="store_true", help="overwrite existing files")
    mode.add_argument("--merge", action="store_true", help="append missing lines to existing files")
    args = ap.parse_args(argv)

    engines = list(dict.fromkeys(args.engine))
    out = Path(args.out)
    if not args.dry_run and not out.is_dir():
        print(f"error: {out} is not a directory", file=sys.stderr)
        return 2
    for name, lines in ((".gitignore", build_gitignore(engines)), (".gitattributes", build_gitattributes(engines))):
        status = write(out / name, lines, dry=args.dry_run, force=args.force, merge=args.merge)
        if not args.dry_run:
            print(f"{name}: {status}")
    if not args.dry_run:
        print("next: run `git lfs install` once, then commit .gitignore and .gitattributes first")
    return 0


if __name__ == "__main__":
    sys.exit(main())
