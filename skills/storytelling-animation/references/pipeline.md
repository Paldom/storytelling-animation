# The pipeline: six skills, six gates

Each step is a sibling skill with its own SKILL.md; this file is the map. Run the
steps in order; a gate is a script exit code plus, where marked, eyes on an image.

| # | Skill | Reads | Writes | Gate (must pass before the next step) |
| --- | --- | --- | --- | --- |
| 1 | `animation-storyboard` | the brief | `storyboard.json` | `validate_storyboard.py storyboard.json` exits 0 |
| 2 | `vector-asset-sourcing` | storyboard `visual` fields | `public/**`, `assets/manifest.json`, `ATTRIBUTION.md` | `check_assets.py assets/manifest.json --root .` exits 0 |
| 3 | `vector-scene-layout` | storyboard, manifest | Remotion project, `animation.config.json` (license basis), `src/tokens.ts`, `src/timeline.ts`, `src/scenes/*.tsx`, `out/stills/` | `render_stills.py` exits 0 **and** every still viewed, per target |
| 4 | `smooth-motion-choreography` | scenes, `motion` intents | animated scenes, `src/motion.ts`, loop-aware `src/Video.tsx` | `lint_motion.py src` exits 0 **and** transition/seam strips viewed |
| 5 | `animation-export-presets` | compositions | `out/masters/`, `out/<preset>.mp4|gif` | `check_output.py` exits 0 for every deliverable |
| 6 | `animation-frame-qa` | deliverables | `out/qa-<target>/` images + `report.json` | every check recorded `pass` with `qa_frames.py --record` after looking |

`scripts/pipeline_status.py` reads these artefacts, re-runs the sibling validators it
finds, applies the freshness rules below, and prints the first open gate. What it
cannot see: whether anyone looked at a still or a strip. Recording a QA decision is
the only place a human judgement enters the evidence, which is why the QA gate
requires it.

## Project layout the skills agree on

```
<project>/
├── storyboard.json           # step 1 (the only copy; timeline.ts imports it)
├── assets/manifest.json      # step 2
├── ATTRIBUTION.md            # step 2, when a credit is required
├── animation.config.json     # step 3: remotion_license_basis, storyboard, targets
├── public/                   # step 2 assets
├── src/                      # steps 3-4
│   ├── tokens.ts  timeline.ts  fonts.ts  Video.tsx  SceneOnly.tsx  Root.tsx  motion.ts
│   └── scenes/<beatId>.tsx + index.ts
└── out/
    ├── stills/               # step 3
    ├── frames/               # step 4 strips
    ├── masters/  <target>.mp4|gif   # step 5 (gif-loop → .gif, everything else .mp4)
    └── qa-<target>/          # step 6, one fresh folder per deliverable
```

## Change propagation

A change re-opens every gate downstream of the file it touches. `pipeline_status.py`
enforces the file-time version of this: stills, deliverables and QA reports older than
`storyboard.json` or any `src/` file are reported as stale. Scene files are shared by
every target, so a scene edit reopens layout for all targets:

| Changed | Re-run from |
| --- | --- |
| brief, text, beat timing, loop, targets | step 1 (then everything) |
| an icon, illustration or font | step 2 → 3 (stills) → 4 (strips) → 5 → 6 |
| a scene's layout | step 3 stills for that target → 4 → 5 → 6 |
| motion only | step 4 strips → 5 → 6 |
| encoding only | step 5 → 6 |

Never patch downstream to hide an upstream defect: a card that is unreadable on the
phone is a layout fix, not a QA note; a jump at the seam is a motion fix, not a
re-encode.

## Preconditions

- Node ≥ 18 with npm/npx; ffmpeg and ffprobe on PATH; Python 3.10+.
- Network for the one-time scaffold (`npx create-video@4.0.522 --blank`) and for
  Google Fonts at render time unless fonts are copied locally.
- Remotion license basis known: free for individuals, companies of ≤ 3 people
  and non-profits; otherwise a Company License (remotion.pro/license). Step 3
  records it; step 5 refuses to render without it.
- The official `remotion-dev/skills` installed for API questions the siblings do not cover.

## What "done" means

Every gate passed for every target, the deliverables and `ATTRIBUTION.md` (if any)
listed with their intended destination and handling notes, the license basis
stated, and the manual steps named: a test upload to LinkedIn, a test insert on the
presenting machine.
