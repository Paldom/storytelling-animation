# Transitions and loops in Remotion

## TransitionSeries arithmetic

`<TransitionSeries>` overlaps neighbouring sequences by each transition's duration:
two 40-frame and 60-frame sequences with a 30-frame transition last
`40 + 60 − 30 = 70` frames (remotion.dev/docs/transitions/transitionseries). The
storyboard validator does the same subtraction, and `timeline.ts` exports
`totalFrames` from it: never compute the composition length any other way.

Presentations used here: `fade()` (default and for `morph`), `slide({direction})`,
`wipe({direction})`; timings `linearTiming({durationInFrames})` for cuts that
should feel neutral, `springTiming({config: {damping: 200}})` for a heavier, settled
handoff. Overlap frames come from the storyboard's `transition.overlap_s`.

## Morphs

A morph between two shapes needs both paths to have the same command count:
normalise with `@remotion/paths` (`normalizePath`, `reduceInstructions`) and then
`interpolatePath(progress, a, b)`. Morph only between shapes with matching node
counts; otherwise use a fade-through. Keep the morph inside the transition overlap
so the two beats share the shape.

## Loops (`storyboard.loop: true`)

Definition: with period `P = totalFrames`, frame `P` must equal frame `0` in pose
and velocity, and the stored last frame is `P − 1` (one step before the first
frame), never a copy of frame 0.

Implementation (`assets/templates/Video.tsx`):

1. The last beat's `transition.overlap_s` is the wrap overlap `w`.
2. After the last beat, append a `<TransitionSeries.Sequence durationInFrames={w}>`
   holding a copy of the hook scene, preceded by the last beat's transition.
3. Wrap the series in `<Sequence from={-w}>` so the cross-fade occupies composition
   frames `[P − w, P)` and finishes exactly at frame `P`.
4. Frame `0` of the composition is the hook at its local frame `w`, so the hook's
   entrance, including any group stagger, must be complete by then: `w ≥ ENTER_FRAMES`
   (12 at 30 fps; the template throws on less, and on a loop with no wrap at all). Give
   the wrap ≥ 0.5 s. The wrap is always a fade, whatever the beat's transition type.
5. A single-card loop is the same recipe with one beat: the card fades into itself.

Why this and not "make the last frame equal the first": duplicating the endpoint
frame is a visible one-frame hold, and equal endpoints with different velocities still
jerk. The cross-fade lands on the hook's settled pose at frame `P`; any velocity
mismatch is hidden inside the blend rather than shown as a cut. For the cleanest seam
keep the hook still during its first `w` frames and let the previous beat's exit be
the only motion.

Check the seam by rendering a wrap strip (frames `P − 5 … P − 1` then `0 … 4`); the
QA skill's `qa_frames.py --wrap` does this.

## Camera moves and strobing

Fast full-frame motion at 24–30 fps strobes because each frame is a sharp still.
RED's guideline for 24 fps with a 180° shutter: pan no faster than one image width
per 7 seconds as a starting point (reddigitalcinema.com/red-101/camera-panning-speed);
higher frame rates and motion blur relax it. Practical rules:

- Prefer short travel with overshoot-and-settle over long pans.
- Keep any pan ≤ `frameWidth / (7 × fps)` px per frame (`maxPanPxPerFrame`).
- If a fast move is the point, wrap the moving group in
  `<CameraMotionBlur shutterAngle={180} samples={10}>` from `@remotion/motion-blur`;
  each sample re-renders the frame, so keep it to the beat that needs it.
- Do not run text through a fast move; fade it out first.

Platforms accept 30 fps everywhere (LinkedIn ads recommend it); 60 fps doubles render
time and the feed may not play it back at 60. The project's fps is the storyboard's.
