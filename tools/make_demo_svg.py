#!/usr/bin/env python3
"""Render real godot_lint output on the test fixture as a terminal-style SVG for the README.

  python tools/make_demo_svg.py            # writes docs/demo-godot-lint.svg
"""
from __future__ import annotations

import importlib.util
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINT = ROOT / "plugins/godot/skills/godot-project-lint/scripts/godot_lint.py"
FIXTURE = ROOT / "tests/fixtures/godot4_project"
OUT = ROOT / "docs/demo-godot-lint.svg"

# Findings to show, in this order (code, file, line). All come from the real report.
PICK = [
    ("path-case", "scenes/main.tscn", 4),
    ("missing-resource", "scenes/main.tscn", 6),
    ("gd3-class", "scripts/player.gd", 1),
    ("gd3-onready", "scripts/player.gd", 4),
    ("gd3-connect", "scripts/player.gd", 11),
    ("gd3-move-and-slide", "scripts/player.gd", 17),
    ("gd3-yield", "scripts/player.gd", 18),
    ("stale-path", "scenes/main.tscn", 5),
]

MAX_COLS = 112
CHAR_W = 7.83   # Consolas-ish advance at 13px
LINE_H = 21
PAD_X, PAD_TOP = 22, 58

COLORS = {
    "bg": "#0d1117", "bar": "#161b22", "border": "#30363d", "text": "#c9d1d9",
    "dim": "#8b949e", "prompt": "#3fb950", "error": "#f85149", "warning": "#d29922",
    "path": "#79c0ff", "code": "#d2a8ff", "title": "#8b949e",
}


def load_lint():
    spec = importlib.util.spec_from_file_location("godot_lint", LINT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["godot_lint"] = mod
    spec.loader.exec_module(mod)
    return mod


def clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> int:
    lint = load_lint()
    rep = lint.lint_project(FIXTURE)
    by_key = {(f["code"], f["file"], f["line"]): f for f in rep["findings"]}
    missing = [k for k in PICK if k not in by_key]
    if missing:
        print(f"error: findings not in report: {missing}", file=sys.stderr)
        return 1

    s = rep["summary"]
    st = rep["stats"]
    rows: list[list[tuple[str, str]]] = [
        [("prompt", "$ "), ("text", "python godot_lint.py tests/fixtures/godot4_project")],
        [("text", f"Godot {rep['godot_major']} project: {st['gd_files']} scripts, {st['scenes']} scenes, "
                  f"{st['resources']} resources, {rep['references_checked']} res:// references checked")],
        [("error", f"{s['error']} errors"), ("text", ", "), ("warning", f"{s['warning']} warnings"),
         ("text", f", {s['info']} info")],
    ]
    for key in PICK:
        f = by_key[key]
        sev = f["severity"]
        loc = f"{f['file']}:{f['line']}"
        head = f"  [{sev}] "
        used = len(head) + len(loc) + 1 + len(f["code"]) + 2
        rows.append([
            (sev, head), ("path", loc), ("text", " "), ("code", f["code"]), ("text", ": "),
            ("text", clip(f["message"], MAX_COLS - used)),
        ])
    rows.append([("dim", f"  … {len(rep['findings']) - len(PICK)} more")])

    width = int(PAD_X * 2 + MAX_COLS * CHAR_W)
    height = PAD_TOP + LINE_H * len(rows) + 18
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="godot_lint output: Godot 3 leftovers and broken res:// paths found in a Godot 4 project">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{COLORS["bg"]}" stroke="{COLORS["border"]}"/>',
        f'<path d="M10.5 0.5h{width - 21}a10 10 0 0 1 10 10v24h-{width - 1}v-24a10 10 0 0 1 10-10z" fill="{COLORS["bar"]}"/>',
        f'<circle cx="22" cy="18" r="6" fill="#ff5f57"/><circle cx="42" cy="18" r="6" fill="#febc2e"/><circle cx="62" cy="18" r="6" fill="#28c840"/>',
        f'<text x="{width / 2}" y="22" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" fill="{COLORS["title"]}">godot-project-lint · gamedev-toolkit</text>',
        f'<g font-family="Consolas, ui-monospace, SFMono-Regular, Menlo, monospace" font-size="13" xml:space="preserve">',
    ]
    for i, row in enumerate(rows):
        y = PAD_TOP + i * LINE_H
        spans = "".join(f'<tspan fill="{COLORS[c]}">{escape(t)}</tspan>' for c, t in row)
        out.append(f'<text x="{PAD_X}" y="{y}">{spans}</text>')
    out += ["</g>", "</svg>", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({width}x{height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
