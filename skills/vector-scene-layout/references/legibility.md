# Legibility at delivery size

Why the numbers in `frame_tokens.py` are what they are. Checked 2026-09-08.

## The phone is the display

The narrowest display these tokens support is a phone feed showing the video
**390 logical px wide** (a common phone viewport; narrower phones get proportionally
smaller text). A 1080 px wide video there is scaled by 390/1080, so
**1 logical px ≈ 2.77 video px**. Apple's typography minimums are in points, which on
iOS are logical pixels (developer.apple.com/design/human-interface-guidelines/typography):
11 pt minimum, 17 pt default body, "avoid light font weights". Converted:

| Role | logical px on the phone | Video px at 1080 wide | Weight |
| --- | --- | --- | --- |
| caption (smallest allowed) | ~11.5 | 32 | ≥ 500 |
| body | ~17 | 48 | ≥ 500 |
| headline | ~30 | 84 | ≥ 600 |
| display | ~43 | 120 | ≥ 700 |

Feed and vertical targets scale with **width** (`scale = width / 1080`): a 1920×1080
landscape post in the same 390 px feed column is scaled by 390/1920, so its text must
be 1.78× larger in video px to read the same, and the tokens do that (body 86 px, minimums round up).
Slide targets scale with **height** (`scale = height / 1080`): a projector fills the
height, and 48 px on a 1080p slide reads fine in a room. `phonePreviewScale` in the
tokens (= 390 / width) is the `--scale` that produces a phone-sized still.

Strokes: a 1 logical px hairline is 2.77 video px; after H.264 4:2:0 subsampling and
the platform's re-encode, anything under ~3 px at 1080 wide shimmers or vanishes.
Token `stroke.min` = 3 px, `stroke.regular` = 4 px, `stroke.bold` = 8 px at scale 1.

## Contrast

WCAG 2.1 SC 1.4.3 (w3.org/TR/WCAG21/#contrast-minimum): 4.5:1 for text, 3:1 for
large text (≥ 18 pt, or 14 pt bold), and SC 1.4.11: 3:1 for graphical objects. In
video, add two rules that come from encoding, not accessibility:

- Put contrast in **luminance**, not hue. 4:2:0 chroma subsampling halves colour
  resolution; thin saturated red or blue text on a contrasting hue fringes after the
  platform re-encode. Light text on a dark background is the safe default.
- Text over moving gradients, particles or video crawls after compression; put a
  flat plate behind it or keep the background still while text is up.

`frame_tokens.py contrast "#fg" "#bg"` prints the ratio and PASS/FAIL against 4.5:1;
`--large` applies 3:1, which only applies when the text is large *as displayed*: a
headline token (84 px at 1080 wide) is ~30 logical px on a phone, so it qualifies; a
body token does not.

## Safe areas

| Family | Top | Right | Bottom | Left | Basis |
| --- | --- | --- | --- | --- | --- |
| feed (LinkedIn 4:5, 1:1, 16:9; GIF) | 5% | 5% | 12% | 5% | EBU R95 graphics-safe 5% per edge (tech.ebu.ch/publications/r095); the 12% bottom band is a heuristic for feed controls — LinkedIn only says "keep the edges free of key elements" (linkedin.com/help/linkedin/answer/a554001) |
| vertical (9:16) | 15% | 6% | 35% | 6% | Meta Reels: "at least 14% of the top, 35% of the bottom, and 6% on each side" (facebook.com/business/ads-guide/update/video/instagram-reels); for taller custom sizes the top/bottom insets grow to keep essentials inside a centred 4:5 crop (`(height − 1.25 × width) / 2`) |
| slide (PowerPoint) | 5% | 5% | 5% | 5% | EBU R95 graphics-safe |

Nothing essential (text, logo, CTA) goes outside the safe rectangle; backgrounds and
decorative shapes may bleed to the edge.

## Line length and layout

- `maxCharsPerLine` in the tokens ≈ safe width / (0.55 × headline size): at 1080×1350
  that is 21 characters, i.e. two short lines for an 8-word card. Break lines by
  meaning, never mid-phrase.
- One focal element per beat; ≥ 60% of the frame is negative space in the clearest
  frame of a diagram-style explainer (a pattern in most Kurzgesagt-style samples).
- Frame 0 is the thumbnail on LinkedIn (custom thumbnails are desktop-only):
  design the hook beat's first readable frame as a poster.
- Loops must be designed so the last frame's pose equals the first frame's pose.

## Fonts

Load through `@remotion/google-fonts` (OFL fonts, embedded at render) or
`@remotion/fonts` for licensed files, and `await waitUntilDone()` behind
`delayRender()` before measuring text; otherwise early frames render in the
fallback font and the video swaps typefaces mid-play (remotion.dev/docs/fonts).
Use `@remotion/layout-utils` `fitText` for one-line headlines that must fit the
safe width; never animate `font-size` (reflow jumps lines).
