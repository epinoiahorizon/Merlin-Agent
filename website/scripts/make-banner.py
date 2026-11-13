"""Render the docs social banner: MERLIN-AGENT, same arcade treatment as before.

Why a script rather than a hand-edited PNG: the OG image is the first thing anyone sees when the
docs link is shared, and the previous one still said HERMES-AGENT. A generator keeps the style
reproducible and makes the next product rename a one-line change instead of an art task.

  python website/scripts/make-banner.py --out website/static/img/merlin-agent-banner.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1160, 175
BG = (0, 0, 0)
TEXT = "MERLIN-AGENT"
FONT_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "static" / "fonts" / "PressStart2P-Regular.ttf",
    Path(r"C:/Users/JM Project/AppData/Local/Temp/PressStart2P.ttf"),
]
GRADIENT = [(0.0, (255, 210, 63)), (0.55, (245, 168, 0)), (0.90, (122, 68, 19)), (1.0, (110, 63, 20))]
TRAIL_OFFSETS = [6, 12, 18, 24]
TRAIL_COLOR = (224, 138, 16)


def lerp_gradient(t: float) -> tuple[int, int, int]:
    for (t0, c0), (t1, c1) in zip(GRADIENT, GRADIENT[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0
            r, g, b = (round(a + (bb - a) * f) for a, bb in zip(c0, c1))
            return (r, g, b)
    return GRADIENT[-1][1]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise SystemExit("PressStart2P.ttf not found; put it in website/static/fonts/ or pass --font")


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int) -> ImageFont.FreeTypeFont:
    size = max_height
    while size > 8:
        font = load_font(size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= max_width and bottom - top <= max_height:
            return font
        size -= 2
    return load_font(8)


def render(out: Path, font_path: Path | None = None) -> None:
    if font_path:
        FONT_CANDIDATES.insert(0, Path(font_path))
    canvas = Image.new("RGB", (W, H), BG)
    probe = ImageDraw.Draw(canvas)
    font = fit_font(probe, TEXT, W - 20, int(H * 0.82))

    bbox = probe.textbbox((0, 0), TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2 - bbox[0]
    y = int(H * 0.06) - bbox[1]

    # Trail first, painted behind: outline-only copies stepping down-right, which is what gives the
    # original its depth. Drawn back-to-front so the nearest copy ends up on top of the farther ones.
    for offset in reversed(TRAIL_OFFSETS):
        probe.text((x + offset, y + offset), TEXT, font=font, fill=None, stroke_width=2, stroke_fill=TRAIL_COLOR)

    # Main text: gradient fill applied through the glyph mask, so the ramp follows the letters rather
    # than the canvas (a canvas-wide gradient would leave the bottom of each glyph too light).
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).text((x, y), TEXT, font=font, fill=255)

    ramp = Image.new("RGB", (W, H))
    ramp_px = ramp.load()
    y0, y1 = y + bbox[1], y + bbox[3]
    for py in range(H):
        t = 0.0 if py < y0 else 1.0 if py > y1 else (py - y0) / max(1, y1 - y0)
        colour = lerp_gradient(t)
        for px in range(W):
            ramp_px[px, py] = colour

    canvas.paste(ramp, (0, 0), mask)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG", optimize=True)
    name = font.getname()
    print(f"wrote {out} ({W}x{H}) font={(name or ('unknown',))[0]} size={font.size}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="website/static/img/merlin-agent-banner.png")
    ap.add_argument("--font", default=None)
    render(Path(ap.parse_args().out), ap.parse_args().font)
