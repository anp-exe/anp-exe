#!/usr/bin/env python3
"""
generate_readme.py  --  render the berry cyberpunk terminal profile SVG.

Pulls live GitHub stats (repos, commits, stars, followers, lines of code)
and paints them into a self-contained SVG that keeps a monospace terminal
look on GitHub (where inline HTML/CSS in READMEs is sanitised away).

Auth:  uses GITHUB_TOKEN from the environment ONLY. Nothing is committed.
       Runs fine with no token too -- it falls back to the cached numbers
       so you can preview locally.

Outputs: assets/terminal.svg  (+ refreshes assets/stats_cache.json)
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------
USER = os.environ.get("GITHUB_REPOSITORY_OWNER") or os.environ.get("GH_USER") or "anp-exe"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
COUNT_LOC = os.environ.get("COUNT_LOC", "1") not in ("0", "false", "False")

ROOT = Path(__file__).resolve().parent          # assets/
PORTRAIT_FILE = ROOT / "portrait.txt"           # ASCII fallback
PORTRAIT_IMG = ROOT / "portrait.png"            # embedded photo (preferred)
CACHE_FILE = ROOT / "stats_cache.json"
OUT_SVG = ROOT / "terminal.svg"

# ---- monochrome palette: white / grey on near-black ----------------------
BG          = "#0a0a0a"   # near-black
PANEL       = "#111111"   # slightly lifted panel
BAR         = "#161616"   # window titlebar
STROKE      = "#2b2b2b"   # panel border
DIM         = "#8a8a8a"   # grey (labels)
LEADER      = "#333333"   # leader dots
VALUE       = "#f2f2f2"   # near-white (values)
ACCENT      = "#ffffff"   # white accent / headings
PINK        = "#ffffff"   # white (prompt / headings)
LILAC       = "#b8b8b8"   # soft grey secondary
GREENish    = "#dddddd"
DOTS        = ["#4d4d4d", "#808080", "#b3b3b3"]  # grayscale traffic lights

# ---- monospace geometry --------------------------------------------------
CW = 6.6        # char width  @ 11px mono (portrait)
LH = 12.4       # portrait line height
INFO_FS = 13
INFO_CW = 7.9
INFO_LH = 20

# label field width in chars for the dotted-leader info rows
LABEL_COL = 12
VALUE_COL = 15   # column where values begin


# --------------------------------------------------------------------------
# GitHub GraphQL / REST helpers
# --------------------------------------------------------------------------
def gql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}",
                 "Content-Type": "application/json",
                 "User-Agent": USER},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read())
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


def rest(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Authorization": f"bearer {TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": USER},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def account_year(login):
    data = gql("query($l:String!){user(login:$l){createdAt}}", {"l": login})
    return int(data["user"]["createdAt"][:4])


def fetch_stats():
    """Return dict of live stats, raising on any hard failure."""
    # followers, repo count, stars, account age
    q = """
    query($l:String!, $after:String){
      user(login:$l){
        login
        followers{ totalCount }
        repositories(first:100, ownerAffiliations:OWNER, after:$after,
                     orderBy:{field:STARGAZERS, direction:DESC}){
          totalCount
          pageInfo{ hasNextPage endCursor }
          nodes{ name stargazerCount isFork nameWithOwner defaultBranchRef{ name } }
        }
      }
    }"""
    repos, after = [], None
    followers = repo_total = 0
    while True:
        d = gql(q, {"l": USER, "after": after})["user"]
        followers = d["followers"]["totalCount"]
        repo_total = d["repositories"]["totalCount"]
        repos.extend(d["repositories"]["nodes"])
        pi = d["repositories"]["pageInfo"]
        if not pi["hasNextPage"]:
            break
        after = pi["endCursor"]

    stars = sum(r["stargazerCount"] for r in repos)

    # lifetime commit contributions: sum per calendar year
    start = account_year(USER)
    now = datetime.now(timezone.utc).year
    commits = 0
    cq = """
    query($l:String!,$f:DateTime!,$t:DateTime!){
      user(login:$l){ contributionsCollection(from:$f, to:$t){
        totalCommitContributions
        restrictedContributionsCount } } }"""
    for y in range(start, now + 1):
        d = gql(cq, {"l": USER, "f": f"{y}-01-01T00:00:00Z",
                     "t": f"{y}-12-31T23:59:59Z"})["user"]["contributionsCollection"]
        commits += d["totalCommitContributions"] + d["restrictedContributionsCount"]

    loc = count_loc(repos) if COUNT_LOC else None

    return {
        "user": USER,
        "repos": repo_total,
        "stars": stars,
        "followers": followers,
        "commits": commits,
        "loc": loc,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# text extensions we count toward LOC
_TEXT_EXT = {
    ".py", ".c", ".h", ".cpp", ".hpp", ".js", ".jsx", ".ts", ".tsx",
    ".html", ".css", ".scss", ".md", ".yml", ".yaml", ".json", ".sh",
    ".java", ".go", ".rs", ".rb", ".php", ".sql", ".r", ".m", ".ipynb",
    ".toml", ".cfg", ".ini", ".txt", ".svg", ".vue", ".lua", ".kt",
}


def count_loc(repos):
    """Shallow-clone each non-fork repo and count lines of text files."""
    total = 0
    tmp = tempfile.mkdtemp(prefix="loc_")
    try:
        for r in repos:
            if r.get("isFork"):
                continue
            url = f"https://x-access-token:{TOKEN}@github.com/{r['nameWithOwner']}.git"
            dst = os.path.join(tmp, r["name"])
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", "--quiet", url, dst],
                    check=True, capture_output=True, timeout=180)
            except Exception:
                continue
            for dirpath, dirnames, files in os.walk(dst):
                if ".git" in dirpath:
                    continue
                for fn in files:
                    if os.path.splitext(fn)[1].lower() not in _TEXT_EXT:
                        continue
                    fp = os.path.join(dirpath, fn)
                    try:
                        if os.path.getsize(fp) > 2_000_000:  # skip >2MB
                            continue
                        with open(fp, "rb") as fh:
                            total += fh.read().count(b"\n")
                    except Exception:
                        continue
            shutil.rmtree(dst, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return total


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {"user": USER, "repos": 0, "stars": 0, "followers": 0,
            "commits": 0, "loc": 0, "updated": "never"}


def human(n):
    if n is None:
        return "n/a"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 10_000:
        return f"{n/1000:.1f}k"
    return f"{n:,}"


# --------------------------------------------------------------------------
# static profile data (the info block)
# --------------------------------------------------------------------------
INFO_SECTIONS = [
    [
        ("Subject",   "Anna Parker"),
        ("Role",      "BSc AI & Philosophy @ KCL (2026-2029)"),
        ("Origin",    "London, UK"),
        ("Status",    "Building * Learning * Shipping"),
        ("ToolChain", "JetBrains, Git, MkDocs, GH Actions"),
    ],
    [
        ("Core",      "Python, C++"),
        ("Data",      "pandas, NumPy, matplotlib"),
        ("Web",       "HTML/CSS, JS, GitHub Pages"),
        ("Focus",     "Data journalism, ML maths, AI ethics"),
        ("Certs",     "AWS Certified AI Practitioner"),
    ],
]
CONTACT = [
    ("Portfolio", "anp-exe.github.io/anna"),
    ("GitHub",    "anp-exe"),
]


# --------------------------------------------------------------------------
# SVG building
# --------------------------------------------------------------------------
def png_size(path):
    """Read a PNG's width/height from its IHDR (no PIL dependency)."""
    import struct
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def esc(s):
    return escape(str(s), quote=True)


def text(x, y, s, fill, fs=INFO_FS, weight="400", cls="", extra=""):
    c = f' class="{cls}"' if cls else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" '
            f'font-size="{fs}" font-weight="{weight}"{c}{extra}>{esc(s)}</text>')


def leader_row(x, y, label, value, width_chars=46):
    """label ... value  with three coloured tspans on one baseline."""
    dots = max(3, VALUE_COL - len(label))
    dot_str = " " + ("." * (dots - 1)) + " "
    pad_after = width_chars - VALUE_COL - len(value)
    parts = [
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{INFO_FS}" xml:space="preserve">',
        f'<tspan fill="{DIM}">{esc(label)}</tspan>',
        f'<tspan fill="{LEADER}">{esc(dot_str)}</tspan>',
        f'<tspan fill="{VALUE}">{esc(value)}</tspan>',
        "</text>",
    ]
    return "".join(parts)


def build_svg(stats):
    # Prefer an embedded photo (assets/portrait.png); fall back to ASCII.
    use_img = PORTRAIT_IMG.exists()

    pad = 26
    bar_h = 34
    left_x = pad

    if use_img:
        iw, ih = png_size(PORTRAIT_IMG)
        img_w = 285.0
        img_h = img_w * ih / iw
        img_b64 = base64.b64encode(PORTRAIT_IMG.read_bytes()).decode()
        portrait_h = img_h + 24            # + room for caption
        info_x = max(left_x + img_w + 60, 360)
        portrait = []
        pfs = plh = 0
    else:
        portrait = PORTRAIT_FILE.read_text(encoding="utf-8").rstrip("\n").split("\n") \
            if PORTRAIT_FILE.exists() else PLACEHOLDER_PORTRAIT.split("\n")
        p_rows = len(portrait)
        p_cols = max(len(l) for l in portrait)
        # auto-size font so any column count fits a target width; rows were
        # pre-squashed 0.5x, so line-height ~= 1.2*fontsize keeps proportions.
        target_pw = 430.0
        pfs = min(11.0, max(4.2, target_pw / (p_cols * 0.6)))
        plh = pfs * 1.2
        portrait_w = p_cols * pfs * 0.6
        info_x = max(left_x + portrait_w + 64, 360)
        portrait_h = p_rows * plh

    info_lines = (sum(len(s) for s in INFO_SECTIONS)
                  + len(INFO_SECTIONS)      # blank line between sections
                  + 2                       # "Contact:" header + blank
                  + len(CONTACT) + 1)
    info_h = info_lines * INFO_LH
    body_h = max(portrait_h, info_h) + 24

    stats_h = 150
    W = int(info_x + 46 * INFO_CW + pad)
    W = max(W, 900)
    H = int(bar_h + 20 + body_h + stats_h + pad)

    S = []
    S.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="\'JetBrains Mono\',\'Fira Code\','
        f"'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace\">")

    # defs: glow + berry gradient for portrait
    S.append(f'''<defs>
  <linearGradient id="berry" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{PINK}"/>
    <stop offset="0.55" stop-color="{ACCENT}"/>
    <stop offset="1" stop-color="{LILAC}"/>
  </linearGradient>
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="0.6" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="gray">
    <feColorMatrix type="saturate" values="0"/>
    <feComponentTransfer><feFuncA type="linear" slope="1"/></feComponentTransfer>
  </filter>
  <pattern id="scan" width="1" height="3" patternUnits="userSpaceOnUse">
    <rect width="1" height="3" fill="#000000" opacity="0"/>
    <rect width="1" height="1" fill="#000000" opacity="0.16"/>
  </pattern>
</defs>''')

    # window
    S.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="{BG}"/>')
    S.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" '
             f'fill="none" stroke="{STROKE}"/>')
    S.append(f'<rect x="0" y="0" width="{W}" height="{bar_h}" rx="12" fill="{BAR}"/>')
    S.append(f'<rect x="0" y="{bar_h-12}" width="{W}" height="12" fill="{BAR}"/>')
    for i, c in enumerate(DOTS):
        S.append(f'<circle cx="{22+i*20}" cy="{bar_h/2:.0f}" r="6" fill="{c}"/>')
    S.append(text(96, bar_h/2 + 4, f"{stats['user']}@github: ~/profile — neofetch",
                  DIM, fs=12))

    # ---- portrait -------------------------------------------------------
    py0 = bar_h + 26
    if use_img:
        ix, iy0 = left_x, py0 - 12
        r = 6
        S.append(f'<clipPath id="pclip"><rect x="{ix:.1f}" y="{iy0:.1f}" '
                 f'width="{img_w:.1f}" height="{img_h:.1f}" rx="{r}"/></clipPath>')
        S.append(f'<image x="{ix:.1f}" y="{iy0:.1f}" width="{img_w:.1f}" '
                 f'height="{img_h:.1f}" clip-path="url(#pclip)" '
                 f'preserveAspectRatio="xMidYMid slice" filter="url(#gray)" '
                 f'href="data:image/png;base64,{img_b64}"/>')
        # subtle scanlines + frame for the terminal feel
        S.append(f'<rect x="{ix:.1f}" y="{iy0:.1f}" width="{img_w:.1f}" '
                 f'height="{img_h:.1f}" rx="{r}" fill="url(#scan)" '
                 f'clip-path="url(#pclip)"/>')
        S.append(f'<rect x="{ix:.1f}" y="{iy0:.1f}" width="{img_w:.1f}" '
                 f'height="{img_h:.1f}" rx="{r}" fill="none" stroke="{STROKE}"/>')
        # corner brackets
        cl = 14
        for (cx, cy, dx, dy) in [
            (ix, iy0, 1, 1), (ix + img_w, iy0, -1, 1),
            (ix, iy0 + img_h, 1, -1), (ix + img_w, iy0 + img_h, -1, -1)]:
            S.append(f'<path d="M {cx+dx*cl:.1f} {cy:.1f} L {cx:.1f} {cy:.1f} '
                     f'L {cx:.1f} {cy+dy*cl:.1f}" fill="none" '
                     f'stroke="{VALUE}" stroke-width="1.5"/>')
        S.append(text(ix + 2, iy0 + img_h + 16, "> ./portrait --render",
                      DIM, fs=11))
    else:
        S.append(f'<g filter="url(#glow)" fill="url(#berry)" '
                 f'font-size="{pfs:.2f}" letter-spacing="0" xml:space="preserve" '
                 f'style="white-space:pre">')
        for i, line in enumerate(portrait):
            y = py0 + i * plh
            S.append(f'<text x="{left_x}" y="{y:.1f}">{esc(line)}</text>')
        S.append("</g>")

    # ---- info block -----------------------------------------------------
    iy = py0 + 6
    S.append(text(info_x, iy, "> whoami --verbose", PINK, fs=INFO_FS, weight="700"))
    iy += INFO_LH * 1.6
    for si, section in enumerate(INFO_SECTIONS):
        for label, value in section:
            S.append(leader_row(info_x, iy, label, value))
            iy += INFO_LH
        iy += INFO_LH * 0.6
    # contact
    S.append(text(info_x, iy, "Contact:", ACCENT, fs=INFO_FS, weight="700"))
    iy += INFO_LH
    for label, value in CONTACT:
        S.append(leader_row(info_x, iy, label, value))
        iy += INFO_LH

    # ---- live stats panel ----------------------------------------------
    panel_y = bar_h + 20 + body_h
    panel_x = pad
    panel_w = W - pad * 2
    S.append(f'<rect x="{panel_x}" y="{panel_y}" width="{panel_w}" '
             f'height="{stats_h-16}" rx="8" fill="{PANEL}" stroke="{STROKE}"/>')
    sx = panel_x + 22
    sy = panel_y + 30
    S.append(text(sx, sy, "> gh stats --live", PINK, fs=INFO_FS, weight="700"))
    S.append(f'<text x="{panel_x + panel_w - 22:.1f}" y="{sy:.1f}" fill="{DIM}" '
             f'font-size="11" text-anchor="end">updated {esc(stats["updated"])}</text>')
    sy += INFO_LH * 1.4

    rows = [
        ("Repos",         human(stats["repos"])),
        ("Commits",       human(stats["commits"])),
        ("Stars",         human(stats["stars"])),
        ("Followers",     human(stats["followers"])),
        ("Lines of Code", human(stats["loc"])),
    ]
    col_w = (panel_w - 44) / len(rows)
    for i, (label, value) in enumerate(rows):
        cx = sx + i * col_w
        S.append(text(cx, sy, label, DIM, fs=11))
        S.append(text(cx, sy + 24, value, VALUE, fs=20, weight="700",
                      extra=' filter="url(#glow)"'))

    # blinking cursor / prompt line
    cy = panel_y + stats_h - 18
    S.append(text(sx, cy, f"{stats['user']}@github:~$ ", PINK, fs=INFO_FS))
    cur_x = sx + len(f"{stats['user']}@github:~$ ") * INFO_CW
    S.append(f'<rect x="{cur_x:.0f}" y="{cy-11:.0f}" width="9" height="15" '
             f'fill="{PINK}"><animate attributeName="opacity" values="1;1;0;0" '
             f'dur="1.06s" repeatCount="indefinite"/></rect>')

    S.append("</svg>")
    return "\n".join(S)


PLACEHOLDER_PORTRAIT = """\
+------------------------+
|                        |
|      [ PORTRAIT ]      |
|                        |
|   drop your photo, run |
|   img_to_ascii.py to   |
|   fill this block      |
|                        |
|   44 cols x ~40 rows   |
|                        |
+------------------------+"""


def main():
    stats = None
    if TOKEN:
        try:
            stats = fetch_stats()
            CACHE_FILE.write_text(json.dumps(stats, indent=2))
            print("fetched live stats:", stats)
        except Exception as e:
            print(f"[warn] live fetch failed ({e}); using cache", file=sys.stderr)
    else:
        print("[info] no GITHUB_TOKEN; using cached numbers for preview")

    if stats is None:
        stats = load_cache()

    svg = build_svg(stats)
    OUT_SVG.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT_SVG}  ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
