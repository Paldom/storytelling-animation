# Delivery specs behind the presets

Every number in `assets/presets.json` traces to a line here. Checked 2026-09-08 on
the vendor pages named; "policy" marks this skill's choice within the vendor's range.

## LinkedIn organic video (feed posts)

Source: linkedin.com/help/linkedin/answer/a548372 ("Video sharing troubleshooting") and
a7174587 ("Share videos on LinkedIn").

| Item | Vendor statement | Preset |
| --- | --- | --- |
| Formats | MP4, MOV, AVI, WEBM, MKV, WMV and others; ProRes "may upload but will not process" | MP4 |
| Codec | H.264 or VP8 (ads help a424737) | H.264 High |
| Size | 75 KB – 5 GB | cap 5 GB |
| Duration | 3 s (desktop) / 2 s (mobile) – 15 min; Company Pages 10 min (a1311816) | min 3 s, policy warn above 60 s |
| Resolution | 256×144 – 4096×2304 | 1080×1350 / 1080×1080 / 1080×1920 / 1920×1080 |
| Aspect | 1:2.4 – 2.4:1 | 4:5, 1:1, 9:16, 16:9 |
| Frame rate | 10 – 60 fps; ads: "Recommended frame rate: 30" | storyboard fps (30 default) |
| Bitrate | 192 Kbps – 30 Mbps | CRF 18 (~6–12 Mbps at 1080p for flat vector content) |
| Autoplay | muted (a565326) | no audio track by default |
| Captions | SRT/VTT upload, 47 chars/line, 3 lines | text is on screen already |
| Thumbnail | custom upload on desktop only | frame 0 is designed as the poster |
| Animated GIF | "Our video platform doesn't accommodate for animated GIFs" (a554001) | never deliver a GIF to LinkedIn |
| Safe zone | "Keep the edges free of key elements, text, and logos" | layout tokens handle it |

LinkedIn re-encodes uploads. CRF 18 is this skill's policy for the upload master:
in practice it keeps thin strokes and gradients through that second pass for flat
vector content, while lower values add bytes without visible gain. The checker also
enforces the platform floors a sparse vector clip can fall under: 75 KB minimum and
192 Kbps minimum bitrate. Ads recommend 4:5 at 1080×1350 and 15–30 s; videos under
30 s loop in the ad player until 30 s of playback (a424737).

## PowerPoint

Sources: support.microsoft.com "Video and audio file formats supported in PowerPoint"
(d8b12450), "Insert and play a video file from your computer" (f3fcbd3e), "Add an
animated GIF to a slide" (3a04f755), "Compress your media files".

| Item | Vendor statement | Preset |
| --- | --- | --- |
| Recommended format | ".mp4 files encoded with H.264 video and AAC audio" on Windows and Mac | H.264 High MP4, silent (add AAC only if the video has sound) |
| Other formats | WebM needs Web Media Extensions on Windows; WMV/AVI/MPEG-2 deprecated since version 2505 (converted on insert); HEVC, VP9 and ProRes are not listed | avoid |
| Web app | inserts files up to 256 MB; cannot play animated GIFs | cap 256 MB; no GIF for web decks |
| Compress Media | Windows only; 1080p/720p/480p; "embedded subtitles … are lost" | tell the user to leave it off |
| Play options | Start: In Click Sequence (default), Automatically, When Clicked On; Loop until Stopped; Rewind after Playing; Hide While Not Playing; Play Full Screen | set Automatically + Loop for loops |
| Transparency | only a Mac *export* option (HEVC) documents transparency; nothing documents inserting alpha video | bake the slide background colour into the render |

Policy: `-tune animation -crf 16 -g 30` (short GOP so PowerPoint's trim and scrubbing
land on the right frame; x264's animation tune raises deblocking and references for
flat colour), render 1080p for 1080p rooms and `--scale 2` (3840×2160) for 4K rooms
because PowerPoint's upscaling is soft. Colour tagging removes one cause of a visible
seam between the clip and the slide background (a BT.601 misread); it does not
guarantee a match if the deck's colour is managed differently.

## GIF (README, email, PowerPoint desktop)

Sources: ffmpeg.org/ffmpeg-filters.html#palettegen and #paletteuse.

- Two passes: `palettegen=stats_mode=diff` computes histograms "only for the part
  that differs from previous frame", which spends the 256 colours on what moves;
  `paletteuse=dither=bayer:bayer_scale=5` (bayer_scale 0–5, higher = less visible
  pattern) with `diff_mode=rectangle` re-encodes only the changing rectangle.
- 15 fps (Remotion's own guidance: GIFs commonly run 10–15 fps), ≤ 800 px wide,
  `-loop 0` = infinite (the checker verifies the NETSCAPE loop extension), policy cap 8 MB.
- 256 colours per frame: flat vector colour survives, gradients band. Keep GIF
  variants flat.

## Encoding rules used everywhere

- `yuv420p` and even dimensions: libx264 refuses odd sizes with 4:2:0
  ("width not divisible by 2"); QuickTime/PowerPoint players want 4:2:0.
- `-movflags +faststart` moves the `moov` atom before `mdat` so playback starts
  before the download finishes; the checker reads the atom order from the file.
- Colour tags: Remotion's `--color-space=bt709` converts and tags the matrix; the
  ffmpeg pass adds primaries and transfer through the `h264_metadata` bitstream
  filter (`colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1`,
  full-range flag 0) so no player guesses BT.601 and shifts brand colours, and a
  PowerPoint clip does not show a seam against the slide background.
- One master per composition (`--crf 10`, PNG frames; still a lossy 4:2:0 H.264, but
  visually clean for flat vector content) and one lossy pass per deliverable: two
  encodes total, never a chain. `render.py --input existing.mp4` re-encodes an existing
  file instead when only the delivery encoding is wrong.
- Reference ladder for bitrates (YouTube's recommended upload encoding, 1722171):
  1080p30 8 Mbps, 1080p60 12 Mbps, 2160p30 35–45 Mbps; CRF 16–18 lands under these
  for vector content.

## Custom sizes

Any even width × height at the storyboard's fps. Design at the custom size (the
layout skill's `frame_tokens.py --target custom --width W --height H`), do not
upscale a 1080 master. Portrait sizes with height/width greater than 2.4 are outside
LinkedIn's aspect range.
