#!/usr/bin/env bash
# Regenerates assets/demo/example.gif and contact-sheet.png from the example storyboard by
# running the pipeline's own scripts on a throwaway Remotion project. Needs Node 18+,
# ffmpeg/ffprobe, Python 3.10+, and network for the one-time scaffold.
# Run from anywhere: bash assets/demo/regenerate.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="${WORK:-/tmp/storytelling-animation-demo}"
rm -rf "$WORK"
npx -y create-video@4.0.522 --yes --blank "$WORK" >/dev/null
cd "$WORK"
npm i --silent --save-exact @remotion/transitions@4.0.522 @remotion/google-fonts@4.0.522 @remotion/paths@4.0.522
python3 - <<'PY'
import json, pathlib
t = pathlib.Path("tsconfig.json"); d = json.loads(t.read_text()); d["compilerOptions"]["resolveJsonModule"] = True; t.write_text(json.dumps(d, indent=2))
PY
cp "$REPO/skills/animation-storyboard/assets/storyboard.example.json" storyboard.json
python3 - <<'PY'
import json, pathlib
s = json.loads(pathlib.Path("storyboard.json").read_text()); s["targets"] = ["linkedin-4x5"]; pathlib.Path("storyboard.json").write_text(json.dumps(s, indent=2))
pathlib.Path("animation.config.json").write_text(json.dumps({"version": 1, "remotion_license_basis": "individual", "storyboard": "storyboard.json", "targets": ["linkedin-4x5"]}))
PY
python3 "$REPO/skills/animation-storyboard/scripts/validate_storyboard.py" storyboard.json
python3 "$REPO/skills/vector-scene-layout/scripts/frame_tokens.py" --target linkedin-4x5 --ts > src/tokens.ts
cp -R "$REPO/skills/vector-scene-layout/assets/templates/"* src/
cp "$REPO/skills/smooth-motion-choreography/assets/templates/motion.ts" "$REPO/skills/smooth-motion-choreography/assets/templates/Video.tsx" src/
cp "$REPO/skills/smooth-motion-choreography/assets/templates/scenes/TextCard.tsx" src/scenes/
cat > src/scenes/index.ts <<'TS'
import type React from "react";
import type { SceneProps } from "./Scene";
import { TextCard } from "./TextCard";
export const scenes: Record<string, React.FC<SceneProps>> = { hook: TextCard, cost: TextCard, shift: TextCard, outcome: TextCard, cta: TextCard };
TS
rm -f src/Composition.tsx
python3 "$REPO/skills/smooth-motion-choreography/scripts/lint_motion.py" src
python3 "$REPO/skills/animation-export-presets/scripts/render.py" --project . --preset linkedin-4x5
python3 "$REPO/skills/animation-frame-qa/scripts/qa_frames.py" out/linkedin-4x5.mp4 --out out/qa-linkedin-4x5 --family feed --storyboard storyboard.json
# README GIF straight from the master (the 18 s example is longer than the GIF preset's 15 s policy).
ffmpeg -v error -y -i out/masters/linkedin-4x5.mp4 -vf "fps=15,scale=640:-2:flags=lanczos,palettegen=stats_mode=diff" out/palette.png
ffmpeg -v error -y -i out/masters/linkedin-4x5.mp4 -i out/palette.png -lavfi "fps=15,scale=640:-2:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" -loop 0 "$REPO/assets/demo/example.gif"
cp out/qa-linkedin-4x5/contact.png "$REPO/assets/demo/contact-sheet.png"
echo "regenerated $REPO/assets/demo/"
