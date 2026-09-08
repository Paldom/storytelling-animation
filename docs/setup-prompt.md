# Setup prompt: produce an animation with these skills

Paste the block below as a `/goal` in Claude Code inside an empty project folder,
after installing the skills (`npx skills add Paldom/storytelling-animation`). Replace
the bracketed parts. It orders the six pipeline skills, gates each step on its
verifier, only parallelises work on disjoint files, and never touches git.

```text
/goal Produce a finished vector storytelling animation from the brief below using the storytelling-animation skills, one gated step at a time. Never run git commit or git push. Work in this folder only.

Brief: [one paragraph: message, audience, CTA text and URL]
Brand: [background hex, text hex, accent hex, font family or "none"]
Targets: [linkedin-4x5 | linkedin-1x1 | linkedin-9x16 | linkedin-16x9 | pptx-16x9 | pptx-4k | gif-loop | custom WxH]
Length: [e.g. under 30 s | exactly 8 s loop]
Verbatim sentences: [none | "..."]
Remotion license basis: [individual | company-of-3-or-fewer | non-profit | company-license:<id>]

Steps and gates (do not start a step until the previous gate passes):
1. /animation-storyboard: write storyboard.json from the brief. Gate: python3 <skill>/scripts/validate_storyboard.py storyboard.json exits 0. Print the summary. Stop and ask me only if the brief is missing a required fact from the checklist.
2. /vector-asset-sourcing: one icon pack, licensed assets under public/, assets/manifest.json, ATTRIBUTION.md. Gate: check_assets.py assets/manifest.json --root . exits 0.
3. /vector-scene-layout: scaffold with npx create-video@4.0.522 --blank, write animation.config.json with the license basis above, generate src/tokens.ts, copy the templates, one static scene per beat. Gate: render_stills.py storyboard.json --target <each target> exits 0 AND you open every still (full size and --phone) and confirm text is inside the safe box and readable. Scenes for different beats may be written in parallel by separate agents; Root.tsx, Video.tsx, timeline.ts and tokens.ts are single-owner.
4. /smooth-motion-choreography: animate each scene from useCurrentFrame() with the helpers; transitions and loop wrap from the storyboard. Gate: lint_motion.py src exits 0 AND you render and look at a strip around every transition (and the loop seam if looping).
5. /animation-export-presets: render.py --project . --preset <each target> (it checks each file before publishing it). Gate: every requested preset reports published.
6. /animation-frame-qa: qa_frames.py out/<target>.<ext> --out out/qa-<target> --family <feed|vertical|slide> --storyboard storyboard.json [--wrap]. Gate: no fail, and every manual item recorded pass with qa_frames.py --record after you looked at the images. Route any defect to the owning step and re-run every downstream gate.

Run python3 <storytelling-animation skill>/scripts/pipeline_status.py --project . whenever you resume, and before claiming done.

Done means: every gate passed for every target; out/<preset> files listed with their destination and handling notes (PowerPoint: Start Automatically, Loop until Stopped, no Compress Media; LinkedIn: MP4 upload plus the credit line from ATTRIBUTION.md in the post text if one exists); the governing idea and anything dropped from the brief stated; the manual steps left for me (test upload, presenter machine) listed. If a gate cannot pass, say which one and why instead of working around it.
```

Notes:

- `<skill>` paths resolve to wherever the skills were installed (Claude Code exposes
  each as `${CLAUDE_SKILL_DIR}` inside that skill); the orchestrator skill's body
  gives the exact commands, so the prompt names them only as gates.
- The whole prompt stays under 4,000 characters so it fits a single `/goal`.
- Do not add "commit when done": the repo convention is that the owner reviews and
  commits every change.
