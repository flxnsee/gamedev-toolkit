#!/usr/bin/env python3
"""Render docs/social-preview.png (1280x640) for GitHub Settings > Social preview.

Needs Pillow (pip install pillow) and fonts: Segoe UI + Consolas on Windows, or pass
--sans/--sans-bold/--mono with paths to other TTF files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/social-preview.png"
W, H = 1280, 640

BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
DIM = "#8b949e"
RED = "#f85149"
YELLOW = "#d29922"
BLUE = "#79c0ff"
PURPLE = "#d2a8ff"
GREEN = "#3fb950"

ENGINES = [("Godot", "#478cbf"), ("Unity", "#4c5a6b"), ("Unreal", "#313a5e"), ("Blender", "#e87d0d")]

TERMINAL = [
    [(GREEN, "$ "), (TEXT, "python godot_lint.py my-game")],
    [(RED, "16 errors"), (TEXT, ", "), (YELLOW, "1 warnings")],
    [(RED, "[error] "), (BLUE, "main.tscn:4 "), (PURPLE, "path-case")],
    [(RED, "[error] "), (BLUE, "player.gd:4 "), (PURPLE, "gd3-onready")],
    [(RED, "[error] "), (BLUE, "player.gd:18 "), (PURPLE, "gd3-yield")],
    [(YELLOW, "[warn]  "), (BLUE, "main.tscn:5 "), (PURPLE, "stale-path")],
]


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        sys.exit(f"font not found: {path} (pass --sans/--sans-bold/--mono)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sans", default="C:/Windows/Fonts/segoeui.ttf")
    ap.add_argument("--sans-bold", default="C:/Windows/Fonts/segoeuib.ttf")
    ap.add_argument("--mono", default="C:/Windows/Fonts/consola.ttf")
    a = ap.parse_args()

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # subtle grid
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill="#10161d")
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill="#10161d")

    left = 80
    d.text((left, 78), "flxnsee / gamedev-toolkit", font=font(a.sans, 30), fill=DIM)
    d.text((left, 118), "gamedev-toolkit", font=font(a.sans_bold, 84), fill=TEXT)
    sub = font(a.sans, 34)
    d.text((left, 232), "Skills that know your engine.", font=sub, fill=TEXT)
    d.text((left, 276), "Checks that run on your real project.", font=sub, fill=TEXT)

    chip_f = font(a.sans_bold, 26)
    x = left
    for name, color in ENGINES:
        tw = d.textlength(name, font=chip_f)
        d.rounded_rectangle([x, 352, x + tw + 36, 400], radius=24, fill=color)
        d.text((x + 18, 358), name, font=chip_f, fill="#ffffff")
        x += tw + 36 + 14

    d.text((left, 520), "for Claude Code · Codex · Cursor · any Agent Skills agent",
           font=font(a.sans, 26), fill=DIM)

    # terminal panel
    px0, py0, px1, py1 = 760, 300, 1210, 560
    d.rounded_rectangle([px0, py0, px1, py1], radius=14, fill=PANEL, outline=BORDER, width=2)
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        cx = px0 + 24 + i * 22
        d.ellipse([cx - 7, py0 + 17, cx + 7, py0 + 31], fill=c)
    mono = font(a.mono, 22)
    y = py0 + 52
    for row in TERMINAL:
        x = px0 + 22
        for color, text in row:
            d.text((x, y), text, font=mono, fill=color)
            x += d.textlength(text, font=mono)
        y += 32

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)} ({W}x{H})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
