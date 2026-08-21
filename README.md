<!--
  anp-exe/anp-exe  —  profile README

  LAYOUT
  Two-column table: Melody + skill badges on the left, terminal stats card on
  the right. The badges live HERE and not inside the SVG on purpose — an SVG
  that GitHub serves as an <img> cannot load external images, so anything from
  skillicons.dev or shields.io has to be its own <img> in this file.

  Cell widths are PERCENTAGES, not pixels, so the columns stay in proportion on
  a phone. With a fixed px width the left cell cannot shrink, so on a narrow
  screen the card cell compresses while the left column keeps its size and ends
  up dominating. The px widths on the images below act as maximums only —
  GitHub's own CSS (max-width: 100%) scales them down inside a narrower cell.

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
    <td width="26%" valign="top" align="center">

<!--
  Each item is wrapped in its own <div>. <img> and <a> are INLINE elements, so
  blank lines between them do nothing — they flow side by side and only break
  when a row runs out of width. That is why the small badges ended up next to
  each other. The <div>s force one per line.
-->

<div><img src="./assets/melody.png" width="160" alt="My Melody"></div>

<!--
  The whole grid is ONE image, so every icon in it shares the single
  skillicons.dev link — you cannot make one tile point somewhere else. Anything
  that needs its own destination has to be a separate badge below.

  git + githubactions were added to keep the count at 12 so perline=3 fills
  four even rows. Drop any two of them if you would rather have ten.
-->

<div>
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=github,python,pycharm,pytorch,scikitlearn,matlab,aws,obsidian,apple,figma,git,githubactions&perline=3" alt="Skills: GitHub, Python, PyCharm, PyTorch, scikit-learn, MATLAB, AWS, Obsidian, Apple, Figma, Git, GitHub Actions">
  </a>
</div>

<div>
  <a href="https://medium.com/@Joy-P/i-was-the-only-woman-playing-among-50-or-100-men-fc39f6fedbe5">
    <img src="https://img.shields.io/badge/Featured%20on%20Medium-12100E?style=for-the-badge&logo=medium&logoColor=white" alt="Featured on Medium — “I was the only woman playing among 50 or 100 men”">
  </a>
</div>

<!--
  Credly badge. If the image ever fails to load, swap the src for the URL
  Credly itself advertises in the badge page's og:image tag:
  https://images.credly.com/images/4d4693bb-530e-4bca-9327-de07f3aa2348/linkedin_thumb_image.png
  (that one is a wide LinkedIn thumbnail, so it will need a bigger width).
  The badge must stay Public in Credly or it won't render for visitors.
-->
<div>
  <a href="https://www.credly.com/badges/f2462771-efa4-4541-ac13-a0cec2dcbae7/public_url">
    <img src="https://images.credly.com/size/340x340/images/4d4693bb-530e-4bca-9327-de07f3aa2348/image.png" width="70" alt="AWS Certified AI Practitioner — verify on Credly">
  </a>
</div>

<div><img src="./assets/strawb.png" width="90" alt=""></div>

  </td>
  <td width="74%" valign="top">

<a href="https://github.com/anp-exe">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/terminal.svg">
    <img alt="Anna Parker — terminal profile" src="./assets/terminal_light.svg">
  </picture>
</a>

  </td>
  </tr>
</table>
