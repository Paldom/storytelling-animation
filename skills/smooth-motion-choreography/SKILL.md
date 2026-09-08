---
name: smooth-motion-choreography
description: Choreographs smooth motion for existing Remotion vector scenes - enter, hold, emphasis, camera and exit moves, ease and spring presets (settle, overshoot, no bounce), stagger, draw-on, transitions, loop seams, a flicker linter. Use when the user asks to animate scenes or icons, ease something in, smooth jerky, flickering or popping motion, or fix a loop that jumps. Not for CSS, web UI, or export.
license: MIT
---

# smooth-motion-choreography

Adds motion to the static scenes of a Remotion project so the result reads as one
calm system on a muted phone feed. It fixes the failures agents produce by default:
springs that bounce text, CSS transitions that flicker in the parallel render,
staggers that read as one pop, pans that strobe at 30 fps, text that moves while it
should be read, exits that vanish before the cut, and loops with a visible seam.

## When to use / when NOT to use

Use when the scenes exist and need animating, when motion feels jerky, mechanical,
floaty or flickery, when transitions or a loop seam need fixing, or when someone asks
which easing or spring to use in Remotion.

Do NOT use for: beats and timing of the story (`animation-storyboard`), building or
sizing scenes (`vector-scene-layout`), encoding and presets (`animation-export-presets`),
judging a finished render (`animation-frame-qa`), web UI hover effects, CSS or GSAP
questions, or Remotion API detail (`remotion-dev/skills`).

## Workflow

1. **Read the contract**: `storyboard.json` gives each beat's `motion` intent,
   transition type and overlap; `src/timeline.ts` gives frames. Read
   `references/motion-vocabulary.md` once: five moves, easing tokens, springs, stagger.
2. **Copy the helpers**: `assets/templates/motion.ts` into `src/`. If `src/Video.tsx`
   is still the layout template, replace it with `assets/templates/Video.tsx` (same
   series plus the loop wrap); if it was customised, patch the wrap in by hand (recipe
   in `references/loops-and-transitions.md`). `assets/templates/scenes/TextCard.tsx`
   shows an animated card.
3. **Animate each scene** from the local frame:
   `const frame = useCurrentFrame(); const { fps } = useVideoConfig();` then
   `presence()`/`enter()`/`exit()` for cards, `settle()` for icons, `evolvePath` for
   draw-on, `clamp01()` with an easing token for travel. Map each beat's `motion`
   intent to the vocabulary; grouped items use `enterGroup()` (≤ 4 items, whole
   cascade inside 0.5 s); keep every text card still for its readable window; pass
   `skipExit` when an overlapping transition does the handoff; animate `transform`,
   `opacity` and SVG geometry (dash offset, path, fill), never layout properties
   (`font-size`, `width`, `left`, padding).
4. **Transitions and loops**: the storyboard's `transition` per beat drives
   `TransitionSeries`; for `loop: true` the template appends the hook copy and shifts
   the series (recipe in `references/loops-and-transitions.md`).
5. **Lint, then look**:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/lint_motion.py" src
   npx remotion render src/index.ts <target> out/frames --sequence --image-format=png --frames=<a>-<b>
   ```
   Lint must report 0 errors. Render 10–15 frames around every transition and the
   loop seam (`P-5` to `P-1`, then `0` to `4`), tile them
   (`ffmpeg -pattern_type glob -i 'out/frames/*.png' -vf "scale=160:-2,tile=11x1" strip.png`)
   and open the strip. Fix anything that pops, jumps, strobes or moves under text.
6. **Hand off**: the list of moves per beat and anything the intent asked for that
   was toned down (and why). Next: `animation-export-presets`.

## Output spec

- Every scene animated from `useCurrentFrame()` with the helpers or the easing tokens;
  `lint_motion.py src` exits 0.
- Transition strips and, for loops, the wrap strip rendered and reviewed.
- No text moves during its readable window; the CTA beat is still.

## Gotchas

- Remotion renders frames in parallel tabs: CSS `transition`/`animation`, timers,
  `Date.now`, `Math.random`, GSAP/Motion do not animate or differ per frame. Use
  `random(seed)`; derive everything from the frame.
- `useCurrentFrame()` is local inside a `<Sequence>`; subtracting the beat's start
  again is the most common timing bug.
- `spring()` defaults overshoot; text takes `damping: 200`. Always pass `fps`.
- `interpolate` without `extrapolateRight: "clamp"` keeps going after the range.
- Enter from `scale(0.92)` or a short rise; never `scale(0)` or a hard pop.
- Stagger 2 frames at 30 fps for grouped items and cap the group at 4 so the whole
  cascade lands inside 0.5 s; one frame is a pop, five is a sequence of events. A text
  card never staggers.
- A full-frame pan under ~7 s strobes at 24–30 fps, and an eased pan peaks at about
  twice its average speed, so budget half of `maxPanPxPerFrame` for eased moves;
  shorten the travel or use `<CameraMotionBlur>` on that beat only (render time
  multiplies by `samples`).
- Never animate `font-size`, `width`, `left`: text reflows and line breaks jump.
- A loop is a period, not "last frame equals first": the last beat cross-fades into
  a hook copy and the series is shifted by the wrap; the wrap must be > 0 and ≥ the
  hook's complete entrance including any stagger (the template throws otherwise),
  and the wrap is always a fade.
- 60 fps doubles render time and most feeds play 30; keep the storyboard's fps.

## Pointers

- `scripts/lint_motion.py` — anti-pattern lint with line numbers; `--self-test`.
- `assets/templates/motion.ts` — `EASE`, `SPRING`, `enter`, `enterGroup`, `exit`, `presence`, `rise`, `scaleIn`, `settle`, `clamp01`, `maxPanPxPerFrame`.
- `assets/templates/Video.tsx` — TransitionSeries with the loop wrap; `scenes/TextCard.tsx` — animated card.
- `references/motion-vocabulary.md` — moves, tokens, springs, stagger, smoothness rules, determinism, sources.
- `references/loops-and-transitions.md` — series arithmetic, morphs, the loop recipe, strobing and motion blur.
