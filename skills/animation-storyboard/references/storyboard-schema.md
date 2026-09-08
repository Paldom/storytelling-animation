# storyboard.json — contract v1

One JSON object. Every later skill (layout, motion, export, QA) reads this file and
nothing else about the story. Validate with
`python3 "${CLAUDE_SKILL_DIR}/scripts/validate_storyboard.py" storyboard.json`.

## Top level

| Field | Type | Rule |
| --- | --- | --- |
| `version` | int | must be `1` |
| `title` | string | non-empty; display only (file names come from target ids and beat ids) |
| `fps` | int | 24–60; `30` is the default for every preset |
| `targets` | string[] | preset ids, first one is primary: `linkedin-4x5`, `linkedin-1x1`, `linkedin-9x16`, `linkedin-16x9`, `pptx-16x9`, `pptx-4k`, `gif-loop`, `custom` |
| `loop` | bool | `true` makes the last beat hand off to the first (period = whole video); loops may have a single beat |
| `custom_size` | object | required with target `custom`: `{ "width", "height" }` in even pixels |
| `max_duration_s` | number | optional cap the client asked for; validation fails above it |
| `exact_duration_s` | number | optional exact length (loops, slots); validation fails unless the frame total matches |
| `brand` | object | optional: `background`, `text`, `accent` (hex), `font` (family name), free-form extras |
| `beats` | object[] | ≥ 2 (≥ 1 when `loop` is true), in playback order |

## Beat

| Field | Type | Rule |
| --- | --- | --- |
| `id` | string | unique, `^[a-z][a-z0-9-]{0,31}$` (no underscore: it becomes a Remotion composition id), names the scene component and still files |
| `role` | `hook` \| `body` \| `cta` | first beat must be `hook`; last should be `cta` |
| `duration_s` | number > 0 | whole frames at `fps` preferred (`3.5` at 30 fps = 105 frames) |
| `text` | string | ≤ 8 words, ≤ 64 chars; empty string for a purely visual beat |
| `verbatim` | bool | optional; `true` for sentences that must appear word for word (legal, brand): raises the cap to 20 words / 160 chars, the hold still scales with length |
| `visual` | string | what is on screen at the beat's clearest moment (the storyboard still) |
| `motion` | string | intent only ("rows slide in, then jam"); the motion skill owns the vocabulary |
| `transition` | object | `{ "type": "cut" \| "fade" \| "slide" \| "wipe" \| "morph" \| "none", "overlap_s": number ≥ 0 }` — how this beat hands off to the **next** one |

## Timing math (the validator's rules)

- Quantise first: `frames = floor(seconds × fps + 0.5)` for every `duration_s` and
  `overlap_s`; all other rules run on those integers, and the validator's summary
  (`start_f`, `frames`, `overlap_in_f`, `overlap_out_f`, `total_frames`) is the
  schedule downstream code must reproduce (`timeline.ts` uses the same rounding).
- Total frames: `Σ frames − Σ overlap frames` (overlaps are shared time, as in
  Remotion's `TransitionSeries`). With `loop: true` the last beat's overlap is subtracted
  too: its tail cross-fades into the first beat, so frame `total_frames` equals frame 0.
- Readable hold per text card, in frames: `frames − enter(0.4 s) − exit(0.3 s) −
  overlap_in − overlap_out` must be ≥ `ceil(max(1.33, 0.35 × words, chars / 20) × fps)`.
- `cut` and `none` transitions cannot overlap; the last beat cannot overlap unless
  `loop` is true.
- Length budgets by target family (min / warn / max seconds):
  linkedin 3/60/90 · pptx 1/120/300 · gif 1/8/15 · custom 1/120/900.

## Minimal valid example

```json
{
  "version": 1,
  "title": "Demo",
  "fps": 30,
  "targets": ["linkedin-4x5"],
  "loop": false,
  "beats": [
    { "id": "hook", "role": "hook", "duration_s": 3, "text": "Still copying data by hand?",
      "visual": "two windows, rows dragged between them", "motion": "rows slide, then jam",
      "transition": { "type": "fade", "overlap_s": 0.4 } },
    { "id": "cta", "role": "cta", "duration_s": 3, "text": "Sync it in one click",
      "visual": "logo and URL, still", "motion": "fade in, hold" }
  ]
}
```

A fuller example with brand tokens and five beats: `assets/storyboard.example.json`.
