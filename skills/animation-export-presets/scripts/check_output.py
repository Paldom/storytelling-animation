#!/usr/bin/env python3
"""Check a rendered file against a delivery preset: ffprobe facts, container, atom order,
GIF loop flag, platform floors and a full decode pass.

Expected size and fps come from the preset and the project's storyboard.json (fps;
custom_size for the custom preset), never from guesses. MP4 presets: codec, High
profile, yuv420p, even dimensions, exact fps, BT.709 tags, faststart (moov before
mdat), no audio, duration bounds, byte floor/cap, bitrate range, decode. GIF: codec,
width cap, 15 fps (centisecond timing tolerated), infinite-loop extension, size, decode.

Usage:
    python3 check_output.py out/linkedin-4x5.mp4 --preset linkedin-4x5 [--project .]
    python3 check_output.py out/custom.mp4 --preset custom --project .
    python3 check_output.py --self-test

Exit codes: 0 = all checks pass, 1 = a check failed, 2 = cannot probe or resolve expectations.
Stdlib only; needs ffprobe/ffmpeg.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

PRESETS_FILE = Path(__file__).resolve().parent.parent / "assets" / "presets.json"


def probe(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[-500:] or "ffprobe failed")
    return json.loads(proc.stdout)


def decodes(path: Path) -> bool:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    return proc.returncode == 0


def top_level_atoms(path: Path) -> list[str]:
    """Names of the top-level MP4 boxes in file order."""
    names: list[str] = []
    size_total = path.stat().st_size
    with path.open("rb") as fh:
        offset = 0
        while offset + 8 <= size_total:
            fh.seek(offset)
            size, name = struct.unpack(">I4s", fh.read(8))
            if size == 1:
                size = struct.unpack(">Q", fh.read(8))[0]
            elif size == 0:
                size = size_total - offset
            names.append(name.decode("latin1"))
            if size < 8:
                break
            offset += size
    return names


def gif_loop_count(path: Path) -> int | None:
    """Loop count from the NETSCAPE2.0 application extension; 0 = infinite; None = absent."""
    data = path.read_bytes()
    i = data.find(b"NETSCAPE2.0")
    if i == -1:
        return None
    j = data.find(b"\x03\x01", i)
    if j == -1 or j + 4 > len(data):
        return None
    return struct.unpack("<H", data[j + 2 : j + 4])[0]


def fps_of(stream: dict, is_gif: bool = False) -> Fraction:
    """avg_frame_rate for video; r_frame_rate for GIF, whose centisecond delays make
    the average drift (1/15 s is 6.67 cs, stored as 6 or 7)."""
    keys = ("r_frame_rate", "avg_frame_rate") if is_gif else ("avg_frame_rate", "r_frame_rate")
    for key in keys:
        raw = stream.get(key)
        if raw and raw != "0/0":
            return Fraction(raw)
    return Fraction(0)


def expectations(
    preset_name: str, preset: dict, storyboard: dict | None
) -> tuple[int | None, int | None, int | None]:
    """(width, height, fps) the file must have; None when the preset does not fix it."""
    if preset["container"] == "gif":
        return None, None, int(preset["fps"])
    if storyboard is None or not isinstance(storyboard.get("fps"), int):
        raise ValueError("storyboard.json with an integer fps is required to check an MP4 preset")
    fps = int(storyboard["fps"])
    if preset_name == "custom":
        cs = storyboard.get("custom_size") or {}
        if not (isinstance(cs.get("width"), int) and isinstance(cs.get("height"), int)):
            raise ValueError("custom preset needs custom_size {width, height} in storyboard.json")
        return int(cs["width"]), int(cs["height"]), fps
    return int(preset["width"]), int(preset["height"]), fps


def evaluate(
    info: dict,
    preset: dict,
    *,
    atoms: list[str] | None,
    decoded: bool | None,
    loops: int | None,
    width: int | None,
    height: int | None,
    fps: int | None,
) -> list[tuple[str, bool, str]]:
    """Return (check, ok, detail) rows. Pure: takes the probe dict and file facts."""
    rows: list[tuple[str, bool, str]] = []
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        return [("video stream", False, "none found")]
    fmt = info.get("format", {})
    is_gif = preset["container"] == "gif"
    rows.append(
        (
            "codec",
            video.get("codec_name") == preset["video_codec"],
            f"{video.get('codec_name')} (want {preset['video_codec']})",
        )
    )
    w, h = int(video.get("width", 0)), int(video.get("height", 0))
    if is_gif:
        rows.append(
            ("container", "gif" in str(fmt.get("format_name", "")), str(fmt.get("format_name")))
        )
        rows.append(
            (
                "width cap",
                0 < w <= preset["max_width"] and h > 0,
                f"{w}x{h} (cap {preset['max_width']} wide)",
            )
        )
        rows.append(
            (
                "infinite loop",
                loops == 0,
                "NETSCAPE loop=0" if loops == 0 else f"loop extension {loops!r}",
            )
        )
    else:
        rows.append(
            (
                "container",
                "mp4" in str(fmt.get("format_name", "")).split(","),
                str(fmt.get("format_name")),
            )
        )
        rows.append(
            (
                "profile",
                video.get("profile") == preset.get("profile"),
                f"{video.get('profile')} (want {preset.get('profile')})",
            )
        )
        rows.append(
            (
                "pix_fmt",
                video.get("pix_fmt") == preset["pix_fmt"],
                f"{video.get('pix_fmt')} (want {preset['pix_fmt']})",
            )
        )
        for key in ("color_space", "color_primaries", "color_transfer"):
            rows.append((key, video.get(key) == preset.get("color", "bt709"), f"{video.get(key)}"))
        rows.append(
            (
                "color_range",
                video.get("color_range") == preset.get("range", "tv"),
                f"{video.get('color_range')}",
            )
        )
        rows.append(("even dimensions", w % 2 == 0 and h % 2 == 0, f"{w}x{h}"))
        if width and height:
            rows.append(
                ("dimensions", (w, h) == (width, height), f"{w}x{h} (want {width}x{height})")
            )
    got_fps = fps_of(video, is_gif)
    if fps:
        ok = abs(float(got_fps) - fps) < (2.0 if is_gif else 1e-6)
        rows.append(("fps", ok, f"{got_fps} (want {fps})"))
        lo_hi = preset.get("fps_range")
        if lo_hi:
            rows.append(
                (
                    "fps within platform range",
                    lo_hi[0] <= float(got_fps) <= lo_hi[1],
                    f"{lo_hi[0]}..{lo_hi[1]}",
                )
            )
    duration = float(fmt.get("duration") or video.get("duration") or 0)
    rows.append(
        (
            "duration",
            preset["min_s"] <= duration <= preset["max_s"],
            f"{duration:.2f}s (allowed {preset['min_s']}..{preset['max_s']}s)",
        )
    )
    if preset.get("recommended_max_s") and duration > preset["recommended_max_s"]:
        rows.append(
            (
                "duration (recommended)",
                True,
                f"{duration:.2f}s exceeds the recommended {preset['recommended_max_s']}s; allowed but flagged",
            )
        )
    size = int(fmt.get("size") or 0)
    rows.append(
        (
            "size",
            preset.get("min_bytes", 1) <= size <= preset["max_bytes"],
            f"{size} bytes (allowed {preset.get('min_bytes', 1)}..{preset['max_bytes']})",
        )
    )
    br = preset.get("bitrate_range_kbps")
    if br and duration > 0:
        kbps = size * 8 / duration / 1000
        rows.append(
            ("bitrate", br[0] <= kbps <= br[1], f"{kbps:.0f} kbps (allowed {br[0]}..{br[1]})")
        )
    if not is_gif and preset.get("faststart") and atoms is not None:
        ok = "moov" in atoms and "mdat" in atoms and atoms.index("moov") < atoms.index("mdat")
        rows.append(("faststart", ok, " ".join(atoms)))
    if preset.get("audio") == "none":
        has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
        rows.append(
            (
                "no audio track",
                not has_audio,
                "audio present" if has_audio else "silent as intended",
            )
        )
    if decoded is not None:
        rows.append(("decodes fully", decoded, "ffmpeg -xerror decode"))
    return rows


def check_file(
    path: Path, preset_name: str, preset: dict, storyboard: dict | None, *, decode: bool = True
) -> list[tuple[str, bool, str]]:
    """Probe the file and evaluate it; used by render.py before publishing a deliverable."""
    width, height, fps = expectations(preset_name, preset, storyboard)
    info = probe(path)
    is_gif = preset["container"] == "gif"
    return evaluate(
        info,
        preset,
        atoms=None if is_gif else top_level_atoms(path),
        decoded=decodes(path) if decode else None,
        loops=gif_loop_count(path) if is_gif else None,
        width=width,
        height=height,
        fps=fps,
    )


def self_test() -> None:
    presets = json.loads(PRESETS_FILE.read_text())["presets"]
    good = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "profile": "High",
                "pix_fmt": "yuv420p",
                "width": 1080,
                "height": 1350,
                "avg_frame_rate": "30/1",
                "color_space": "bt709",
                "color_primaries": "bt709",
                "color_transfer": "bt709",
                "color_range": "tv",
            }
        ],
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "18.2", "size": "1200000"},
    }
    w, h, fps = expectations("linkedin-4x5", presets["linkedin-4x5"], {"fps": 30})
    assert (w, h, fps) == (1080, 1350, 30)
    rows = evaluate(
        good,
        presets["linkedin-4x5"],
        atoms=["ftyp", "moov", "mdat"],
        decoded=True,
        loops=None,
        width=w,
        height=h,
        fps=fps,
    )
    assert all(ok for _, ok, _ in rows), [r for r in rows if not r[1]]
    bad = json.loads(json.dumps(good))
    bad["streams"][0].update(
        {"pix_fmt": "yuv444p", "width": 1081, "color_transfer": "unknown", "avg_frame_rate": "59/2"}
    )
    bad["format"].update({"duration": "2.0", "size": "20000", "format_name": "mov"})
    rows = evaluate(
        bad,
        presets["linkedin-4x5"],
        atoms=["ftyp", "mdat", "moov"],
        decoded=False,
        loops=None,
        width=w,
        height=h,
        fps=fps,
    )
    failed = {name for name, ok, _ in rows if not ok}
    assert {
        "container",
        "pix_fmt",
        "even dimensions",
        "dimensions",
        "color_transfer",
        "fps",
        "duration",
        "size",
        "faststart",
        "decodes fully",
    } <= failed, failed
    gif = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "gif",
                "width": 800,
                "height": 801,
                "r_frame_rate": "15/1",
                "avg_frame_rate": "50/3",
            }
        ],
        "format": {"format_name": "gif", "duration": "8.0", "size": "4000000"},
    }
    w, h, fps = expectations("gif-loop", presets["gif-loop"], None)
    rows = evaluate(
        gif, presets["gif-loop"], atoms=None, decoded=True, loops=0, width=w, height=h, fps=fps
    )
    assert all(ok for _, ok, _ in rows), [r for r in rows if not r[1]]  # odd height is fine for GIF
    rows = evaluate(
        gif, presets["gif-loop"], atoms=None, decoded=True, loops=None, width=w, height=h, fps=fps
    )
    assert any(name == "infinite loop" and not ok for name, ok, _ in rows)
    try:
        expectations("custom", presets["custom"], {"fps": 25})
    except ValueError:
        pass
    else:
        raise AssertionError("custom without custom_size must be rejected")
    assert expectations(
        "custom", presets["custom"], {"fps": 25, "custom_size": {"width": 1440, "height": 1440}}
    ) == (1440, 1440, 25)
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "a.mp4"
        f.write_bytes(
            struct.pack(">I4s", 8, b"ftyp")
            + struct.pack(">I4s", 8, b"moov")
            + struct.pack(">I4s", 8, b"mdat")
        )
        assert top_level_atoms(f) == ["ftyp", "moov", "mdat"]
        g = Path(td) / "a.gif"
        g.write_bytes(b"GIF89a" + b"\x00" * 10 + b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")
        assert gif_loop_count(g) == 0
        g.write_bytes(b"GIF89a" + b"\x00" * 10)
        assert gif_loop_count(g) is None
    print("self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("file", nargs="?", type=Path)
    ap.add_argument("--preset", help="preset id from assets/presets.json")
    ap.add_argument(
        "--project",
        type=Path,
        default=Path("."),
        help="project root holding storyboard.json (fps, custom_size)",
    )
    ap.add_argument(
        "--no-decode", action="store_true", help="skip the full decode pass (slow on long files)"
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.file is None or not args.preset:
        ap.error("file and --preset are required")
    presets = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))["presets"]
    if args.preset not in presets:
        ap.error(f"unknown preset {args.preset!r}; known: {', '.join(presets)}")
    if not args.file.is_file():
        print(f"ERROR {args.file} does not exist", file=sys.stderr)
        return 2
    storyboard = None
    sb_path = args.project / "storyboard.json"
    if sb_path.is_file():
        try:
            storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
        except ValueError:
            storyboard = None
    try:
        rows = check_file(
            args.file, args.preset, presets[args.preset], storyboard, decode=not args.no_decode
        )
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR {args.file}: {exc}", file=sys.stderr)
        return 2
    for name, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<26} {detail}")
    failed = sum(1 for _, ok, _ in rows if not ok)
    print(
        f"{'FAIL' if failed else 'OK'}: {failed} failing check(s) of {len(rows)} for preset {args.preset}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
