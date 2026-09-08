---
name: vector-asset-sourcing
description: Picks icon and illustration packs licensed for a commercial rendered video - license and credit matrix, one-pack stroke consistency, SVG and Lottie hygiene checks, pinning, assets manifest. Use when the user asks which pack to use for the animation, whether an SVG, Lottie or illustration may go in the video, or to add assets for its scenes. Not for app or web UI icons, scene layout, or animating.
license: MIT
---

# vector-asset-sourcing

Chooses and checks the icons, illustrations, Lottie files and fonts that go into a
rendered vector animation. It fixes three observed failures: mixing icon sets with
different grids and stroke weights (the video looks assembled), shipping a client
video with "free" assets that required a credit or forbade commercial use, and
importing SVG/Lottie files that carry scripts, external images or expressions that
do not render frame by frame.

## When to use / when NOT to use

Use when picking an icon or illustration pack for an animation, when someone asks
"can we use this in the video", when adding SVG or Lottie files to the project, or
when the assets manifest needs writing or checking.

Do NOT use for: placing or sizing assets in a scene (`vector-scene-layout`),
animating them (`smooth-motion-choreography`), animated icon components for a web
UI, designing an app icon, or vectorising a raster logo.

## Workflow

1. **Inventory what the storyboard needs**: list every visual noun in
   `storyboard.json` (`visual` fields) and mark which are icons, illustrations, or
   shapes you will draw yourself (rects, lines, connectors: draw them, do not source them).
2. **Pick one pack** from `references/license-matrix.md`. Default: Lucide (ISC,
   24 px grid, 2 px stroke) for icons; unDraw or Storyset-with-credit for people
   and scenes; LottieFiles public animations for a pre-animated flourish. Stay on one
   stroke weight. Prefer no-attribution licenses for client work.
3. **Copy files into `public/`** with the pack's version pinned in the manifest
   (`version`, `source` URL). Never load assets from a CDN at render time.
4. **Write `assets/manifest.json`** (contract in `references/importing-assets.md`,
   runnable example in `assets/example/`): one entry per file with `license`
   from the checker's list, `attribution` text when the license needs it, `fonts[]`
   for every typeface.
5. **Check and emit credits**:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/check_assets.py" assets/manifest.json --write-attribution ATTRIBUTION.md
   ```
   Fix every error (unknown license, missing credit, script/external ref/raster in an
   SVG, external images or expressions in a Lottie); resolve warnings about mixed
   packs or stroke weights by replacing the odd file, not by silencing the warning.
6. **Hand off**: the file list, the pack and stroke weight chosen, and the attribution
   requirement (if any) go into the reply; `vector-scene-layout` imports from `public/`.

## Output spec

- `public/` holds every asset as SVG or Lottie JSON, no rasters.
- `assets/manifest.json` passes `check_assets.py` with 0 errors.
- `ATTRIBUTION.md` exists when any asset needs credit, and the reply says where the
  credit must appear (post text, slide notes, on screen).

## Gotchas

- The license is on the file, not the site: LottieFiles public animations are free,
  marketplace files are not; SVGRepo relabels CC-BY as MIT. Follow the source link.
- Free tiers of Flaticon, Storyset, Icons8 and Lordicon all require a visible credit;
  a paid tier removes it. `CC-BY-NC`, `ND` and GPL assets fail the checker on purpose.
- Icon packs are drawn on their own grid; one 1.5 px icon among 2 px icons is visible
  at headline size. Draw the missing shape instead of borrowing from a second pack.
- CSS-hover and Motion-driven "animated icon" libraries do not play in a frame
  render (each frame renders alone); animate the static SVG with `useCurrentFrame()`.
- Lottie files with external images or After Effects expressions render blank or
  differ between preview and render; the checker rejects them.
- Brand logos: Simple Icons is CC0 for the drawing only; the trademark is not yours.
- Pin versions. The 2024 `lottie-player` npm compromise hit every page loading an
  unpinned CDN build.

## Pointers

- `scripts/check_assets.py` — manifest, license and file checks; `--self-test`.
- `references/license-matrix.md` — packs, licenses, traps, fonts, supply chain.
- `references/importing-assets.md` — inline SVG vs `<Img>`, Lottie import, manifest contract.
- `assets/example/` — a passing manifest with own-work SVGs, a Lottie file and a font.
