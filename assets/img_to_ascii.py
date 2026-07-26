#!/usr/bin/env python3
"""
img_to_ascii.py  --  turn a photo into a berry-toned ASCII portrait.

Usage:
    python3 assets/img_to_ascii.py <image> [--width 44] [--out assets/portrait.txt] [--invert]

Notes
-----
* Monospace glyphs are ~2x taller than wide, so we squash rows by 0.5 to
  keep the face's aspect ratio correct.
* Output is a plain-text block. Colour is applied later by generate_readme.py
  (a berry gradient over the whole block), so this file only decides *shape*.
* Charset runs dark -> light. Use --invert if your subject is light-on-dark.
"""
import argparse
from PIL import Image, ImageOps, ImageEnhance

# Dense -> sparse. More rungs = smoother gradient.
# "sparse" ends in a space, so light areas drop out and the portrait floats.
# "filled" has no space, so the background renders as ':'/'.' and the art is a
# solid textured block with visible edges.
RAMPS = {
    "sparse": "@%#WM*ozc+i!;:,.'` ",
    "filled": "@%#*+=-:.",
}
CHAR_ASPECT = 0.5  # row squash factor for monospace


def to_ascii(path: str, width: int, invert: bool, contrast: float,
             ramp_name: str = "sparse") -> str:
    img = Image.open(path).convert("L")
    img = ImageOps.autocontrast(img, cutoff=2)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    w, h = img.size
    new_h = max(1, int(width * (h / w) * CHAR_ASPECT))
    img = img.resize((width, new_h))
    px = img.getdata()

    base = RAMPS[ramp_name]
    ramp = base[::-1] if invert else base
    n = len(ramp) - 1
    keep_trailing = " " not in base      # 'filled' must keep its background
    rows = []
    for row in range(new_h):
        line = []
        for col in range(width):
            v = px[row * width + col]           # 0..255
            line.append(ramp[int(v / 255 * n)])
        joined = "".join(line)
        rows.append(joined if keep_trailing else joined.rstrip())
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--width", type=int, default=44)
    ap.add_argument("--out", default="assets/portrait.txt")
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--contrast", type=float, default=1.15)
    ap.add_argument("--ramp", choices=sorted(RAMPS), default="sparse",
                    help="'sparse' drops the background out; "
                         "'filled' renders it as ':' for a solid block")
    a = ap.parse_args()

    art = to_ascii(a.image, a.width, a.invert, a.contrast, a.ramp)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(art + "\n")
    lines = art.count("\n") + 1
    cols = max(len(l) for l in art.splitlines())
    print(f"wrote {a.out}  ({cols} cols x {lines} rows)")


if __name__ == "__main__":
    main()
