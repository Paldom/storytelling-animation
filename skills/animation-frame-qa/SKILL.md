---
name: animation-frame-qa
description: Reviews a rendered animation video at delivery size before sign-off - bounded contact sheet, phone-width stills, safe-area overlay, loop seam strip, luminance flash report, a look-at-it checklist with pass, fail or manual verdicts. Use when the user asks to check, review, QA, proof or sign off a rendered mp4 or gif, whether text reads on a phone, or which frames flash or strobe. Not for rendering.
license: MIT
---

# animation-frame-qa

Makes an agent look at the video it made, the way a viewer will see it, before it
says "done". It fixes the failure where a render that passed every script check
still ships with an unreadable phone view, a CTA under the feed controls, a hook
frame that is blank, a seam that jumps, or a flash nobody noticed because nobody
opened a frame.

## When to use / when NOT to use

Use on a finished MP4 or GIF when someone asks to review, check, QA, proof or sign
it off, when a client says text looks tiny, or when something flickers or strobes
and the frames need finding.

Do NOT use for: producing the files (`animation-export-presets`), fixing motion
(`smooth-motion-choreography`), fixing layout (`vector-scene-layout`), checking
colour pairs before layout (that skill's contrast command), code review, web
accessibility audits, extracting frames for other purposes, or film criticism.

## Workflow

1. **Produce the artefacts** into a fresh folder per deliverable (bounded: ≤ 60
   sampled frames, tiles scaled first, exact decoded frame count):
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/qa_frames.py" out/linkedin-4x5.mp4 --out out/qa-linkedin-4x5 --family feed --storyboard storyboard.json
   python3 "${CLAUDE_SKILL_DIR}/scripts/qa_frames.py" out/gif-loop.gif --out out/qa-gif-loop --family feed --storyboard storyboard.json --wrap
   ```
   `--family` is `feed` (LinkedIn 4:5, 1:1, 16:9, GIF), `vertical` (9:16) or `slide`
   (PowerPoint); `--storyboard` adds a settled phone-width still per beat; `--wrap`
   adds the loop seam strip. A non-zero exit means an artefact could not be made.
2. **Open every image** the script wrote: `contact.png`, `phone-first/mid/last.png`,
   `phone-beat-<id>.png`, `safe-first/mid/last.png`, `wrap.png`. Read `report.json`
   for the luminance jumps.
3. **Walk the checklist** in `references/review-checklist.md`: poster frame, phone
   legibility, safe areas, pacing and stillness, luminance jumps, loop seam, delivery
   facts, credits. Decide each item pass or fail with the frame numbers or beat ids.
4. **Record the decisions** into the report so the pipeline can tell reviewed from
   generated:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/qa_frames.py" --record out/qa-linkedin-4x5/report.json "poster frame reads alone=pass" "CTA still=pass"
   ```
5. **Route each failure** to the skill that owns it (table in the checklist) and
   re-run this review after the fix. Do not re-encode to fix a motion or layout defect.
6. **Close** only when every item is recorded pass. This is local visual QA; say so,
   and list what stays manual outside the repo (platform preview, presenter machine).

## Output spec

- `out/qa-<preset>/` per deliverable with the images and `report.json` whose checks
  are all recorded `pass`.
- A verdict per checklist item with evidence (frame numbers, which image), the
  routed fixes, and an explicit "not done" when anything failed or was unverified.

## Gotchas

- The contact sheet samples at most 60 frames: it shows pacing, not every frame.
  The luminance report covers every decoded frame but only mean luma; it finds cuts
  and broken frames, not flash safety, which stays a judgement call.
- Every luminance jump not at a storyboard transition is a defect (unloaded font,
  missing asset, random value).
- Old images in a reused folder are not evidence; the script refuses a non-empty
  `--out`.
- Judge legibility on the 390 px stills, never on the full-size frames; the full-size
  frames always look fine.
- Frame 0 is the thumbnail on LinkedIn; a fade-from-black hook means a black thumbnail.
- For loops, "last frame equals first frame" is wrong; the last frame is one step
  before the first. Judge the seam on the wrap strip's continuity, not on equality.
- `check_output.py` (export skill) proves the container; this skill proves the
  picture. Neither proves the platform accepted the upload: do a test post.
- Safe areas are heuristics from EBU R95, Meta Reels and LinkedIn's "keep the edges
  free"; a client's own overlay (subtitle band, watermark) may need more.

## Pointers

- `scripts/qa_frames.py` — artefacts + luminance report; `--storyboard`, `--wrap`, `--family`, `--record`, `--self-test`.
- `references/review-checklist.md` — the eight checks, sources, and the routing table.
