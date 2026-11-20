#!/usr/bin/env python3
"""Render demo/scenes.txt as an animated terminal GIF (demo/demo.gif).

The scenes are real output from check.py, guard.py and policy_block.py, trimmed to fit.
Needs Pillow: pip install pillow. Usage: python3 demo/make_gif.py [scenes.txt] [out.gif]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
W, H, PAD, LINE = 960, 560, 26, 21
FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/Library/Fonts/Menlo.ttc",
              "/System/Library/Fonts/Menlo.ttc", "C:/Windows/Fonts/consola.ttf"]
BG, BAR, FG, DIM = (13, 17, 23), (22, 27, 34), (201, 209, 217), (139, 148, 158)
COLORS = {"STOP": (255, 123, 114), "FIX": (210, 153, 34), "CHECK": (88, 166, 255), "INFO": (139, 148, 158)}
PROMPT, TITLE = (63, 185, 80), (240, 246, 252)


def font(size, bold=False):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p.replace("Mono.ttf", "Mono-Bold.ttf") if bold else p, size)
        except OSError:
            continue
    return ImageFont.load_default()


MONO, MONO_B, BIG = font(15), font(15, True), font(40, True)


def color_of(line):
    s = line.strip()
    for key, c in COLORS.items():
        if s.startswith(key) or s.startswith(f"- {key}:"):
            return c
    if s.startswith("Result:"):
        return COLORS["STOP"] if "STOP" in s else COLORS["FIX"] if "Fix" in s else PROMPT
    if s.startswith("==") or s.startswith("sarwan_skill guard"):
        return TITLE
    if s.startswith(("at ", '"')) or s.startswith("```"):
        return DIM
    return FG


def frame(title, lines, cursor=False):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 34], fill=BAR)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([16 + i * 22, 11, 28 + i * 22, 23], fill=c)
    d.text((W // 2, 17), title, font=MONO, fill=DIM, anchor="mm")
    y = 34 + PAD // 2
    for line in lines[-((H - 60) // LINE):]:
        if line.startswith("$ "):
            d.text((PAD, y), "$", font=MONO_B, fill=PROMPT)
            d.text((PAD + 18, y), line[2:], font=MONO_B, fill=TITLE)
        else:
            c = color_of(line)
            d.text((PAD, y), line, font=MONO_B if c in COLORS.values() and line.strip()[:4] in ("STOP", "FIX ") else
                   MONO, fill=c)
        y += LINE
    if cursor:
        last = lines[-1] if lines else ""
        x = PAD + (18 + MONO.getlength(last[2:]) if last.startswith("$ ") else MONO.getlength(last))
        d.rectangle([x + 2, y - LINE + 3, x + 10, y - 3], fill=FG)
    return img


def title_card(lines):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((W // 2, H // 2 - 50), lines[0], font=BIG, fill=TITLE, anchor="mm")
    d.text((W // 2, H // 2 + 5), lines[1], font=font(22, True), fill=PROMPT, anchor="mm")
    if len(lines) > 2:
        d.text((W // 2, H // 2 + 45), lines[2], font=MONO, fill=DIM, anchor="mm")
    return img


def scenes(text):
    out, cur = [], None
    for line in text.splitlines():
        if line.startswith("=== "):
            cur = [line[4:], []]
            out.append(cur)
        elif cur is not None:
            cur[1].append(line)
    return out


def render(scene_file, out_file):
    frames, durations = [], []
    for title, body in scenes(Path(scene_file).read_text(encoding="utf-8")):
        if title == "title":
            frames.append(title_card(body))
            durations.append(2600)
            continue
        shown = []
        for line in body:
            if line.startswith("$ "):
                typed = "$ "
                for i in range(0, len(line) - 2, 3):
                    typed = "$ " + line[2:2 + i + 3]
                    frames.append(frame(title, shown + [typed], cursor=True))
                    durations.append(45)
                shown.append(line)
                frames.append(frame(title, shown))
                durations.append(450)
            else:
                shown.append(line)
                frames.append(frame(title, shown))
                durations.append(110)
        durations[-1] = 3200
    frames[0].save(out_file, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    print(f"wrote {out_file} ({len(frames)} frames, {sum(durations) / 1000:.0f}s)")


if __name__ == "__main__":
    render(sys.argv[1] if len(sys.argv) > 1 else HERE / "scenes.txt", sys.argv[2] if len(sys.argv) > 2 else
           HERE / "demo.gif")
