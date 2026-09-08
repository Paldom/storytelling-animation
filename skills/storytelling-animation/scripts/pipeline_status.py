#!/usr/bin/env python3
"""Report which pipeline gates a project has passed, from the artefacts on disk.

The orchestrator runs six skills in order; each leaves evidence. This script reads
that evidence, re-runs the sibling validators it can find, checks freshness (an
artefact older than the storyboard or the scenes it depends on reopens its gate),
and prints the first gate that is not satisfied. A gate whose validator is not
installed stays OPEN: presence of a file is never proof.

Gates (in order):
  1 storyboard   storyboard.json validates (animation-storyboard/scripts/validate_storyboard.py)
  2 assets       assets/manifest.json passes (vector-asset-sourcing/scripts/check_assets.py)
  3 layout       animation.config.json (license basis, targets == storyboard targets), src/tokens.ts,
                 timeline.ts, Video.tsx, Root.tsx, one scene per beat, one still per beat and target,
                 stills newer than the storyboard and the scenes
  4 motion       src/motion.ts present, lint clean (smooth-motion-choreography/scripts/lint_motion.py)
  5 export       out/<target>.<ext> for every storyboard target, newer than the scenes, and passing
                 animation-export-presets/scripts/check_output.py
  6 qa           out/qa-<target>/report.json for every deliverable, newer than it, every check pass
                 (manual items recorded with qa_frames.py --record)

Usage:
    python3 pipeline_status.py [--project .] [--skills-dir <dir with sibling skills>]
    python3 pipeline_status.py --self-test

Exit codes: 0 = all gates satisfied, 1 = a gate is open (printed), 2 = not a project.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

GATES = ("storyboard", "assets", "layout", "motion", "export", "qa")


def read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def sibling(skills_dir: Path | None, skill: str, script: str) -> Path | None:
    if skills_dir is None:
        return None
    p = skills_dir / skill / "scripts" / script
    return p if p.is_file() else None


def run_ok(cmd: list[str], cwd: Path) -> bool:
    try:
        return (
            subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=900, check=False
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


def newest(paths: list[Path]) -> float:
    return max((p.stat().st_mtime for p in paths if p.is_file()), default=0.0)


def deliverable_for(target: str, out: Path) -> Path:
    return out / (f"{target}.gif" if target == "gif-loop" else f"{target}.mp4")


def gates(project: Path, skills_dir: Path | None) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    sb_path = project / "storyboard.json"
    sb = read_json(sb_path)
    beats_raw = sb.get("beats") if sb else None
    targets_raw = sb.get("targets") if sb else None
    if (
        not sb
        or not isinstance(beats_raw, list)
        or not isinstance(targets_raw, list)
        or not targets_raw
    ):
        out.append(
            (
                "storyboard",
                False,
                "storyboard.json missing or not an object with beats[] and targets[]",
            )
        )
        return out
    beats = [
        str(b.get("id")) for b in beats_raw if isinstance(b, dict) and isinstance(b.get("id"), str)
    ]
    targets = [str(t) for t in targets_raw if isinstance(t, str)]
    validator = sibling(skills_dir, "animation-storyboard", "validate_storyboard.py")
    if validator is None:
        out.append(
            (
                "storyboard",
                False,
                "validator not found (install animation-storyboard, pass --skills-dir)",
            )
        )
    else:
        ok = run_ok([sys.executable, str(validator), str(sb_path)], project)
        out.append(("storyboard", ok, "validator exit 0" if ok else "validator reports errors"))

    manifest = project / "assets" / "manifest.json"
    checker = sibling(skills_dir, "vector-asset-sourcing", "check_assets.py")
    if not manifest.is_file():
        out.append(("assets", False, "assets/manifest.json missing"))
    elif checker is None:
        out.append(("assets", False, "checker not found (install vector-asset-sourcing)"))
    else:
        ok = run_ok([sys.executable, str(checker), str(manifest), "--root", str(project)], project)
        out.append(
            ("assets", ok, "manifest checks clean" if ok else "manifest checker reports errors")
        )

    cfg = read_json(project / "animation.config.json") or {}
    missing: list[str] = []
    basis = cfg.get("remotion_license_basis")
    if not isinstance(basis, str) or not basis.strip():
        missing.append("animation.config.json remotion_license_basis")
    cfg_targets = cfg.get("targets")
    if not isinstance(cfg_targets, list) or sorted(str(t) for t in cfg_targets) != sorted(targets):
        missing.append(f"animation.config.json targets must equal the storyboard's {targets}")
    sources = [
        project / rel
        for rel in ("src/tokens.ts", "src/timeline.ts", "src/Video.tsx", "src/Root.tsx")
    ]
    sources += [project / "src" / "scenes" / f"{b}.tsx" for b in beats]
    missing += [str(p.relative_to(project)) for p in sources if not p.is_file()]
    stills = [project / "out" / "stills" / f"{t}--{b}.png" for t in targets for b in beats]
    missing += [str(p.relative_to(project)) for p in stills if not p.is_file()]
    inputs_mtime = max(sb_path.stat().st_mtime, newest(sources))
    if (
        not missing
        and newest(stills) < inputs_mtime
        and any(p.stat().st_mtime < inputs_mtime for p in stills)
    ):
        missing.append("stills older than the storyboard or scenes (re-render)")
    out.append(
        (
            "layout",
            not missing,
            "files and stills present and current"
            if not missing
            else "missing: " + ", ".join(missing[:5]) + (" …" if len(missing) > 5 else ""),
        )
    )

    linter = sibling(skills_dir, "smooth-motion-choreography", "lint_motion.py")
    if not (project / "src" / "motion.ts").is_file():
        out.append(("motion", False, "src/motion.ts missing (motion step not started)"))
    elif linter is None:
        out.append(("motion", False, "linter not found (install smooth-motion-choreography)"))
    else:
        ok = run_ok([sys.executable, str(linter), str(project / "src")], project)
        out.append(("motion", ok, "lint clean" if ok else "motion lint reports errors"))

    out_dir = project / "out"
    checker = sibling(skills_dir, "animation-export-presets", "check_output.py")
    problems: list[str] = []
    deliverables: list[tuple[str, Path]] = []
    for t in targets:
        f = deliverable_for(t, out_dir)
        if not f.is_file():
            problems.append(f"{f.name} missing")
            continue
        if f.stat().st_mtime < inputs_mtime:
            problems.append(f"{f.name} older than the storyboard or scenes")
            continue
        if checker is None:
            problems.append("output checker not found (install animation-export-presets)")
            continue
        if not run_ok(
            [
                sys.executable,
                str(checker),
                str(f),
                "--preset",
                t,
                "--project",
                str(project),
                "--no-decode",
            ],
            project,
        ):
            problems.append(f"{f.name} fails its preset check")
            continue
        deliverables.append((t, f))
    out.append(
        (
            "export",
            not problems,
            "every target rendered, current and checked"
            if not problems
            else "; ".join(problems[:4]),
        )
    )

    qa_problems: list[str] = []
    for t, f in deliverables:
        report = read_json(out_dir / f"qa-{t}" / "report.json")
        if report is None:
            qa_problems.append(f"no report for {f.name}")
            continue
        if (out_dir / f"qa-{t}" / "report.json").stat().st_mtime < f.stat().st_mtime:
            qa_problems.append(f"report for {f.name} predates the file")
            continue
        checks = report.get("checks")
        if not isinstance(checks, dict) or not checks:
            qa_problems.append(f"empty report for {f.name}")
            continue
        statuses = {
            k: (v.get("status") if isinstance(v, dict) else None) for k, v in checks.items()
        }
        failed = [k for k, s in statuses.items() if s == "fail"]
        open_items = [k for k, s in statuses.items() if s != "pass"]
        if failed:
            qa_problems.append(f"{f.name}: failed {', '.join(failed[:3])}")
        elif open_items:
            qa_problems.append(f"{f.name}: {len(open_items)} item(s) not yet recorded pass")
    if not deliverables:
        qa_problems.append("nothing to review yet")
    out.append(
        (
            "qa",
            not qa_problems,
            "every deliverable reviewed and recorded"
            if not qa_problems
            else "; ".join(qa_problems[:4]),
        )
    )
    return out


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        skills = p / "skills"
        for name, script in (
            ("animation-storyboard", "validate_storyboard.py"),
            ("vector-asset-sourcing", "check_assets.py"),
            ("smooth-motion-choreography", "lint_motion.py"),
            ("animation-export-presets", "check_output.py"),
        ):
            d = skills / name / "scripts"
            d.mkdir(parents=True)
            (d / script).write_text("import sys; sys.exit(0)\n")
        proj = p / "proj"
        proj.mkdir()
        rows = gates(proj, skills)
        assert rows[0][0] == "storyboard" and not rows[0][1]
        (proj / "storyboard.json").write_text(
            json.dumps({"targets": ["linkedin-4x5"], "beats": [{"id": "hook"}, {"id": "cta"}]})
        )
        rows = gates(proj, None)
        assert [r[0] for r in rows] == list(GATES) and not rows[0][1] and "not found" in rows[0][2]
        rows = gates(proj, skills)
        assert rows[0][1] and not rows[1][1] and not rows[2][1]
        (proj / "assets").mkdir()
        (proj / "assets" / "manifest.json").write_text("{}")
        (proj / "animation.config.json").write_text(
            json.dumps(
                {"remotion_license_basis": "individual", "targets": ["linkedin-4x5", "pptx-16x9"]}
            )
        )
        rows = gates(proj, skills)
        assert not rows[2][1] and "targets must equal" in rows[2][2]
        (proj / "animation.config.json").write_text(
            json.dumps({"remotion_license_basis": "individual", "targets": ["linkedin-4x5"]})
        )
        for rel in (
            "src/tokens.ts",
            "src/timeline.ts",
            "src/Video.tsx",
            "src/Root.tsx",
            "src/motion.ts",
            "src/scenes/hook.tsx",
            "src/scenes/cta.tsx",
        ):
            (proj / rel).parent.mkdir(parents=True, exist_ok=True)
            (proj / rel).write_text("x")
        import time

        time.sleep(0.02)
        for rel in (
            "out/stills/linkedin-4x5--hook.png",
            "out/stills/linkedin-4x5--cta.png",
            "out/linkedin-4x5.mp4",
        ):
            (proj / rel).parent.mkdir(parents=True, exist_ok=True)
            (proj / rel).write_text("x")
        rows = gates(proj, skills)
        assert all(ok for _, ok, _ in rows[:5]), rows
        assert not rows[5][1] and "no report" in rows[5][2], rows[5]
        qa = proj / "out" / "qa-linkedin-4x5"
        qa.mkdir()
        time.sleep(0.02)
        (qa / "report.json").write_text(
            json.dumps({"checks": {"a": {"status": "pass"}, "b": {"status": "manual_required"}}})
        )
        rows = gates(proj, skills)
        assert not rows[5][1] and "not yet recorded" in rows[5][2], rows[5]
        (qa / "report.json").write_text(
            json.dumps({"checks": {"a": {"status": "pass"}, "b": {"status": "pass"}}})
        )
        assert gates(proj, skills)[5][1]
        (qa / "report.json").write_text("[]")
        assert not gates(proj, skills)[5][1]
        time.sleep(0.02)
        (proj / "storyboard.json").write_text(
            json.dumps({"targets": ["linkedin-4x5"], "beats": [{"id": "hook"}, {"id": "cta"}]})
        )
        rows = gates(proj, skills)
        assert not rows[2][1] and "older" in rows[2][2], rows[2]
        (proj / "animation.config.json").write_text("null")
        assert not gates(proj, skills)[2][1]
    print("self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument(
        "--skills-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent,
        help="folder containing the sibling skills (default: this skill's parent)",
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.project.is_dir():
        print(f"ERROR {args.project} is not a directory", file=sys.stderr)
        return 2
    skills_dir = args.skills_dir if args.skills_dir.is_dir() else None
    if skills_dir is None:
        print(
            f"WARN  skills dir {args.skills_dir} not found; validator-backed gates stay OPEN",
            file=sys.stderr,
        )
    rows = gates(args.project.resolve(), skills_dir)
    first_open = None
    for name, ok, detail in rows:
        print(f"{'PASS' if ok else 'OPEN'}  {name:<11} {detail}")
        if not ok and first_open is None:
            first_open = name
    if first_open:
        print(f"NEXT: {first_open}")
        return 1
    print("ALL GATES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
