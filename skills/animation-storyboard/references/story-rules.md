# Story rules for silent-autoplay explainers

Verified 2026-09-08 against the sources linked. Numbers marked *policy* are this
skill's defaults, chosen from the sources; everything else is quoted guidance.

## Shape of the story

- One governing idea per video, stated in one sentence before any beat is written.
  A viewer who saw it once should be able to repeat that sentence.
- Default arc for a product or process explainer: **problem → shift → outcome → CTA**
  (hook shows the problem; the "shift" is the moment the solution appears).
  Agency guidance: one idea per 15 s is comfortable, per 10 s is brisk; a consistent
  drop-off point is almost always two ideas compressed into one scene
  (educationalvoice.co.uk/animated-storytelling, updated 2026-09-07).
- The storyboard is "the finished animation with movement removed": if a beat fails
  as a still image with its caption, it fails animated. Sign off the storyboard
  before layout; changes are cheap here and expensive after motion.
- Hold one visual metaphor for the whole piece. A metaphor that changes mid-video
  reads as a new video.
- Withhold the accent/brand colour until the solution beat; halt all motion during
  the CTA (pattern in 6 of 7 sampled B2B explainers, advids.co, 2026-07-01; small sample).

## Platform facts that drive timing

| Fact | Value | Source |
| --- | --- | --- |
| LinkedIn feed autoplay is muted | "may play automatically without sound" | linkedin.com/help/linkedin/answer/a565326 |
| Mobile viewers without sound | 92% | LinkedIn Marketing Blog, 2025-06-05 |
| Attention window | "first six seconds" (organic blog); "first 10 seconds" (video ad tips) | linkedin.com/business/marketing/blog…13-top-tips…; business.linkedin.com…/video-ad-tips |
| Short beats completion | 7–15 s videos "up to a 300% lift in completion" (ads) | business.linkedin.com…/video-ad-tips |
| Organic minimum duration | 3 s desktop upload, 2 s mobile app | linkedin.com/help/linkedin/answer/a7174587 |
| Organic maximum | 15 min (Pages: 10 min) | a7174587; a1311816 |
| Ads duration / fps | 3 s–30 min; "Recommended frame rate: 30" | business.linkedin.com/advertise/ads/sponsored-content/video-ads/specs |
| Loop behaviour (ads) | videos under 30 s loop until 30 s of playback | linkedin.com/help/lms/answer/a424737 |
| PowerPoint playback | embedded MP4 plays on click or automatically, can loop | support.microsoft.com "Set the play options for a video" |

Policy budgets used by the validator (seconds: minimum / warn above / maximum):
`linkedin 3 / 60 / 90`, `pptx 1 / 120 / 300`, `gif 1 / 8 / 15`, `custom 1 / 120 / 900`.

## On-screen text is the narration

Text cards replace voice-over, so reading speed sets the clock.

| Guidance | Value | Source |
| --- | --- | --- |
| BBC subtitle speed | 160–180 wpm, i.e. 0.33–0.375 s per word; minimum ≈0.3 s/word | bbc.co.uk/accessibility/forproducts/guides/subtitles (v1.2.3, 2024) |
| Netflix timed text | ≤20 characters/s adults, ≤17 children; 42 chars/line; max 2 lines; 5/6 s min, 7 s max per event | partnerhelp.netflixstudios.com (General Requirements, 2024-06-28) |
| DCMP captioning key | minimum 40 frames (1 s 10 f), maximum 6 s | dcmp.org/learn/597 |

Policy derived from these, enforced by `validate_storyboard.py`:

- `readable = duration − 0.4 s enter − 0.3 s exit − overlaps` must be ≥ `max(1.33 s, 0.35 s × words, characters / 20)`, computed in whole frames.
- ≤ 8 words and ≤ 64 characters per card: a headline, not a subtitle.
- No card shorter than 1.33 s of readable time; nothing needs more than ~7 s. `verbatim: true` lifts the word cap to 20 for sentences that must appear word for word.
- The hook beat carries text: frame 0 is the thumbnail and the first second is the pitch.

## Beat count by length (policy)

| Total | Beats | Notes |
| --- | --- | --- |
| 6–10 s loop | 1–2 | one card, one motion, seamless wrap |
| 15–30 s feed post | 4–6 | hook, 2–3 body, CTA |
| 30–60 s explainer | 6–10 | problem, cost, shift, how (2–4), outcome, CTA |
| 60–90 s | 10–14 | only when the brief demands it; flag it |

## Loops

A loop's period is the whole video: frame `N` must equal frame `0` in pose and
velocity, so the last beat hands off to the first with a fade or matching pose,
never a cut. The stored last frame is one step *before* the first frame, not a copy
of it (a copied frame is a visible stutter).

## Brief checklist (ask only what is missing)

1. What should the viewer believe or do after watching?
2. Where is it watched: LinkedIn feed (muted, phone), a slide (projector, big room), elsewhere?
3. Target length, or "as short as it can be".
4. Sentences that must appear verbatim (legal, brand claims).
5. Brand colours and font, if any; existing assets to reuse.
6. Loop or play once; CTA text and URL.
