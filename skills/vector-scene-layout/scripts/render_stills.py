#!/usr/bin/env python3
"""Render one still per storyboard beat with `npx remotion still`, scene by scene.

Layout is judged on stills. Each beat is rendered from its own composition
`<target>--<beatId>` (registered by the Root template) at the beat's local
midpoint, so no transition, neighbour or loop wrap is blended into the picture.

Usage:
    python3 render_stills.py storyboard.json --target linkedin-4x5 [--entry src/index.ts] [--out out/stills]
    python3 render_stills.py storyboard.json --target linkedin-4x5 --phone      # 390 px wide previews
    python3 render_stills.py storyboard.json --target custom --width 1440 --phone
    python3 render_stills.py storyboard.json --target linkedin-4x5 --dry-run    # print commands only
    python3 render_stills.py --self-test

Exit codes: 0 = all stills rendered, 1 = a render failed or the storyboard is unusable.
Stdlib only; needs Node + the project's Remotion install on PATH via npx.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

from frame_tokens import PHONE_WIDTH, TARGETS

ID_RE = re.compile(
    r"[a-z][a-z0-9-]{0,31}"
)  # same as the storyboard validator; Remotion ids allow no underscore


def to_frames(seconds: float, fps: int) -> int:
    """Must match animation-storyboard/scripts/validate_storyboard.py."""
    return math.floor(seconds * fps + 0.5)


def beat_frames(storyboard: dict) -> list[tuple[str, int, int]]:
    """Return (beat id, start frame, LOCAL midpoint frame) per beat; overlaps subtract."""
    fps = int(storyboard["fps"])
    start = 0
    out = []
    seen: set[str] = set()
    for beat in storyboard["beats"]:
        bid = str(beat["id"])
        if not ID_RE.fullmatch(bid) or bid in seen:
            raise ValueError(
                f"beat id {bid!r} is not a safe unique id; validate the storyboard first"
            )
        seen.add(bid)
        dur = to_frames(float(beat["duration_s"]), fps)
        overlap = to_frames(float(beat.get("transition", {}).get("overlap_s", 0) or 0), fps)
        out.append((bid, start, dur // 2))
        start += dur - overlap
    return out


def still_command(
    entry: str, composition: str, out_png: Path, frame: int, scale: float
) -> list[str]:
    return [
        "npx",
        "remotion",
        "still",
        entry,
        composition,
        str(out_png),
        f"--frame={frame}",
        f"--scale={scale}",
        "--image-format=png",
        "--log=error",
    ]


def run_group(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run in its own process group so a timeout also kills the browser npx started."""
    with subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
    ) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if hasattr(os, "killpg"):
                os.killpg(proc.pid, signal.SIGKILL)
            else:  # pragma: no cover - Windows has no process groups this way
                proc.kill()
            proc.wait()
            raise
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def self_test() -> None:
    sb = {
        "fps": 30,
        "beats": [
            {"id": "a", "duration_s": 3, "transition": {"type": "fade", "overlap_s": 0.5}},
            {"id": "b", "duration_s": 4},
            {"id": "c", "duration_s": 2.5, "transition": {"overlap_s": 0}},
        ],
    }
    assert beat_frames(sb) == [("a", 0, 45), ("b", 75, 60), ("c", 195, 37)], beat_frames(sb)
    cmd = still_command("src/index.ts", "linkedin-4x5--a", Path("out/a.png"), 45, 1.0)
    assert cmd[:3] == ["npx", "remotion", "still"] and "--frame=45" in cmd
    sb["beats"][1]["id"] = "../x"
    try:
        beat_frames(sb)
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe ids must be rejected")
    assert TARGETS["linkedin-16x9"][0] == 1920 and PHONE_WIDTH == 390
    print("self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "storyboard",
        nargs="?",
        type=Path,
        help="must be the project's storyboard.json (the one timeline.ts imports)",
    )
    ap.add_argument("--project", type=Path, default=Path("."), help="Remotion project root")
    ap.add_argument(
        "--target",
        help="target id (e.g. linkedin-4x5); per-beat compositions are <target>--<beatId>",
    )
    ap.add_argument("--entry", default="src/index.ts")
    ap.add_argument("--out", type=Path, default=Path("out/stills"))
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument(
        "--phone",
        action="store_true",
        help=f"scale so the still is {PHONE_WIDTH} px wide (a phone feed)",
    )
    ap.add_argument(
        "--width", type=int, help="composition width, needed with --phone for a custom target"
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.storyboard is None or not args.target:
        ap.error("storyboard path and --target are required")
    if not re.fullmatch(r"[a-z0-9-]+", args.target):
        ap.error("target must be a preset id such as linkedin-4x5")
    scale = args.scale
    if args.phone:
        width = args.width or (TARGETS[args.target][0] if args.target in TARGETS else None)
        if not width:
            ap.error("--phone with a custom target needs --width")
        scale = round(PHONE_WIDTH / width, 4)
    project_sb = (args.project / "storyboard.json").resolve()
    if args.storyboard.resolve() != project_sb:
        print(
            f"ERROR {args.storyboard} is not the project's storyboard ({project_sb}); timeline.ts imports "
            "that file, so stills would come from a different storyboard than the one you validated",
            file=sys.stderr,
        )
        return 1
    try:
        sb = json.loads(args.storyboard.read_text(encoding="utf-8"))
        beats = beat_frames(sb)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR cannot use {args.storyboard}: {exc}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for beat_id, _start, mid in beats:
        composition = f"{args.target}--{beat_id}"
        png = args.out / f"{composition}.png"
        cmd = still_command(args.entry, composition, png, mid, scale)
        if args.dry_run:
            print(" ".join(cmd))
            continue
        try:
            proc = run_group(cmd, timeout=600)
        except subprocess.TimeoutExpired:
            failed += 1
            print(
                f"FAIL {beat_id}: render timed out after 600 s (process group killed)",
                file=sys.stderr,
            )
            continue
        if proc.returncode != 0 or not png.is_file():
            failed += 1
            print(f"FAIL {beat_id} frame {mid}: {proc.stderr.strip()[-800:]}", file=sys.stderr)
        else:
            print(f"OK   {beat_id} local frame {mid} -> {png}")
    print(f"{'FAIL' if failed else 'OK'}: {failed} of {len(beats)} stills failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
