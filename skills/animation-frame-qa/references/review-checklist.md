# Review checklist for a rendered animation

Run `qa_frames.py`, then open every image it wrote. Each line below is answered by
looking, not by the script; the script only makes looking cheap and bounded. Mark
each item pass / fail / manual. A video is done when nothing is failed and nothing
is left unverified.

## 1. Poster frame (`phone-first.png`, `safe-first.png`)

- Frame 0 is what LinkedIn shows before play (custom thumbnails are desktop-only):
  the hook text is present and readable on its own, brand background in place.
- Nothing is mid-entrance at frame 0 unless the loop wrap put it there on purpose.

## 2. Legibility at phone width (`phone-*.png`, `phone-beat-<id>.png`)

- The stills are 390 px wide, the size of a phone feed; with `--storyboard` there is
  one settled still per beat, so every card gets read. Read every word without
  zooming. If you cannot, the layout tokens were bypassed: send it back with the beat ids.
- Smallest text ≥ the caption token (32 px at 1080 wide ≈ 11.5 logical px); body
  text ≥ 48 px; weights ≥ 500. Thin strokes that disappear here will disappear on
  the platform too (4:2:0 subsampling and a re-encode).
- Contrast is luminance, not hue: red-on-grey and blue-on-green text fringe.

## 3. Safe areas (`safe-first.png`, `safe-mid.png`, `safe-last.png`)

- Everything essential (text, logo, CTA, key icon) sits inside the red rectangle.
  Feed: 5% sides, 5% top, 12% bottom; vertical: 15% top, 35% bottom, 6% sides;
  slide: 5% all round (sources: EBU R95; Meta Reels guidance; LinkedIn "keep the
  edges free").
- Backgrounds may bleed; nothing you need to read may.

## 4. Pacing and stillness (`contact.png`)

- One idea per beat; each text card appears in at least one sample fully settled.
- No text is visibly mid-motion in consecutive samples that should be a hold.
- The CTA beat is still: the last row of the sheet should be near-identical frames.

## 5. Luminance jumps (`report.json` → `checks.luminance`)

- The report lists every frame-to-frame change in mean luminance of 40 or more (on
  0–255). Each one must be an intended cut or transition; a jump inside a beat is a bug
  (a frame rendered without fonts, a missing asset, a random value).
- This is a change detector, not a flash-safety test: it cannot see area-limited
  flashes, saturated-red flashes or ramps, and encoded mean luma is not WCAG relative
  luminance. Flash safety (WCAG 2.3.1: no more than three flashes in any one second)
  stays a manual judgement; keep the vocabulary of this repo to no flashing at all.

## 6. Loop seam (`wrap.png`, loops only)

- The strip shows the last five frames followed by the first five. Pose and
  direction of travel continue across the middle of the strip with no jump,
  no duplicated frame and no fade to background.

## 7. Delivery facts (`report.json` → `probe`)

- Width, height, fps and duration match the storyboard and the preset
  (`check_output.py` in the export skill already proved the container; this is a
  sanity read).

## 8. Credits

- If `ATTRIBUTION.md` has a credit line, it is either on screen (when the license
  demands it) or ready to paste into the post or closing slide.

## Routing a failure

| Symptom | Send to |
| --- | --- |
| text too small, clipped, outside the safe box, weak contrast | `vector-scene-layout` |
| pop, jerk, strobe, flicker, jump inside a beat, bad seam, text moving while readable | `smooth-motion-choreography` |
| wrong size/fps/codec, stalls, colour shift, GIF too big | `animation-export-presets` |
| too many ideas, beats too short to read, no CTA | `animation-storyboard` |

## Recording decisions

Every manual item is recorded into the report, so the orchestrator can tell reviewed
from merely generated:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/qa_frames.py" --record out/qa-linkedin-4x5/report.json "poster frame reads alone=pass" "CTA still=pass: frames 441-546 identical" "text inside safe box=fail: cta beat sits in the bottom band"
```

## Platform sanity (manual, outside the repo)

Codec inspection cannot prove platform acceptance, and this review is local visual
QA, not final delivery sign-off. LinkedIn has no self-only post mode on personal
profiles: preview in the composer without publishing, or use a test Company Page whose
audience you control, and never post unreleased client work to test. Insert the
PowerPoint file into a deck on the machine that will present it and play it once.
