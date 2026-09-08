#!/usr/bin/env python3
"""Produce the review artefacts for a rendered animation, plus a luminance-change diagnostic.

Everything here is evidence for eyes, not a verdict: the script makes looking cheap,
bounded and complete, and records what was looked at. Written into a FRESH run folder:
  contact.png           contact sheet, <= --max-samples frames, 6 per row, scaled before tiling
  phone-first.png       frame 0 at --phone-width (the LinkedIn thumbnail as a phone shows it)
  phone-mid.png         the middle frame at phone width
  phone-last.png        the last frame at phone width
  phone-beat-<id>.png   with --storyboard: every beat at its settled midpoint, phone width
  safe-first.png        frame 0 at full size with the safe-area rectangle drawn on it
  safe-mid.png          the middle frame with the safe rectangle
  safe-last.png         the last frame (the CTA) with the safe rectangle
  wrap.png              with --wrap: the last 5 frames then the first 5 (loop seam)
  report.json           probe facts, luminance jumps, per-check status

Statuses: pass (the script established it), fail (the script established a defect),
manual_required (needs eyes; record the decision with --record). The luminance
report lists frame-to-frame mean-luma changes >= 40; it is a diagnostic for cuts,
missing assets and unloaded fonts, not a WCAG flash test.

Usage:
    python3 qa_frames.py out/linkedin-4x5.mp4 --out out/qa-linkedin-4x5 --family feed --storyboard storyboard.json
    python3 qa_frames.py out/gif-loop.gif --out out/qa-gif-loop --family feed --wrap
    python3 qa_frames.py --record out/qa-linkedin-4x5/report.json "poster frame reads alone=pass" "text inside safe box=fail: cta beat, 9:16"
    python3 qa_frames.py --self-test

Exit codes: 0 = no failed check (manual items may remain), 1 = a check failed or an artefact
could not be produced, 2 = cannot probe or bad arguments. Stdlib only; needs ffmpeg/ffprobe.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

# Safe insets as fractions (top, right, bottom, left); mirrors vector-scene-layout/frame_tokens.py.
SAFE = {
    "feed": (0.05, 0.05, 0.12, 0.05),
    "vertical": (0.15, 0.06, 0.35, 0.06),
    "slide": (0.05, 0.05, 0.05, 0.05),
}
JUMP_THRESHOLD = 40.0  # mean luma delta (0-255) between consecutive frames worth a look
TILE_COLUMNS = 6
MAX_SAMPLES_CAP = 120
MAX_PHONE_WIDTH = 800
MANUAL_ITEMS = (
    "poster frame reads alone",
    "text inside safe box",
    "readable at phone width",
    "nothing essential in the bottom band",
    "CTA still",
    "loop seam continuous (if loop)",
    "credits present (if required)",
    "luminance jumps are intended cuts",
)


def run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def probe(path: Path) -> dict:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[-400:] or "ffprobe failed")
    info = json.loads(proc.stdout)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise RuntimeError("no video stream")
    fps = 0.0
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = video.get(key)
        if raw and raw not in ("0/0", "N/A"):
            fps = float(Fraction(raw))
            if fps > 0:
                break
    duration = float(info.get("format", {}).get("duration") or video.get("duration") or 0)
    counted = video.get("nb_read_frames")
    frames = int(counted) if counted and counted.isdigit() else 0
    if frames <= 0:
        raise RuntimeError("could not count decoded frames")
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": fps,
        "duration": duration,
        "frames": frames,
    }


def sample_rate(duration: float, max_samples: int) -> float:
    """Frames per second to sample so the sheet holds at most max_samples frames."""
    if duration <= 0:
        return 1.0
    return min(1.0, max_samples / duration)


def contact_filter(duration: float, max_samples: int, tile_width: int = 320) -> str:
    rate = sample_rate(duration, max_samples)
    n = max(1, min(max_samples, math.ceil(duration * rate)))
    rows = math.ceil(n / TILE_COLUMNS)
    return f"fps={rate:.6f},scale={tile_width}:-2,tile={TILE_COLUMNS}x{rows}:padding=4:margin=4:color=0x202020"


def safe_box(width: int, height: int, family: str) -> tuple[int, int, int, int]:
    top, right, bottom, left = SAFE[family]
    x, y = round(width * left), round(height * top)
    return x, y, width - x - round(width * right), height - y - round(height * bottom)


def beat_midpoints(storyboard: dict) -> list[tuple[str, int]]:
    """(beat id, absolute midpoint frame); same rounding as the storyboard validator."""
    fps = int(storyboard["fps"])
    to_frames = lambda s: math.floor(s * fps + 0.5)  # noqa: E731
    start, out = 0, []
    for b in storyboard["beats"]:
        dur = to_frames(float(b["duration_s"]))
        overlap = to_frames(float((b.get("transition") or {}).get("overlap_s", 0) or 0))
        out.append((str(b["id"]), start + dur // 2))
        start += dur - overlap
    return out


def luma_series(path: Path) -> list[float]:
    """Mean luma (YAVG) per frame; the file path is an -i argument, never part of a filtergraph."""
    proc = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostats",
            "-i",
            str(path),
            "-vf",
            "signalstats,metadata=print:file=-",
            "-f",
            "null",
            "-",
        ],
        1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[-400:] or "signalstats failed")
    return [
        float(m.group(1)) for m in re.finditer(r"lavfi\.signalstats\.YAVG=([0-9.]+)", proc.stdout)
    ]


def jumps(series: list[float], threshold: float = JUMP_THRESHOLD) -> list[dict]:
    return [
        {"frame": i, "delta": round(series[i] - series[i - 1], 1)}
        for i in range(1, len(series))
        if abs(series[i] - series[i - 1]) >= threshold
    ]


def png_ok(path: Path) -> bool:
    return (
        path.is_file()
        and path.stat().st_size > 100
        and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    )


def record(report_path: Path, decisions: list[str]) -> int:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    checks = report.get("checks", {})
    for d in decisions:
        if "=" not in d:
            print(f"ERROR decision must be 'item=pass|fail[: note]': {d!r}", file=sys.stderr)
            return 2
        item, verdict = d.split("=", 1)
        status, _, note = verdict.partition(":")
        item, status = item.strip(), status.strip()
        if item not in checks or status not in ("pass", "fail"):
            print(f"ERROR unknown item {item!r} or status {status!r} (pass|fail)", file=sys.stderr)
            return 2
        checks[item].update({"status": status, "detail": note.strip() or "reviewed by eye"})
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    open_items = [k for k, v in checks.items() if v.get("status") == "manual_required"]
    failed = [k for k, v in checks.items() if v.get("status") == "fail"]
    print(
        f"recorded {len(decisions)} decision(s); {len(open_items)} still need eyes; {len(failed)} failed"
    )
    return 1 if failed else 0


def self_test() -> None:
    assert sample_rate(18.2, 60) == 1.0 and abs(sample_rate(900, 60) - 60 / 900) < 1e-9
    f = contact_filter(18.2, 60)
    assert "tile=6x4" in f and f.startswith("fps=1.000000"), f
    assert "tile=6x10" in contact_filter(900, 60)
    assert safe_box(1080, 1350, "feed") == (54, 68, 972, 1120)
    assert jumps([100.0] * 60) == []
    assert [j["frame"] for j in jumps([100.0] * 30 + [20.0] * 30)] == [30]
    assert len(jumps([16.0, 66.0, 116.0, 166.0])) == 3  # a ramp is listed, never judged
    sb = {
        "fps": 30,
        "beats": [
            {"id": "a", "duration_s": 3, "transition": {"overlap_s": 0.5}},
            {"id": "b", "duration_s": 4},
        ],
    }
    assert beat_midpoints(sb) == [("a", 45), ("b", 135)]
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        rp = Path(td) / "report.json"
        rp.write_text(
            json.dumps(
                {"checks": {"CTA still": {"status": "manual_required"}, "x": {"status": "pass"}}}
            )
        )
        assert record(rp, ["CTA still=pass: frames 441-546 identical"]) == 0
        assert json.loads(rp.read_text())["checks"]["CTA still"]["status"] == "pass"
        assert record(rp, ["CTA still=fail: moves at 500"]) == 1
        assert record(rp, ["nope=pass"]) == 2
        assert not png_ok(rp)
    print("self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("video", nargs="?", type=Path)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("out/qa"),
        help="fresh folder for this run (must not exist or be empty)",
    )
    ap.add_argument(
        "--family", choices=sorted(SAFE), default="feed", help="safe-area family of the target"
    )
    ap.add_argument(
        "--storyboard", type=Path, help="storyboard.json: adds a settled phone-width still per beat"
    )
    ap.add_argument("--phone-width", type=int, default=390)
    ap.add_argument(
        "--max-samples",
        type=int,
        default=60,
        help=f"contact sheet frame cap (<= {MAX_SAMPLES_CAP})",
    )
    ap.add_argument(
        "--wrap",
        action="store_true",
        help="also render the loop seam strip (last 5 then first 5 frames)",
    )
    ap.add_argument(
        "--record",
        type=Path,
        metavar="REPORT",
        help="record eye decisions into REPORT: item=pass|fail[: note] ...",
    )
    ap.add_argument("decisions", nargs="*", help="with --record: 'item=pass' or 'item=fail: note'")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.record:
        if not args.record.is_file():
            print(f"ERROR {args.record} does not exist", file=sys.stderr)
            return 2
        return record(args.record, args.decisions)
    if args.video is None:
        ap.error("video path required")
    if not args.video.is_file():
        print(f"ERROR {args.video} does not exist", file=sys.stderr)
        return 2
    if (
        not 1 <= args.max_samples <= MAX_SAMPLES_CAP
        or not 100 <= args.phone_width <= MAX_PHONE_WIDTH
    ):
        ap.error(
            f"--max-samples must be 1..{MAX_SAMPLES_CAP} and --phone-width 100..{MAX_PHONE_WIDTH}"
        )
    if args.out.exists() and any(args.out.iterdir()):
        print(
            f"ERROR {args.out} is not empty; use a fresh folder so old images cannot pass as evidence",
            file=sys.stderr,
        )
        return 2
    try:
        meta = probe(args.video)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR cannot probe {args.video}: {exc}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    src = str(args.video)
    checks: dict[str, dict] = {}
    n = meta["frames"]
    mid, last = n // 2, n - 1
    x, y, w, h = safe_box(meta["width"], meta["height"], args.family)
    box = f"drawbox=x={x}:y={y}:w={w}:h={h}:color=red@0.7:t=4"
    phone = f"scale={args.phone_width}:-2"
    jobs: dict[str, list[str]] = {
        "contact.png": [
            "-vf",
            contact_filter(meta["duration"], args.max_samples),
            "-frames:v",
            "1",
        ],
        "phone-first.png": ["-vf", f"select='eq(n\\,0)',{phone}", "-frames:v", "1"],
        "phone-mid.png": ["-vf", f"select='eq(n\\,{mid})',{phone}", "-frames:v", "1"],
        "phone-last.png": ["-vf", f"select='eq(n\\,{last})',{phone}", "-frames:v", "1"],
        "safe-first.png": ["-vf", f"select='eq(n\\,0)',{box}", "-frames:v", "1"],
        "safe-mid.png": ["-vf", f"select='eq(n\\,{mid})',{box}", "-frames:v", "1"],
        "safe-last.png": ["-vf", f"select='eq(n\\,{last})',{box}", "-frames:v", "1"],
    }
    beats: list[tuple[str, int]] = []
    if args.storyboard:
        try:
            beats = beat_midpoints(json.loads(args.storyboard.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checks["storyboard"] = {"status": "fail", "detail": f"cannot read beats: {exc}"}
        for bid, frame in beats:
            if 0 <= frame < n and re.fullmatch(r"[a-z][a-z0-9-]{0,31}", bid):
                jobs[f"phone-beat-{bid}.png"] = [
                    "-vf",
                    f"select='eq(n\\,{frame})',{phone}",
                    "-frames:v",
                    "1",
                ]
            else:
                checks[f"phone-beat-{bid}.png"] = {
                    "status": "fail",
                    "detail": f"beat frame {frame} outside 0..{n - 1} or unsafe id",
                }
    for name, filt in jobs.items():
        target = args.out / name
        try:
            proc = run(
                ["ffmpeg", "-v", "error", "-y", "-i", src, *filt, "-vsync", "vfr", str(target)]
            )
            ok = proc.returncode == 0 and png_ok(target)
            detail = "" if ok else (proc.stderr.strip()[-300:] or "no frame selected")
        except (OSError, subprocess.TimeoutExpired) as exc:
            ok, detail = False, str(exc)
        checks[name] = {"status": "pass" if ok else "fail", "detail": detail}
    if args.wrap:
        k = min(5, max(1, n // 2))
        lavfi = (
            f"[0:v]select='gte(n\\,{n - k})',setpts=N/FRAME_RATE/TB,scale=192:-2[a];"
            f"[1:v]select='lt(n\\,{k})',setpts=N/FRAME_RATE/TB,scale=192:-2[b];"
            f"[a][b]concat=n=2:v=1:a=0,tile={2 * k}x1:padding=4:margin=4:color=0x202020"
        )
        target = args.out / "wrap.png"
        proc = run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                src,
                "-i",
                src,
                "-lavfi",
                lavfi,
                "-frames:v",
                "1",
                str(target),
            ]
        )
        ok = proc.returncode == 0 and png_ok(target)
        checks["wrap.png"] = {
            "status": "pass" if ok else "fail",
            "detail": "" if ok else proc.stderr.strip()[-300:],
            "frames": f"{n - k}..{n - 1} then 0..{k - 1}",
        }
    try:
        series = luma_series(args.video)
        found = jumps(series)
        checks["luminance"] = {
            "status": "pass",  # the listing is the deliverable; judging it is the manual item below
            "frames_analysed": len(series),
            "jumps": found[:50],
            "jumps_total": len(found),
            "detail": "no frame-to-frame mean-luma change >= 40"
            if not found
            else "each jump must be an intended cut; a jump inside a beat is a defect (unloaded font, missing asset)",
        }
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        checks["luminance"] = {
            "status": "manual_required",
            "detail": f"signalstats unavailable: {exc}",
        }
    for item in MANUAL_ITEMS:
        checks.setdefault(
            item,
            {
                "status": "manual_required",
                "detail": "look at the images, then --record the decision",
            },
        )
    report = {
        "video": src,
        "probe": meta,
        "safe_box": {"x": x, "y": y, "w": w, "h": h, "family": args.family},
        "beats": dict(beats),
        "checks": checks,
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    failed = [k for k, v in checks.items() if v["status"] == "fail"]
    manual = [k for k, v in checks.items() if v["status"] == "manual_required"]
    for k, v in checks.items():
        print(f"{v['status']:<16} {k}: {str(v.get('detail', ''))[:100]}")
    print(
        f"{'FAIL' if failed else 'OK'}: {len(failed)} failed, {len(manual)} need eyes; artefacts in {args.out}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
