<!--
  anp-exe/anp-exe  —  profile README
  The terminal readout is assets/terminal.svg (dark) + terminal_light.svg (light).
  Those two files are the SOURCE OF TRUTH for the layout and the ASCII art —
  edit them directly, including hand-tuning the art.

  assets/update_stats.py rewrites only the stat numbers, in place, by element id.
  That is what .github/workflows/terminal-stats.yml runs twice a day.

  assets/generate_readme.py REBUILDS both SVGs from scratch and will wipe any
  hand edits to the art. Only run it to change the layout.

  If the card ever looks stale after a push: GitHub proxies README images
  through camo and caches them per-URL, so the same filename can keep serving
  old bytes for a while. It clears on its own; to force it, append ?v=2 (then
  ?v=3, etc.) to both image URLs below.
-->

<div align="center">

<a href="https://github.com/anp-exe">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/terminal.svg">
    <img alt="Anna Parker — terminal profile" src="./assets/terminal_light.svg">
  </picture>
</a>

</div>
