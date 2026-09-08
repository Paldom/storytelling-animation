# Motion vocabulary for silent vector explainers

A closed set of moves with fixed timing. Every value is a pure function of
`useCurrentFrame()`; the helpers in `assets/templates/motion.ts` implement them.
Checked 2026-09-08 against the sources named.

## The five moves

| Move | What it does | Timing at 30 fps | Helper |
| --- | --- | --- | --- |
| **enter** | element appears: fade + rise (text) or fade + scale 0.92→1 (shapes) | 12 f (0.4 s), spring `damping: 200` for text, `settle` for icons | `enter`, `rise`, `scaleIn`, `settle` |
| **hold** | nothing moves on the element; the reading window | ≥ `max(1.33 s, 0.35 s × words)` per the storyboard | (do nothing) |
| **emphasis** | one settle, draw-on, colour fill, or count-up on the focal element | 8–15 f; springs `settle`/`pop` | `settle`, `evolvePath` |
| **camera** | the whole scene group translates or scales | ≥ 7 s per full frame-width of travel; slow-fast-slow | `maxPanPxPerFrame` |
| **exit** | element leaves: fade + short travel or scale to 0.96 | 9 f (0.3 s), `accelerate` | `exit`, `presence` |

Between beats, the storyboard's `transition` runs on `@remotion/transitions` with the
storyboard's overlap: `fade` (default), `slide`, `wipe`; `morph` is a fade plus
`interpolatePath` on the shared shape.

## Easing tokens (sources)

| Token | Cubic bezier | Use | Source |
| --- | --- | --- | --- |
| standard | (0.2, 0, 0, 1) | movement within the frame | Material 3 `md.sys.motion.easing.standard` |
| decelerate | (0, 0, 0, 1) | entrances | Material 3 standard-decelerate |
| accelerate | (0.3, 0, 1, 1) | exits | Material 3 standard-accelerate |
| emphasized-decelerate | (0.05, 0.7, 0.1, 1) | hero entrance | Material 3 |
| emphasized-accelerate | (0.3, 0, 0.8, 0.15) | hero exit | Material 3 |
| expressive | (0.4, 0.14, 0.3, 1) | playful brands | IBM Carbon expressive standard |

Material tokens: github.com/material-components/material-web `_md-sys-motion.scss`;
Carbon: github.com/carbon-design-system/carbon `packages/motion/src/dtcg/motion.json`.
Carbon's rule: "Do not use easing curves that suggest bounce, stretch, or sudden stops"
for productive motion; reserve expressive motion for a few important moments.

## Durations

| Design system | Tokens |
| --- | --- |
| Material 3 | short 50–200 ms, medium 250–400, long 450–600, extra-long 700–1000 |
| Carbon | fast 70/110 ms, moderate 150/240, slow 400/700 |
| Fluent 2 | 50–500 ms; "give larger elements more time than smaller elements" |

Video policy derived from these plus the storyboard contract: enter 0.4 s (12 f),
exit 0.3 s (9 f), emphasis 0.25–0.5 s, transitions 0.4–0.6 s, camera moves 1–3 s.
Nothing on screen should complete in under 4 frames (133 ms): it reads as a cut.

## Springs (Remotion `spring()`)

Remotion defaults `{ mass: 1, damping: 10, stiffness: 100 }` overshoot visibly. Presets:

| Preset | Config | For |
| --- | --- | --- |
| text | `damping: 200` | any text: lands with no bounce |
| settle | `damping: 18, stiffness: 140` | icons, cards: one small overshoot |
| pop | `damping: 12, stiffness: 180, mass: 0.8` | a single emphasis moment; never text |

Always pass `fps` from `useVideoConfig()`; a spring without it changes speed when the
fps changes. `durationInFrames` on `spring()` stretches the curve to an exact length.

## Stagger

Grouped elements enter 2 frames apart (67 ms at 30 fps), each over 9 frames, at
most 4 per group: the whole cascade lands in 15 frames (0.5 s). One frame apart reads
as a single pop; more than 5 frames reads as separate events. Material's guidance for
lists is tighter still ("no more than 20 ms apart", M1 choreography). A text card is
never staggered: it enters in 12 frames as one piece so its reading window starts on time.

## Smoothness rules

1. Animate `transform`, `opacity`, and SVG geometry (`stroke-dashoffset`, path `d`
   through `interpolatePath`, `fill`). Never `font-size`, `width`, `left`, `padding`:
   they reflow text and jump line breaks (and are slow). The linter flags them.
2. Use fractional transforms; integer-snapped slow drifts crawl.
3. Enter from `scale(0.92)` or a short rise, never from `scale(0)`.
4. No fast full-frame travel at 30 fps: a pan across the frame in under ~7 s
   judders (RED Digital Cinema's 7-second rule for 24 fps/180° shutter, a starting
   point for sharp synthetic frames; reddigitalcinema.com/red-101/camera-panning-speed).
   The rule bounds average speed; an eased pan peaks at roughly twice that, so check the
   largest per-frame displacement, not the duration. Shorten the travel or, if it must
   be fast, wrap it in `@remotion/motion-blur` `<CameraMotionBlur>` (each blur sample
   multiplies render time).
5. Text stays still while it is readable. Movement under text (parallax, particles)
   crawls after compression.
6. Idle elements may breathe (opacity ±0.05, scale ±0.01 over 2–3 s) only if the
   beat has no text; breathing under text reads as jitter at phone size.
7. The CTA beat holds still: no motion for the whole readable window.
8. 12 principles worth keeping in a vector explainer: anticipation (a 2–3 frame
   pull-back before a launch), follow-through (the settle), slow-in/slow-out (the
   easing tokens), arcs (paths, not straight lines, for travelling objects),
   secondary action (one, small), timing. Squash and stretch reads as cartoon: off by
   default for B2B (Thomas & Johnston, *The Illusion of Life*, 1981).

## Determinism (Remotion docs)

Frames render in parallel in several tabs, so every value must come from
`useCurrentFrame()` (remotion.dev/docs/flickering). Forbidden: CSS transitions and
animations, `setTimeout`, `requestAnimationFrame`, `Date.now`, `Math.random` (use
`random(seed)`), wall-clock libraries (GSAP, Motion, anime.js). `useCurrentFrame()`
is local inside a `<Sequence>`; never subtract the beat start again. `interpolate`
without `extrapolateRight: "clamp"` keeps extrapolating after the range.
