#!/usr/bin/env python3
"""
update_stats.py  --  refresh ONLY the numbers inside the committed SVGs.

This mirrors the architecture of Andrew6rant/today.py: the SVG files are the
source of truth for layout AND for the ASCII art, hand-editable and committed.
Nothing here regenerates them. This script parses each SVG, finds the elements
carrying a known id, and rewrites just their text.

  <text id="commits_data" ...>463</text>     <- the number
  <line id="commits_leader" .../>            <- the dotted leader before it

Andrew6rant recomputes a run of '.' characters to keep his values right-aligned.
Ours are anchored with text-anchor="end", so they right-align themselves; the
only thing needing adjustment is where the dashed leader stops.

Safe to run with no token: it falls back to assets/stats_cache.json.

    python3 assets/update_stats.py

To change the layout, colours, rows or art, edit generate_readme.py and rerun
it - but note that OVERWRITES both SVGs, including any hand-tuning you've done
to the ASCII art. That is the trade-off of the template approach: the art is
now yours to keep, so back it up before rebuilding.
"""
import json
import sys
from xml.etree import ElementTree as ET

import generate_readme as g

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)          # keeps output as <svg>, not <ns0:svg>

FIELDS = ("repos", "stars", "commits", "followers", "loc")


def update_svg(path, stats):
    """Rewrite the stat numbers in one SVG. Returns list of (field, value)."""
    tree = ET.parse(path)
    root = tree.getroot()
    applied = []

    for field in FIELDS:
        value = g.human(stats.get(field))
        el = root.find(f".//*[@id='{field}_data']")
        if el is None:
            print(f"  [warn] no element id={field}_data in {path.name}",
                  file=sys.stderr)
            continue
        el.text = value

        # Pull the dashed leader back so it stops short of the new number.
        line = root.find(f".//*[@id='{field}_leader']")
        if line is not None:
            fs = float(el.get("font-size", 15))
            right = float(el.get("x"))
            x1 = float(line.get("x1"))
            x2 = right - len(value) * fs * 0.6 - 6
            # If a long number leaves no room, collapse the leader rather than
            # letting it run underneath the digits.
            line.set("x2", f"{max(x1, x2):.1f}")
            line.set("visibility", "hidden" if x2 <= x1 + 6 else "visible")

        applied.append((field, value))

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return applied


def main():
    stats = None
    if g.TOKEN:
        try:
            stats = g.fetch_stats()
            g.CACHE_FILE.write_text(json.dumps(stats, indent=2))
            print("fetched live stats")
        except Exception as e:
            print(f"[warn] live fetch failed ({e}); using cache", file=sys.stderr)
    else:
        print("[info] no GITHUB_TOKEN; using cached numbers")

    if stats is None:
        stats = g.load_cache()
    if not g.CACHE_FILE.exists():
        g.CACHE_FILE.write_text(json.dumps(stats, indent=2))

    for path in (g.OUT_SVG, g.OUT_SVG_LIGHT):
        if not path.exists():
            print(f"[warn] {path.name} missing - run generate_readme.py once "
                  f"to scaffold it", file=sys.stderr)
            continue
        applied = update_svg(path, stats)
        summary = ", ".join(f"{k}={v}" for k, v in applied)
        print(f"updated {path.name}: {summary}")


if __name__ == "__main__":
    main()
