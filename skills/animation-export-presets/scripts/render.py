#!/usr/bin/env python3
"""Render a Remotion animation to delivery presets: one master per composition, one
ffmpeg pass per deliverable, checked before it is published.

Runs inside --project (cwd for npx, paths relative to it). Refuses to render without
`remotion_license_basis` in animation.config.json. Master: `npx remotion render` at
CRF 10, yuv420p, BT.709, recorded with a sidecar so `--reuse-masters` only reuses a
master made from the same storyboard and flags. Deliverable: libx264 re-encode with
the preset's CRF/GOP/tune, VUI colour tags and faststart, or a two-pass palette GIF;
written to a unique temp name, checked with check_output.py, and only then moved to
out/<preset>.<ext>. A failed encode or check leaves the previous file untouched.

Usage:
    python3 render.py --preset linkedin-4x5 --preset pptx-16x9 [--project .] [--out out]
    python3 render.py --preset pptx-16x9 --input existing.mp4      # re-encode an existing file, no Remotion
    python3 render.py --preset gif-loop --reuse-masters             # reuse a matching master
    python3 render.py --preset linkedin-4x5 --dry-run               # print the commands
    python3 render.py --self-test

Exit codes: 0 = every requested deliverable published, 1 = a step or check failed or the
license basis is missing, 2 = bad arguments. Stdlib only; needs node/npx, ffmpeg, ffprobe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from check_output import check_file

PRESETS_FILE = Path(__file__).resolve().parent.parent / "assets" / "presets.json"
VUI_BT709 = "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0"


def load_presets(path: Path = PRESETS_FILE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or "presets" not in data:
        raise ValueError(f"{path}: not a presets file (version 1)")
    return data


def license_basis(project: Path) -> str | None:
    cfg = project / "animation.config.json"
    if not cfg.is_file():
        return None
    try:
        basis = json.loads(cfg.read_text(encoding="utf-8")).get("remotion_license_basis")
    except ValueError:
        return None
    return basis if isinstance(basis, str) and basis.strip() else None


def master_path(out: Path, composition: str, scale: int) -> Path:
    suffix = f"-x{scale}" if scale != 1 else ""
    return out / "masters" / f"{composition}{suffix}.mp4"


def fingerprint(project: Path, composition: str, flags: list[str], scale: int) -> str:
    """What a master depends on: the storyboard bytes, the composition and the flags."""
    h = hashlib.sha256()
    sb = project / "storyboard.json"
    h.update(sb.read_bytes() if sb.is_file() else b"")
    h.update(f"{composition}|{scale}|{' '.join(flags)}".encode())
    return h.hexdigest()


def remotion_command(
    entry: str, composition: str, master: Path, flags: list[str], scale: int
) -> list[str]:
    cmd = ["npx", "remotion", "render", entry, composition, str(master), *flags, "--log=error"]
    if scale != 1:
        cmd.append(f"--scale={scale}")
    return cmd


def mp4_command(source: Path, preset: dict, tmp: Path, cbr_kbps: int | None = None) -> list[str]:
    """CRF encode by default; with cbr_kbps, a constant-bitrate encode (nal-hrd=cbr pads
    sparse content) for platforms with a bitrate floor that near-static vector clips miss."""
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-preset",
        "slow",
    ]
    if preset.get("x264_tune"):
        cmd += ["-tune", preset["x264_tune"]]
    if cbr_kbps:
        rate = f"{cbr_kbps}k"
        cmd += [
            "-b:v",
            rate,
            "-minrate",
            rate,
            "-maxrate",
            rate,
            "-bufsize",
            f"{cbr_kbps * 2}k",
            "-x264-params",
            "nal-hrd=cbr",
        ]
    else:
        cmd += ["-crf", str(preset["crf"])]
    cmd += [
        "-g",
        str(preset["gop"]),
        "-pix_fmt",
        preset["pix_fmt"],
        "-color_range",
        preset.get("range", "tv"),
    ]
    cmd += ["-bsf:v", VUI_BT709]
    if preset.get("faststart"):
        cmd += ["-movflags", "+faststart"]
    cmd += ["-an", "-f", "mp4", str(tmp)]
    return cmd


def gif_commands(
    source: Path, preset: dict, palette: Path, tmp: Path
) -> tuple[list[str], list[str]]:
    p = preset["palette"]
    chain = f"fps={preset['fps']},scale='min({preset['max_width']},iw)':-2:flags=lanczos"
    gen = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-vf",
        f"{chain},palettegen=stats_mode={p['stats_mode']}:max_colors={p['max_colors']}",
        str(palette),
    ]
    use = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-i",
        str(palette),
        "-lavfi",
        f"{chain}[x];[x][1:v]paletteuse=dither={p['dither']}:bayer_scale={p['bayer_scale']}:diff_mode=rectangle",
        "-loop",
        str(preset.get("loop", 0)),
        "-f",
        "gif",
        str(tmp),
    ]
    return gen, use


def run(cmd: list[str], cwd: Path, dry_run: bool, timeout: int = 3600) -> bool:
    if dry_run:
        print("  $ " + " ".join(cmd))
        return True
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        print(f"ERROR timed out after {timeout}s: {cmd[0]}", file=sys.stderr)
        return False
    if proc.returncode != 0:
        print(
            f"ERROR {cmd[0]} exited {proc.returncode}:\n{proc.stderr.strip()[-1500:]}",
            file=sys.stderr,
        )
        return False
    return True


def unique_tmp(final: Path) -> Path:
    fd, name = tempfile.mkstemp(prefix=final.stem + ".part-", suffix=final.suffix, dir=final.parent)
    os.close(fd)
    return Path(name)


def ensure_master(name: str, preset: dict, data: dict, args: argparse.Namespace) -> Path | None:
    composition = preset["composition"]
    scale = int(preset.get("scale", 1))
    master = master_path(args.out, composition, scale)
    sidecar = master.with_suffix(".json")
    fp = fingerprint(args.project, composition, data["master"]["remotion_flags"], scale)
    if args.reuse_masters and master.is_file() and sidecar.is_file():
        try:
            if json.loads(sidecar.read_text(encoding="utf-8")).get("fingerprint") == fp:
                print(f"[{name}] reusing master {master}")
                return master
        except ValueError:
            pass
        print(f"[{name}] master {master} does not match this storyboard/flags; rendering again")
    master.parent.mkdir(parents=True, exist_ok=True)
    tmp = unique_tmp(master)
    print(f"[{name}] rendering master {master}")
    if not run(
        remotion_command(args.entry, composition, tmp, data["master"]["remotion_flags"], scale),
        args.project,
        args.dry_run,
    ):
        tmp.unlink(missing_ok=True)
        return None
    if args.dry_run:
        tmp.unlink(missing_ok=True)
        return master
    tmp.replace(master)
    sidecar.write_text(
        json.dumps({"fingerprint": fp, "composition": composition, "scale": scale}),
        encoding="utf-8",
    )
    return master


def render_preset(
    name: str, preset: dict, data: dict, args: argparse.Namespace, storyboard: dict | None
) -> bool:
    source = args.input if args.input else ensure_master(name, preset, data, args)
    if source is None:
        return False
    ext = "gif" if preset["container"] == "gif" else "mp4"
    final = args.out / f"{name}.{ext}"
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = unique_tmp(final)
    try:
        if ext == "gif":
            with tempfile.TemporaryDirectory() as td:
                palette = Path(td) / "palette.png"
                gen, use = gif_commands(source, preset, palette, tmp)
                ok = run(gen, args.project, args.dry_run) and run(use, args.project, args.dry_run)
        else:
            ok = run(mp4_command(source, preset, tmp), args.project, args.dry_run)
        if not ok:
            return False
        if args.dry_run:
            return True
        rows = check_file(tmp, name, preset, storyboard, decode=not args.no_decode)
        failed = [(n, d) for n, ok_, d in rows if not ok_]
        floor = (preset.get("bitrate_range_kbps") or [0])[0]
        if ext == "mp4" and floor and [n for n, _ in failed] == ["bitrate"]:
            # Sparse vector content under the platform's bitrate floor: re-encode at a
            # constant bitrate (twice the floor) so the file is accepted.
            target = max(2 * floor, 400)
            print(
                f"[{name}] bitrate under the {floor} kbps floor; re-encoding at a constant {target} kbps"
            )
            if not run(mp4_command(source, preset, tmp, cbr_kbps=target), args.project, False):
                return False
            rows = check_file(tmp, name, preset, storyboard, decode=not args.no_decode)
            failed = [(n, d) for n, ok_, d in rows if not ok_]
        if failed:
            for n, d in failed:
                print(f"[{name}] check failed: {n}: {d}", file=sys.stderr)
            print(f"[{name}] not published; previous {final} left untouched", file=sys.stderr)
            return False
        tmp.replace(final)
        print(f"[{name}] wrote {final} ({final.stat().st_size} bytes), {len(rows)} checks passed")
        return True
    finally:
        tmp.unlink(missing_ok=True)


def self_test() -> None:
    data = load_presets()
    for name, preset in data["presets"].items():
        assert preset["container"] in ("mp4", "gif"), name
        assert "sources" in preset and "why" in preset, name
    lp = data["presets"]["linkedin-4x5"]
    cmd = mp4_command(Path("m.mp4"), lp, Path("t.mp4"))
    assert "-tune" not in cmd and "+faststart" in cmd and cmd[cmd.index("-crf") + 1] == "18"
    cbr = mp4_command(Path("m.mp4"), lp, Path("t.mp4"), cbr_kbps=400)
    assert "-crf" not in cbr and cbr[cbr.index("-minrate") + 1] == "400k" and "nal-hrd=cbr" in cbr
    pp = data["presets"]["pptx-16x9"]
    cmd = mp4_command(Path("m.mp4"), pp, Path("t.mp4"))
    assert (
        cmd[cmd.index("-tune") + 1] == "animation"
        and cmd[cmd.index("-g") + 1] == "30"
        and VUI_BT709 in cmd
    )
    gen, use = gif_commands(
        Path("m.mp4"), data["presets"]["gif-loop"], Path("p.png"), Path("t.gif")
    )
    assert "palettegen=stats_mode=diff" in " ".join(
        gen
    ) and "paletteuse=dither=bayer:bayer_scale=5" in " ".join(use)
    rc = remotion_command(
        "src/index.ts", "pptx-16x9", Path("m.mp4"), data["master"]["remotion_flags"], 2
    )
    assert "--scale=2" in rc and "--crf=10" in rc and "--color-space=bt709" in rc
    assert master_path(Path("out"), "pptx-16x9", 2).name == "pptx-16x9-x2.mp4"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        assert license_basis(p) is None
        (p / "animation.config.json").write_text('{"remotion_license_basis": ""}')
        assert license_basis(p) is None
        (p / "animation.config.json").write_text('{"remotion_license_basis": "individual"}')
        assert license_basis(p) == "individual"
        (p / "storyboard.json").write_text("{}")
        a = fingerprint(p, "c", ["--x"], 1)
        (p / "storyboard.json").write_text("{ }")
        assert fingerprint(p, "c", ["--x"], 1) != a and fingerprint(p, "c", ["--x"], 2) != a
        t = unique_tmp(p / "final.mp4")
        assert t.parent == p and t.name.startswith("final.part-") and t.suffix == ".mp4"
        t.unlink()
    print("self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--preset",
        action="append",
        default=[],
        help="preset id from assets/presets.json; repeatable",
    )
    ap.add_argument(
        "--project", type=Path, default=Path("."), help="Remotion project root (cwd for the render)"
    )
    ap.add_argument("--entry", default="src/index.ts", help="entry point, relative to --project")
    ap.add_argument(
        "--out", type=Path, default=Path("out"), help="output folder, relative to --project"
    )
    ap.add_argument(
        "--input", type=Path, help="re-encode this existing file instead of rendering a master"
    )
    ap.add_argument(
        "--reuse-masters",
        action="store_true",
        help="reuse a master whose sidecar matches the storyboard and flags",
    )
    ap.add_argument(
        "--no-decode",
        action="store_true",
        help="skip the full decode pass in the pre-publish check",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.preset:
        ap.error("at least one --preset is required")
    try:
        data = load_presets()
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    unknown = [p for p in args.preset if p not in data["presets"]]
    if unknown:
        ap.error(f"unknown preset(s) {unknown}; known: {', '.join(data['presets'])}")
    args.project = args.project.resolve()
    if not args.out.is_absolute():
        args.out = args.project / args.out
    if args.input is not None:
        args.input = args.input.resolve()
        if not args.input.is_file():
            ap.error(f"--input {args.input} does not exist")
    else:
        basis = license_basis(args.project)
        if basis is None:
            print(
                "ERROR animation.config.json has no remotion_license_basis. Remotion is free for individuals, "
                "companies with up to 3 people, and non-profits; other organisations need a Company License "
                "(https://www.remotion.pro/license). Record the basis, then render.",
                file=sys.stderr,
            )
            return 1
        print(f"license basis: {basis}")
    storyboard = None
    sb_path = args.project / "storyboard.json"
    if sb_path.is_file():
        try:
            storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
        except ValueError:
            storyboard = None
    args.out.mkdir(parents=True, exist_ok=True)
    failed = [
        name
        for name in args.preset
        if not render_preset(name, data["presets"][name], data, args, storyboard)
    ]
    print(
        f"{'FAIL' if failed else 'OK'}: {len(args.preset) - len(failed)} of {len(args.preset)} preset(s) published"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
