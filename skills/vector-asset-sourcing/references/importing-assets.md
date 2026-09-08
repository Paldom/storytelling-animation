# Importing vector assets into a Remotion composition

## Where files live

Copy assets into the project's `public/` folder (`public/icons/*.svg`,
`public/lottie/*.json`) and load them with `staticFile()`. Render-time downloads
are a determinism and supply-chain risk; a copied file with a pinned version in
the manifest is reproducible.

## Static SVG icons

Two ways, pick one per project:

1. **Inline as JSX** (preferred for icons you will animate): paste the `<svg>`
   markup into a component, keep `viewBox`, replace `class` with `className`,
   `stroke-width` with `strokeWidth`, set `stroke="currentColor"` and drive colour
   via CSS `color`. Every path is then addressable for draw-on
   (`@remotion/paths` `evolvePath`) and per-element motion.
2. **`<Img src={staticFile("icons/clock.svg")} />`** for decorative icons you only
   move or fade as a whole. Remotion waits for the image before rendering the frame.

Size icons from the layout tokens (a fraction of frame height), never with the
SVG's own `width`/`height` attributes; strip those attributes and keep `viewBox`.

Stroke icon sets are drawn at 2 px on a 24 px grid; scaling a 24 px icon to 240 px
makes the stroke 20 px, which is right for a headline-sized icon at 1080 wide.
Mixing a 1.5 px set with a 2 px set is visible at that scale: one pack per project.

## Lottie animations

```tsx
import { Lottie, LottieAnimationData, getLottieMetadata } from "@remotion/lottie";
import { staticFile, delayRender, continueRender, cancelRender } from "remotion";
// fetch staticFile("lottie/checkmark.json") inside useEffect behind delayRender(),
// then <Lottie animationData={data} playbackRate={1} loop={false} style={{ width, height }} />
```

- `getLottieMetadata(json)` returns `durationInSeconds`, `durationInFrames` (in the
  file's own `fps`), `width`, `height`. Convert to composition frames before sizing the
  `<Sequence>`: `Math.ceil(durationInSeconds * compositionFps / playbackRate)`; using the
  file's `durationInFrames` in a composition with a different fps truncates the animation.
- Playback is frame-driven (Remotion seeks the Lottie to the current frame), so
  `<Sequence from>` and `playbackRate` are the timing controls; `<Freeze>` holds a pose.
  For anything that must line up with a text card, an inline SVG animated with
  `useCurrentFrame()` is simpler.
- The checker rejects image assets or layers (vector-only), external fonts, and After
  Effects expressions (`"x": "…"` properties), which render blank or differ from preview.
- Install pinned: `npx remotion add @remotion/lottie` (matches the project's Remotion
  version) and the exact `lottie-web` version it asks for.

## Animated icon libraries

CSS-hover or Motion-driven icon libraries (lucide-animated, animated-icons,
heroicons-animated) run on wall-clock time; in a frame render each frame is
rendered independently, so their animations do not play. Take the static SVG from
the underlying set and animate it with `useCurrentFrame()` instead.

## Assets manifest

`assets/manifest.json` (contract v1). Paths are relative to the project root
(pass `--root .`). `assets[]` entries: `file`, `kind` (`icon` default, `illustration`,
`lottie`, `shape`), `pack` (set name or `own`), `version` (the release you copied
from), `source` (URL or `own:<who>`), `license` (an id from the checker's list),
and for credit licenses `attribution` with the exact credit line. `fonts[]`: `family`,
`source`, `license`, optional `file` under `public/fonts/`. Run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_assets.py" assets/manifest.json --root . --write-attribution ATTRIBUTION.md
```

Deliver `ATTRIBUTION.md` with the video whenever it has a credit line, and put the
credit where the license says: on screen (a closing card) when the terms require a
visible credit in the work itself; otherwise in the LinkedIn post text or on a
closing slide. Slide notes vanish when a deck is exported, so they are not a place
for a required credit. The checker validates what you declared; it does not verify
ownership or that the terms allow your use.
