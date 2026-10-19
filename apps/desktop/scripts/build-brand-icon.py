#!/usr/bin/env python3
"""Build the Merlin wizard-hat brand icon — clean vector, reference-matched.

Rather than thresholding the reference JPEG (which carries band, buckle and
JPEG speckle that turn to mush at 16px), this draws the SAME mark as bold
primitives: tall cone with a curled tip, wide swept brim, one band, one star.
Colors are lifted from the reference art: navy #102037 glyph on gold #fecd28.

Every asset electron-builder, Windows and the web splash read comes from here:
  assets/icon.png  assets/icon-dark.png  assets/icon.ico  assets/icon-dark.ico
  public/apple-touch-icon.png  assets/appx/*.png

Run:  python build_icon_v3.py [--out-root <apps/desktop>] [--sizes] [--preview]
"""
from __future__ import annotations

import io
import math
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw



LANCZOS = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

GOLD = (254, 205, 40, 255)
GOLD_EDGE = (222, 158, 8, 255)
NAVY = (16, 32, 55, 255)

SS = 4  # supersample factor


def bez(p0, p1, p2, p3, n=64):
    """Cubic bezier sample points."""
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        out.append((x, y))
    return out


def star_pts(cx, cy, r, inner=0.40, n=5):
    pts = []
    for i in range(n * 2):
        ang = -math.pi / 2 + i * math.pi / n
        rad = r if i % 2 == 0 else r * inner
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


def write_ico(path: Path, frames: list[Image.Image]) -> None:
    """frames: list of square RGBA images, each already rendered at its size."""
    frames = sorted(frames, key=lambda im: im.width)
    blobs: list[bytes] = []
    for im in frames:
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        blobs.append(buf.getvalue())

    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries, payloads = b"", b""
    for im, blob in zip(frames, blobs):
        w = 0 if im.width >= 256 else im.width
        h = 0 if im.height >= 256 else im.height
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(blob), offset)
        payloads += blob
        offset += len(blob)

    path.write_bytes(header + entries + payloads)


def draw_hat(d: ImageDraw.ImageDraw, S: int, glyph, tile, *, detail: bool = True) -> None:
    """Paint the hat in `glyph` colour with `tile`-coloured negative details."""
    U = lambda x, y: (x * S, y * S)  # noqa: E731

    # --- brim: wide ellipse, the classic wizard sweep --------------------
    d.ellipse(
        [U(0.045, 0.745)[0], U(0.045, 0.745)[1], U(0.955, 0.915)[0], U(0.955, 0.915)[1]],
        fill=glyph,
    )

    # --- cone: left edge up, curl at the tip, right edge down -------------
    left = bez(U(0.255, 0.840), U(0.285, 0.560), U(0.330, 0.230), U(0.470, 0.090))
    # curled tip: sweep right, hook down, tuck back under
    curl = [
        U(0.470, 0.090),
        U(0.505, 0.064),
        U(0.560, 0.054),
        U(0.600, 0.078),
        U(0.622, 0.108),
        U(0.612, 0.140),
        U(0.578, 0.154),
        U(0.548, 0.148),
        U(0.532, 0.126),
    ]
    right = bez(U(0.532, 0.126), U(0.600, 0.250), U(0.700, 0.460), U(0.762, 0.840))
    cone = left + curl + right
    d.polygon(cone, fill=glyph)

    def x_at_y(points, y):
        """x where a y-monotone curve crosses height y (unit space)."""
        pts = sorted(points, key=lambda p: p[1] / S)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            y0, y1 = y0 / S, y1 / S
            if y0 <= y <= y1:
                t = (y - y0) / max(1e-9, y1 - y0)
                return (x0 + (x1 - x0) * t) / S
        return None

    if not detail:
        return

    # --- band: a decorative stripe, inset so it never cuts the silhouette
    y_hi, y_lo = 0.585, 0.640
    l_hi, r_hi = x_at_y(left, y_hi), x_at_y(right, y_hi)
    l_lo, r_lo = x_at_y(left, y_lo), x_at_y(right, y_lo)
    if None not in (l_hi, r_hi, l_lo, r_lo):
        inset = 0.035  # keep the stripe off the cone edges
        d.polygon(
            [
                U(l_hi + inset, y_hi),
                U(r_hi - inset, y_hi),
                U(r_lo - inset, y_lo),
                U(l_lo + inset, y_lo),
            ],
            fill=tile,
        )

    # --- star on the cone ------------------------------------------------
    cx, cy, r = 0.408 * S, 0.352 * S, 0.058 * S
    d.polygon(star_pts(cx, cy, r), fill=tile)


def render(size: int, *, dark: bool) -> Image.Image:
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(S * 0.225)
    if dark:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=NAVY)
        d.rounded_rectangle(
            [int(S * 0.012), int(S * 0.012), S - int(S * 0.012), S - int(S * 0.012)],
            radius=int(S * 0.212),
            outline=GOLD_EDGE,
            width=max(1, int(S * 0.006)),
        )
        draw_hat(d, S, GOLD, NAVY, detail=size >= 128)
    else:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=GOLD)
        draw_hat(d, S, NAVY, GOLD, detail=size >= 128)
    return img.resize((size, size), LANCZOS)


def ascii_preview(img: Image.Image, w: int = 48) -> str:
    h = max(1, int(round(img.height * w / img.width * 0.5)))
    small = img.convert("RGBA").resize((w, h), LANCZOS)
    rows = []
    for y in range(h):
        row = ""
        for x in range(w):
            r, g, b, a = small.getpixel((x, y))
            if a < 70:
                row += " "
            elif r < 100 and b > 20:
                row += "@"
            else:
                row += "#"
        rows.append(row)
    return "\n".join(rows)


def main() -> int:
    argv = sys.argv[1:]
    root = Path(argv[argv.index("--out-root") + 1]) if "--out-root" in argv else Path("out-v5")

    if "--preview" in argv:
        for sz in (16, 24, 32, 48, 64):
            print(f"--- {sz}px ---")
            print(ascii_preview(render(sz, dark=False), w=min(sz, 48)))

    assets, public, appx = root / "assets", root / "public", root / "assets" / "appx"
    for p in (assets, public, appx):
        p.mkdir(parents=True, exist_ok=True)

    light = render(1024, dark=False)
    dark = render(1024, dark=True)
    light.save(assets / "icon.png")
    dark.save(assets / "icon-dark.png")
    light.save(public / "apple-touch-icon.png")

    # Per-size art: small entries omit the band/star so the silhouette stays
    # connected when Windows scales it down in the taskbar.
    ico_sizes = (16, 24, 32, 48, 64, 128, 256)
    write_ico(assets / "icon.ico", [render(s, dark=False) for s in ico_sizes])
    write_ico(assets / "icon-dark.ico", [render(s, dark=True) for s in ico_sizes])

    light.save(assets / "icon.icns", format="ICNS")
    dark.save(assets / "icon-dark.icns", format="ICNS")
    light.resize((1024, 1024), LANCZOS).save(assets / "icon-mac.png")

    for name, dims in [
        ("Square44x44Logo", (44, 44)),
        ("Square150x150Logo", (150, 150)),
        ("StoreLogo", (50, 50)),
        ("Wide310x150Logo", (310, 150)),
    ]:
        light.resize(dims, LANCZOS).save(appx / f"{name}.png")
        dark.resize(dims, LANCZOS).save(appx / f"{name}-dark.png")

    print(f"wrote brand icon set under {root}")
    for f in sorted(assets.glob("icon*")) + sorted(public.glob("apple*")):
        print(f"  {f.relative_to(root)}  {f.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
