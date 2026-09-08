# Remotion project structure for a storyboard-driven animation

## Scaffold (once per animation)

```bash
npx create-video@4.0.522 --blank my-animation      # same version as the packages below
cd my-animation
npm i --save-exact @remotion/transitions@4.0.522 @remotion/google-fonts@4.0.522 @remotion/paths@4.0.522
npx skills add remotion-dev/skills                  # official Remotion API skills for the agent
```

`create-video` writes `package.json` with exact versions and a lockfile. Keep
`remotion`, `@remotion/cli` and every `@remotion/*` package on the same version.

Write `animation.config.json` in the project root before anything renders:

```json
{
  "version": 1,
  "remotion_license_basis": "individual | company-of-3-or-fewer | non-profit | company-license:<id>",
  "storyboard": "storyboard.json",
  "targets": ["linkedin-4x5", "pptx-16x9"]
}
```

`remotion_license_basis` records why this project may use Remotion. Remotion is free
for individuals, companies with up to 3 employees (contractors count), and
non-profits; every other organisation needs a Company License
(remotion.pro/license, github.com/remotion-dev/remotion/blob/main/LICENSE.md). The
export step refuses to render without this field.

## Files

```
my-animation/
├── animation.config.json     # license basis, storyboard path, targets
├── storyboard.json           # the validated contract (copied from the storyboard step)
├── assets/manifest.json      # from vector-asset-sourcing
├── public/                   # icons/, illustrations/, lottie/ (copied, never fetched)
└── src/
    ├── index.ts              # registerRoot (from the template)
    ├── Root.tsx              # one <Composition id={target}> per target
    ├── tokens.ts             # generated: frame_tokens.py --ts
    ├── timeline.ts           # beats -> frame schedule, from storyboard.json
    ├── fonts.ts              # loadFont() + waitUntilDone()
    ├── Video.tsx             # TransitionSeries over the beats
    ├── SceneOnly.tsx         # one beat alone, for isolated layout stills
    └── scenes/<beatId>.tsx   # one static scene per beat
```

Templates for `Root.tsx`, `timeline.ts`, `fonts.ts`, `Video.tsx`, `SceneOnly.tsx`
and an example scene are in `assets/templates/`; copy them, then edit the scenes only.

## How the pieces connect

- `tokens.ts` — generated per target; scenes read sizes from `tokensFor(target)`,
  never from literals. Regenerate when a target is added.
- `timeline.ts` — imports `storyboard.json` and applies the same rounding as the
  validator (`Math.floor(s * fps + 0.5)`); exports `beats[]` with
  `durationInFrames`, `overlapOutFrames`, `startFrame`, and `totalFrames`.
  The composition's `durationInFrames` comes from here, never typed by hand.
- `Video.tsx` — a `<TransitionSeries>`: one `<TransitionSeries.Sequence>` per beat,
  a `<TransitionSeries.Transition>` between beats whose `overlapOutFrames > 0`
  (`linearTiming({durationInFrames: overlap})`, presentation from the storyboard's
  `transition.type`). At the layout stage every scene is static; motion comes later.
- `Root.tsx` — for each target in `animation.config.json`, a `<Composition>` with
  `id={target}`, `width/height` from the tokens, `fps` and `durationInFrames` from
  `timeline.ts`, `defaultProps={{target}}`; plus one `<target>--<beatId>` composition
  per beat rendering `SceneOnly`, so a still never contains a neighbour or transition.
- Loops (`storyboard.loop: true`): the period is `totalFrames`; the wrap overlap is
  handled by the motion step (the last beat's tail cross-fades into the hook), the
  layout step only keeps the first and last poses identical.

## Verify on stills

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/render_stills.py" storyboard.json --target linkedin-4x5 --out out/stills
python3 "${CLAUDE_SKILL_DIR}/scripts/render_stills.py" storyboard.json --target linkedin-4x5 --phone --out out/stills-phone
```

Look at every still (the agent can read PNG files). Check: text inside the safe
rectangle, sizes at or above tokens, one focal element, contrast, nothing clipped.
Fix the scene, re-render, look again. Only then hand off to motion.
