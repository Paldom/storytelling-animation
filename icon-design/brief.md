# Icon brief: storytelling-animation
Assumptions: autonomous run; no brand colour exists, the house palette applies; the mark must read next to Remotion-, ffmpeg- and LinkedIn-adjacent repos in a skills.sh listing.
Product: Agent Skills that turn a written brief into a smooth vector storytelling animation video (storyboard → scenes → motion → LinkedIn/PowerPoint export → frame QA)  ·  Audience: developers and marketers using coding agents  ·  Category neighbors: play triangles, film strips, clapperboards, speech bubbles, timeline bars, Remotion's blue square, Lottie's green blob

## Concepts
### 1. Beat sheet  (axis: vertical)
Depicts: a stacked storyboard
Metaphor: three film frames climbing a stair, the top one filled: the story advances beat by beat and the last beat lands.
Gestalt device: continuity (the diagonal the three frames make)
16px risk: three frames merge into a blob; the diagonal survives only if gaps stay ≥ 1/16 of the glyph.
Distinct from: a film strip (no sprocket holes, no horizontal band), a timeline bar (frames are squares, not ticks).
Not a UI glyph: checked against "stacked chevrons" and "layers/copy": squares climb rather than stack in place.

### 2. Speaking frame  (axis: vertical)
Depicts: a film frame with a tail
Metaphor: one rounded frame with a speech-bubble tail: the frame is what speaks (text is the narration in a muted feed).
Gestalt device: closure (the tail completes the bubble the eye expects)
16px risk: the tail thins to nothing; needs a tail ≥ 3/32 of the glyph width.
Distinct from: a plain speech bubble (frame has a filled inner panel), a clapperboard (no hinge).
Not a UI glyph: checked against "comment/chat" bubbles: this is a rectangle with a short tail and a filled inner card, not the rounded chat blob.

### 3. Rising card  (axis: vertical)
Depicts: a card lifting off a base
Metaphor: a text card rising from a baseline with a motion trail: the enter move every scene starts with.
Gestalt device: figure-ground (the trail is cut from the card's shadow)
16px risk: the trail lines vanish; the card alone becomes a plain rounded rectangle.
Distinct from: upload arrows (no arrowhead), stacked layers (one card, one base).
Not a UI glyph: checked against "upload" and "eject": there is no triangle and no arrow.

### 4. Loop seam  (axis: horizontal)
Depicts: a film frame bent into a loop
Metaphor: a frame whose right edge feeds back into its left: seamless loops for slides.
Gestalt device: continuity
16px risk: the loop reads as a refresh icon.
Distinct from: refresh (no arrowhead), infinity (a rectangle, not two lobes). Borderline; likely killed by the UI-glyph check.
Not a UI glyph: fails the "refresh" check at 16 px, keep only if drawn without any arrowhead and rejected if it still reads as refresh.

## Palette
Background #2A2A2E · Glyph #E8E8EA · Accent #4F8CFF (used on at most one element: the landed frame or the inner card)

## Recommendation
Concept 1 (Beat sheet): it is the only mark that says "story with beats" as a silhouette, survives 16 px as three squares on a diagonal, and wears none of the category's clichés. Concept 2 is the runner-up (speaks to "text is the narration"). Draw 1 and 2 with icon-draw and critique both.
