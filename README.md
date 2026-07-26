<!--
  anp-exe/anp-exe  —  profile README

  LAYOUT
  Two-column table: Melody + skill badges on the left, terminal stats card on
  the right. The badges live HERE and not inside the SVG on purpose — an SVG
  that GitHub serves as an <img> cannot load external images, so anything from
  skillicons.dev or shields.io has to be its own <img> in this file.

  THE CARD
  assets/terminal.svg (dark) + terminal_light.svg (light) are the SOURCE OF
  TRUTH for the card's layout — edit them directly if you want.

  assets/update_stats.py rewrites only the stat numbers, in place, by element
  id. That is what .github/workflows/terminal-stats.yml runs twice a day.

  assets/generate_readme.py REBUILDS both SVGs from scratch. Only run it to
  change the layout. PORTRAIT_MODE is "none" so the card is text only.

  If the card looks stale after a push: GitHub proxies README images through
  camo and caches them per-URL. It clears on its own; to force it, append ?v=2
  (then ?v=3) to the image URLs below.
-->

<table>
  <tr>
    <td width="230" valign="top" align="center">

<img src="./assets/melody.png" width="190" alt="My Melody">

<a href="https://skillicons.dev">
  <img src="https://skillicons.dev/icons?i=github,python,pytorch,scikitlearn,aws&perline=3" alt="Skills: GitHub, Python, PyTorch, scikit-learn, AWS">
</a>

  </td>
  <td valign="top">

<a href="https://github.com/anp-exe">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/terminal.svg">
    <img alt="Anna Parker — terminal profile" src="./assets/terminal_light.svg">
  </picture>
</a>

  </td>
  </tr>
</table>
