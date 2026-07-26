#!/usr/bin/env python3
"""
generate_readme.py  --  SCAFFOLD the terminal profile SVGs from scratch.

  ⚠  This OVERWRITES assets/terminal.svg and assets/terminal_light.svg
     completely, including any ASCII art you have hand-tuned inside them.
     Back those files up before you run it.

The SVGs are the source of truth for the layout AND the art. Day to day you
want assets/update_stats.py, which only rewrites the stat numbers in place and
leaves everything else alone. That is the split Andrew6rant uses: a committed,
hand-editable SVG plus a script that touches nothing but the figures.

Run this only when you want to rebuild the layout (new rows, colours, fonts).

Pulls live GitHub stats (repos, commits, stars, followers, lines of code)
and paints them into a self-contained SVG that keeps a monospace terminal
look on GitHub (where inline HTML/CSS in READMEs is sanitised away).

Auth:  uses GITHUB_TOKEN from the environment ONLY. Nothing is committed.
       Runs fine with no token too -- it falls back to the cached numbers
       so you can preview locally.

Outputs: assets/terminal.svg, assets/terminal_light.svg
         (+ refreshes assets/stats_cache.json)

Portrait detail: regenerate the ASCII at a different column count with
    python3 assets/img_to_ascii.py assets/portrait.png --width 76 --contrast 1.25
Current art is 64 cols x 49 rows. Going much finer than that shrinks the
glyphs below ~9px, where the face stops reading and turns into a grey mass.
Pair a higher column count with a higher ART_SCALE to keep glyphs legible.
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
OUT_SVG = ROOT / "terminal.svg"            # dark variant
OUT_SVG_LIGHT = ROOT / "terminal_light.svg"  # light variant

# ---- portrait source -----------------------------------------------------
# "ascii"  -> tint portrait.txt in the terminal palette (the Andrew6rant look)
# "photo"  -> embed IMAGE_FILE directly, no ASCII conversion at all
# "none"   -> text only. Use this when the artwork lives in README.md instead,
#             which is required for anything that must load an external image
#             (skillicons badges, shields.io) - an SVG served as an <img>
#             cannot fetch external resources, so those can never go in here.
PORTRAIT_MODE = os.environ.get("PORTRAIT_MODE", "none")

# Image used when PORTRAIT_MODE == "photo". Drop your file in assets/ and name
# it here. First one that exists wins, so the build never breaks on a missing
# file. PNG is safest: an animated GIF will not animate once it's embedded in
# an SVG that GitHub serves as an <img>.
IMAGE_CANDIDATES = ["melody.png", "melody.jpg", "melody.gif", "portrait.png"]
IMAGE_FILE = next((ROOT / n for n in IMAGE_CANDIDATES if (ROOT / n).exists()),
                  ROOT / IMAGE_CANDIDATES[-1])

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}

# How tall the image is, as a fraction of the text column's height.
# 1.0 = same height as all the text. Lower = smaller. This is the one number
# to change if Melody looks too big or too small.
IMAGE_SCALE = 0.35

# ---- palettes ------------------------------------------------------------
# THEME_PAIR picks which two get rendered: (dark file, light file).
# Swap to ("mono_dark", "mono_light") for the all-greyscale version.
THEME_PAIR = ("dark", "light")

THEMES = {
    "dark": dict(
        KEY="#ffa657", HEADC="#c9d1d9",
        ART="#adbac7",
        BG="#0d1117", PANEL="#161b22", BAR="#161b22", STROKE="#30363d",
        DIM="#8b949e", LEADER="#30363d", VALUE="#c9d1d9",
        ACCENT="#7ee787", PINK="#79c0ff", LILAC="#d2a8ff",
        DOTS=["#ff5f57", "#febc2e", "#28c840"],
    ),
    "light": dict(
        KEY="#bc4c00", HEADC="#1f2328",
        ART="#57606a",
        BG="#ffffff", PANEL="#f6f8fa", BAR="#f6f8fa", STROKE="#d0d7de",
        DIM="#656d76", LEADER="#d0d7de", VALUE="#1f2328",
        ACCENT="#1a7f37", PINK="#0969da", LILAC="#8250df",
        DOTS=["#ff5f57", "#febc2e", "#28c840"],
    ),
    "mono_dark": dict(
        KEY="#ffffff", HEADC="#f2f2f2",
        ART="#b8b8b8",
        BG="#0a0a0a", PANEL="#111111", BAR="#161616", STROKE="#2b2b2b",
        DIM="#8a8a8a", LEADER="#333333", VALUE="#f2f2f2",
        ACCENT="#ffffff", PINK="#ffffff", LILAC="#b8b8b8",
        DOTS=["#4d4d4d", "#808080", "#b3b3b3"],
    ),
    "mono_light": dict(
        KEY="#000000", HEADC="#141414",
        ART="#5a5a5a",
        BG="#ffffff", PANEL="#f7f7f7", BAR="#f0f0f0", STROKE="#d8d8d8",
        DIM="#6b6b6b", LEADER="#cccccc", VALUE="#141414",
        ACCENT="#000000", PINK="#000000", LILAC="#5a5a5a",
        DOTS=["#c9c9c9", "#a6a6a6", "#8a8a8a"],
    ),
}

# Live palette globals - reassigned by apply_theme() before each render.
BG = PANEL = BAR = STROKE = DIM = LEADER = VALUE = ACCENT = PINK = LILAC = ART = KEY = HEADC = ""
DOTS = []


def apply_theme(name):
    """Point the module-level colour names at one of the THEMES."""
    global BG, PANEL, BAR, STROKE, DIM, LEADER, VALUE, ACCENT, PINK, LILAC, DOTS, ART, KEY, HEADC
    t = THEMES[name]
    BG, PANEL, BAR, STROKE = t["BG"], t["PANEL"], t["BAR"], t["STROKE"]
    DIM, LEADER, VALUE = t["DIM"], t["LEADER"], t["VALUE"]
    ACCENT, PINK, LILAC, DOTS = t["ACCENT"], t["PINK"], t["LILAC"], t["DOTS"]
    ART, KEY, HEADC = t["ART"], t["KEY"], t["HEADC"]

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
# content  --  edit your details here
# --------------------------------------------------------------------------
# Row kinds:
#   ("user", name)            -> "anna@anp-exe ---------------------"
#   ("head", label)           -> "- Contact ------------------------"
#   ("row",  key, value)      -> ". Key: ................... value"
#   ("pair", k1, v1, k2, v2)  -> ". K1: ..... v1   . K2: ..... v2"
#   ("blank",)                -> spacer
PROFILE = [
    ("user", f"anna@{USER}"),
    ("row", "OS", "macOS"),
    ("row", "Role", "BSc AI & Philosophy @ KCL (2026-2029)"),
    ("row", "Location", "London, UK"),
    ("row", "IDE", "PyCharm, JetBrains Suite"),
    ("row", "Toolchain", "Git, MkDocs, GitHub Actions"),
    ("blank",),
    ("row", "Languages", "Python"),
    ("row", "Libraries.Data", "pandas, NumPy"),
    ("row", "Libraries.ML", "scikit-learn, PyTorch"),
    ("row", "Libraries.Viz", "matplotlib, seaborn"),
    ("blank",),
    ("row", "Focus.Research", "Data journalism, ML maths"),
    ("row", "Focus.Ethics", "AI safety and AI ethics"),
    ("row", "Certs", "AWS Certified AI Practitioner"),
    ("blank",),
    ("head", "Contact"),
    ("row", "Portfolio", "anp-exe.github.io/anna"),
    ("row", "GitHub", USER),
    ("row", "LinkedIn", "anp-exe"),
]

STATS_HEADER = "GitHub Stats"

# Row label -> element id. These are the only numbers update_stats.py touches.
STAT_IDS = {
    "Repos": "repos",
    "Stars": "stars",
    "Commits": "commits",
    "Followers": "followers",
    "Lines of Code on GitHub": "loc",
}
ROW_CHARS = 64          # nominal width of the info column, in characters

# Detail of the ASCII portrait.
#   ART_COLS  - regenerate portrait.txt at this width for more/less detail:
#               python3 assets/img_to_ascii.py assets/portrait.png --width N
#   ART_SCALE - vertical room the art gets, as a multiple of the text
#               column height. Raise it so a high column count still
#               renders at a legible glyph size.
ART_SCALE = 1.35

# "side"    -> art beside the text. Art is capped to the text column's height,
#              so keep it near 64 columns or the glyphs get too small to read.
# "stacked" -> art on its own full-width row, text underneath. Use this for
#              high-resolution art (200+ columns): the art reads as a
#              photographic halftone while the body text stays legible.
ART_LAYOUT = "side"
ART_TARGET_W = 1360.0     # rendered width of the art, SVG units (stacked only)


def stats_rows(stats):
    return [
        ("blank",),
        ("head", STATS_HEADER),
        ("pair", "Repos", human(stats["repos"]), "Stars", human(stats["stars"])),
        ("pair", "Commits", human(stats["commits"]),
                 "Followers", human(stats["followers"])),
        ("row", "Lines of Code on GitHub", human(stats["loc"])),
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


def image_size(path):
    """(width, height) for any image. Uses Pillow when available so JPG/GIF
    work too, and falls back to the PNG header so this file keeps running
    with nothing installed."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return png_size(path)


def esc(s):
    return escape(str(s), quote=True)


def leader_row(x, right, y, key, value, fs):
    """`. Key: ........... value`, with the value flush to `right`.

    Alignment is GEOMETRIC, not character-counted: the key is anchored left,
    the value is anchored right, and the gap is bridged by a dashed <line>.
    That way the columns stay aligned even if the viewer substitutes a
    non-monospace font - which is exactly what broke the old version.
    """
    cw = fs * 0.6
    label = f"{key}:"
    # Live stats get stable ids so update_stats.py can rewrite just the number
    # in place, the way Andrew6rant's today.py does.
    sid = STAT_IDS.get(key)
    vid = f' id="{sid}_data"' if sid else ""
    lid = f' id="{sid}_leader"' if sid else ""
    out = [
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs}" xml:space="preserve">'
        f'<tspan fill="{LEADER}">. </tspan>'
        f'<tspan fill="{KEY}" font-weight="700">{esc(label)}</tspan></text>',
        f'<text{vid} x="{right:.1f}" y="{y:.1f}" font-size="{fs}" '
        f'text-anchor="end" fill="{VALUE}">{esc(value)}</text>',
    ]
    x1 = x + (len(label) + 2) * cw + 6
    x2 = right - len(str(value)) * cw - 6
    if x2 > x1 + 6:
        out.append(f'<line{lid} x1="{x1:.1f}" y1="{y - fs * 0.30:.1f}" '
                   f'x2="{x2:.1f}" y2="{y - fs * 0.30:.1f}" '
                   f'stroke="{LEADER}" stroke-width="1.4" '
                   f'stroke-dasharray="1.4 4.2" stroke-linecap="round"/>')
    return "".join(out)


def pair_row(x, right, y, k1, v1, k2, v2, fs):
    mid = x + (right - x) / 2
    return (leader_row(x, mid - 16, y, k1, v1, fs)
            + leader_row(mid + 8, right, y, k2, v2, fs))


def rule_row(x, right, y, label, fs, lead=""):
    """`anna@anp-exe --------` / `- Contact --------`, rule drawn as a line."""
    cw = fs * 0.6
    txt = f"{lead}{label}"
    out = [f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs}" fill="{HEADC}" '
           f'font-weight="700" xml:space="preserve">{esc(txt)}</text>']
    x1 = x + (len(txt) + 1) * cw + 4
    if right > x1 + 8:
        out.append(f'<line x1="{x1:.1f}" y1="{y - fs * 0.30:.1f}" '
                   f'x2="{right:.1f}" y2="{y - fs * 0.30:.1f}" '
                   f'stroke="{STROKE}" stroke-width="1.4"/>')
    return "".join(out)


def build_svg(stats):
    use_img = PORTRAIT_MODE == "photo" and PORTRAIT_IMG.exists()

    pad = 30
    fs = 15.0
    lh = 22.0
    cw = fs * 0.6
    left_x = pad

    rows = PROFILE + stats_rows(stats)
    info_h = len(rows) * lh
    info_w = ROW_CHARS * cw

    # ---- portrait sizing -------------------------------------------------
    if PORTRAIT_MODE == "none":
        art_w = art_h = 0.0
        portrait, pfs, plh, p_cols = [], 0, 0, 0
        img_b64 = img_mime = ""
    elif use_img:
        iw, ih = image_size(IMAGE_FILE)
        # Image height as a fraction of the text column's height. A mascot
        # wants to be much smaller than a full-bleed ASCII portrait, so this
        # has its own knob rather than reusing ART_SCALE.
        art_h = info_h * IMAGE_SCALE
        art_w = art_h * iw / ih
        img_b64 = base64.b64encode(IMAGE_FILE.read_bytes()).decode()
        img_mime = MIME.get(IMAGE_FILE.suffix.lower(), "image/png")
        portrait, pfs, plh, p_cols = [], 0, 0, 0
    else:
        portrait = (PORTRAIT_FILE.read_text(encoding="utf-8").rstrip("\n").split("\n")
                    if PORTRAIT_FILE.exists() else PLACEHOLDER_PORTRAIT.split("\n"))
        p_rows = len(portrait)
        p_cols = max(len(l) for l in portrait)
        # Scale the art to the HEIGHT of the info column, not a fixed width:
        # sizing a tall portrait by width makes it tower over the text.
        # Rows are pre-squashed 0.5x, so lh = 1.2 * fontsize.
        # ART_SCALE > 1 buys the art extra vertical room, which is how you get
        # a high column count AND glyphs that are still big enough to read.
        if ART_LAYOUT == "stacked":
            # Art gets its own full-width row, so size it by WIDTH and let the
            # height fall out. This is the only way a high column count keeps
            # its detail: side by side, fitting art + text across GitHub's
            # ~870px display width squeezes the body font under 7px.
            pfs = ART_TARGET_W / (p_cols * 0.62)
            plh = pfs * 1.2
        else:
            # Scale the art to the HEIGHT of the info column, not a fixed width:
            # sizing a tall portrait by width makes it tower over the text.
            # Rows are pre-squashed 0.5x, so lh = 1.2 * fontsize.
            # ART_SCALE > 1 buys the art extra vertical room, which is how you
            # get a high column count AND glyphs still big enough to read.
            plh = (info_h * ART_SCALE) / p_rows
            pfs = max(3.0, min(20.0, plh / 1.2))
            plh = pfs * 1.2
        art_w = p_cols * pfs * 0.62   # 0.62 not 0.60: safety margin,
                                     # since width is no longer pinned
        art_h = p_rows * plh

    gap = 0 if PORTRAIT_MODE == "none" else 54
    if ART_LAYOUT == "stacked" and PORTRAIT_MODE != "none":
        info_x = left_x
        info_r = info_x + info_w
        W = int(max(art_w, info_w) + pad * 2)
        H = int(art_h + gap + info_h + pad * 2)
    else:
        info_x = left_x + art_w + gap
        info_r = info_x + info_w
        W = int(info_r + pad)
        H = int(max(art_h, info_h) + pad * 2)

    S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,'
         f"'DejaVu Sans Mono','JetBrains Mono','Cascadia Code',Menlo,"
         f"Consolas,'Liberation Mono',monospace\">"]

    S.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="{BG}"/>')

    # ---- portrait --------------------------------------------------------
    if PORTRAIT_MODE == "none":
        top = info_top = pad
    elif ART_LAYOUT == "stacked":
        top = pad
        info_top = pad + art_h + gap
    else:
        # Whichever column is shorter gets centred against the taller one.
        body_h = max(art_h, info_h)
        top = pad + (body_h - art_h) / 2
        info_top = pad + (body_h - info_h) / 2
    if PORTRAIT_MODE == "none":
        pass
    elif use_img:
        S.append(f'<clipPath id="pclip"><rect x="{left_x}" y="{top}" '
                 f'width="{art_w:.1f}" height="{art_h:.1f}" rx="8"/></clipPath>')
        S.append(f'<image x="{left_x}" y="{top}" width="{art_w:.1f}" '
                 f'height="{art_h:.1f}" clip-path="url(#pclip)" '
                 f'preserveAspectRatio="xMidYMid meet" '
                 f'href="data:{img_mime};base64,{img_b64}"/>')
    else:
        # Flat tint in the terminal palette - no white box, no border.
        #
        # Deliberately NO textLength here. Pinning each line to a fixed width
        # looks like it should guarantee the art can't overflow, but renderers
        # ignore trailing whitespace when measuring a string: sparse lines
        # (mostly spaces, a few glyphs) measure short and then get stretched
        # to reach the pinned width, while dense lines already fill it. The
        # result is a portrait whose top rows are smeared wide and whose
        # bottom rows are correct. Natural monospace advance is the fix.
        S.append(f'<g fill="{ART}" font-size="{pfs:.2f}" xml:space="preserve" '
                 f'style="white-space:pre">')
        for i, line in enumerate(portrait):
            S.append(f'<text x="{left_x}" y="{top + (i + 1) * plh:.1f}">'
                     f'{esc(line)}</text>')
        S.append("</g>")

    # ---- info column -----------------------------------------------------
    y = info_top + lh
    for r in rows:
        kind = r[0]
        if kind == "blank":
            pass
        elif kind == "user":
            S.append(rule_row(info_x, info_r, y, r[1], fs))
        elif kind == "head":
            S.append(rule_row(info_x, info_r, y, r[1], fs, lead="- "))
        elif kind == "row":
            S.append(leader_row(info_x, info_r, y, r[1], r[2], fs))
        elif kind == "pair":
            S.append(pair_row(info_x, info_r, y, r[1], r[2], r[3], r[4], fs))
        y += lh

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

    # Always leave a cache file behind, so the workflow's `git add` step can
    # never fail on a missing path.
    if not CACHE_FILE.exists():
        CACHE_FILE.write_text(json.dumps(stats, indent=2))

    for theme, out in ((THEME_PAIR[0], OUT_SVG), (THEME_PAIR[1], OUT_SVG_LIGHT)):
        apply_theme(theme)
        svg = build_svg(stats)
        out.write_text(svg, encoding="utf-8")
        print(f"wrote {out.name}  ({len(svg)} bytes, theme={theme})")


if __name__ == "__main__":
    main()
