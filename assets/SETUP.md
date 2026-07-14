# Terminal profile — setup

Everything lives in `assets/`. The README just embeds `assets/terminal.svg`.

## Why SVG (not a fenced code block)

GitHub **strips inline HTML/CSS** from README markdown, so you cannot colour
text inside a page. A fenced ```code``` block keeps monospace but is a single
theme-controlled colour — no berry/magenta. An **SVG rendered as an image** is
the only way to get *coloured monospace + a terminal frame + a blinking cursor*
that looks identical on every device and in light/dark mode. That's the
Andrew6rant approach, and it's what this uses.

## Files

| File | Purpose |
|------|---------|
| `assets/generate_readme.py` | Fetches live stats + renders `terminal.svg`. Stdlib only. |
| `assets/img_to_ascii.py` | Turns your photo into `portrait.txt`. Needs Pillow. |
| `assets/portrait.txt` | The ASCII portrait (left column). Swap freely. |
| `assets/terminal.svg` | The generated artwork the README shows. |
| `assets/stats_cache.json` | Last good stats (fallback if the API hiccups). |
| `.github/workflows/terminal-stats.yml` | Auto-refresh, twice daily, `GITHUB_TOKEN` only. |

## 1. The portrait

**Default = embedded photo.** If `assets/portrait.png` exists, the generator
embeds it into the SVG, forced to grayscale, with a terminal frame + scanlines.
This is the recognisable, clean option. To swap your photo, just replace
`assets/portrait.png` (a cropped head-and-shoulders shot works best).

**Optional = ASCII art.** Delete `assets/portrait.png` and the generator falls
back to `assets/portrait.txt`. Generate that from a photo with:

```bash
pip install pillow
python3 assets/img_to_ascii.py path/to/photo.jpg --width 90 --contrast 1.3
# lighter subject on dark bg? add --invert
```

Note: photo-to-ASCII is inherently abstract — great as a stylised effect,
not a sharp likeness. The embedded photo is the better call for a real face.

## 2. Render the SVG locally (preview, no token needed)

```bash
python3 assets/generate_readme.py    # uses cached numbers when no token
```

Open `assets/terminal.svg` in a browser to check it.

## 3. Turn on live stats

No secrets to add — GitHub Actions injects `GITHUB_TOKEN` automatically.

1. Commit and push everything to `anp-exe/anp-exe` on `main`.
2. GitHub → repo **Settings → Actions → General → Workflow permissions** →
   set **Read and write permissions** (lets the job commit the refreshed SVG).
3. Actions tab → **terminal-stats** → **Run workflow** to populate it now.
   After that it runs twice a day on its own.

## Editing content later

Change the info block (Subject/Role/Core/etc.) in the `INFO_SECTIONS` /
`CONTACT` lists near the bottom of `generate_readme.py`. Colours are the
palette constants at the top (`PINK`, `ACCENT`, `VALUE`, `LILAC`, ...).

## Security

No API keys or credentials are stored anywhere. The workflow uses the
ephemeral `GITHUB_TOKEN` that GitHub creates per-run and destroys after.
The token is only used in-memory to authenticate API calls and shallow
clones for the lines-of-code count — it is never written to a file.
