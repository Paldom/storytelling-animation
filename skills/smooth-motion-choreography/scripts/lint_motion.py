#!/usr/bin/env python3
"""Lint Remotion scene code for the patterns that flicker, strobe or reflow in a render.

Remotion renders frames in parallel across several browser tabs, so anything not
derived from useCurrentFrame() (wall-clock timers, CSS transitions, Math.random)
produces different pixels per frame. This is a diagnostic grep with line numbers,
not a proof of determinism: a clean result means none of the known bad patterns
are present.

Usage:
    python3 lint_motion.py src/                 # lint every .ts/.tsx under src/
    python3 lint_motion.py src/scenes/hook.tsx  # one file
    python3 lint_motion.py --self-test

Exit codes: 0 = no findings, 1 = findings (errors), 2 = nothing to lint. Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

# (id, regex, severity, message). Severity "error" fails the run; "warn" is advisory.
RULES: list[tuple[str, re.Pattern[str], str, str]] = [
    (
        "random",
        re.compile(r"\bMath\.random\s*\("),
        "error",
        "Math.random() differs per render thread; use random(seed) from remotion",
    ),
    (
        "clock",
        re.compile(r"\b(?:Date\.now|performance\.now)\s*\(|\bnew\s+Date\s*\("),
        "error",
        "wall-clock time is not a function of the frame; derive everything from useCurrentFrame()",
    ),
    (
        "timer",
        re.compile(r"\b(?:setTimeout|setInterval|requestAnimationFrame)\s*\("),
        "error",
        "timers run on wall-clock time and never fire in a frame render",
    ),
    (
        "css-transition",
        re.compile(
            r"(?:^|[\s{,])[\"']?(?:transition|animation|animationName|transitionProperty)[\"']?\s*:(?!:)"
        ),
        "error",
        "CSS transitions/animations are wall-clock driven; animate the value from the frame instead",
    ),
    (
        "keyframes",
        re.compile(r"@keyframes\b"),
        "error",
        "CSS @keyframes do not render frame-accurately",
    ),
    (
        "reflow",
        re.compile(
            r"\b(?:fontSize|width|height|left|top|padding|margin|letterSpacing)\s*:\s*[^,\n]*\b(?:frame|progress|interpolate|spring)\b"
        ),
        "error",
        "animating layout properties reflows text and jumps line breaks; animate transform/opacity",
    ),
    (
        "hand-duration",
        re.compile(r"durationInFrames\s*=\s*\{\s*\d+\s*\}"),
        "warn",
        "hand-typed durationInFrames; derive it from timeline.ts so it matches the storyboard",
    ),
    (
        "global-frame",
        re.compile(r"useCurrentFrame\s*\(\s*\)\s*[-+]\s*(?:beat|scene)\w*\.startFrame"),
        "warn",
        "useCurrentFrame() is already local inside a Sequence; subtracting the beat start double-shifts",
    ),
    (
        "fetch",
        re.compile(r"\bfetch\s*\("),
        "warn",
        "fetch() at render time must be wrapped in delayRender()/continueRender() and should read a local staticFile()",
    ),
    (
        "gsap",
        re.compile(r"\bfrom\s+['\"](?:gsap|framer-motion|motion/react|animejs|lottie-web)['\"]"),
        "error",
        "wall-clock animation libraries do not play in a frame render; drive values from useCurrentFrame()",
    ),
    (
        "linear-only",
        re.compile(r"\beasing\s*:\s*Easing\.linear\b"),
        "warn",
        "linear easing reads mechanical for entrances/exits; keep it for constant-speed travel only",
    ),
]


def strip_comments(text: str) -> str:
    """Blank out // and /* */ comments (keeping newlines) without touching string contents."""
    out: list[str] = []
    i, n = 0, len(text)
    quote: str | None = None
    while i < n:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end == -1 else end
            out.append(" " * (end - i))
            i = end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append("".join("\n" if c == "\n" else " " for c in text[i:end]))
            i = end
            continue
        out.append(ch)
        i += 1
    return "".join(out)


INTERPOLATE_CALL_RE = re.compile(r"\binterpolate\s*\(")
CLAMP_RE = re.compile(r"extrapolate(?:Left|Right)\s*:\s*[\"']clamp[\"']")
UNCLAMPED_MSG = (
    "interpolate() without extrapolateLeft/Right: 'clamp' keeps moving after the range ends"
)
SPRING_CALL_RE = re.compile(r"\bspring\s*\(")
SPRING_MSG = (
    "spring() needs the composition fps ({ frame, fps, ... }) or its timing changes with fps"
)


def call_args(code: str, call_re: re.Pattern[str]) -> list[tuple[int, str]]:
    """(offset, argument text) for every call matched by call_re, using balanced parens."""
    found = []
    for m in call_re.finditer(code):
        depth, i = 1, m.end()
        while i < len(code) and depth:
            depth += {"(": 1, ")": -1}.get(code[i], 0)
            i += 1
        found.append((m.start(), code[m.end() : i]))
    return found


def spring_calls_without_fps(code: str) -> list[int]:
    """Offsets of spring( calls whose balanced argument list never names fps."""
    return [off for off, args in call_args(code, SPRING_CALL_RE) if not re.search(r"\bfps\b", args)]


def interpolate_calls_unclamped(code: str) -> list[int]:
    """Offsets of interpolate( calls that do not clamp both ends."""
    return [
        off for off, args in call_args(code, INTERPOLATE_CALL_RE) if len(CLAMP_RE.findall(args)) < 2
    ]


def lint_text(text: str, name: str) -> list[tuple[str, int, str, str]]:
    """Return (severity, line, rule id, message) findings for one file."""
    findings = []
    code = strip_comments(text)
    for rule_id, pattern, severity, message in RULES:
        for m in pattern.finditer(code):
            line = code.count("\n", 0, m.start()) + 1
            findings.append((severity, line, rule_id, message))
    for offset in spring_calls_without_fps(code):
        findings.append(("error", code.count("\n", 0, offset) + 1, "spring-fps", SPRING_MSG))
    for offset in interpolate_calls_unclamped(code):
        findings.append(("warn", code.count("\n", 0, offset) + 1, "unclamped", UNCLAMPED_MSG))
    findings.sort(key=lambda f: f[1])
    return [(s, ln, f"{name}:{ln}", f"[{rid}] {msg}") for s, ln, rid, msg in findings]


def collect(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(
                sorted(
                    f
                    for f in p.rglob("*")
                    if f.suffix in (".ts", ".tsx") and "node_modules" not in f.parts
                )
            )
        elif p.is_file():
            files.append(p)
    return files


def self_test() -> None:
    bad = """
import { gsap } from "gsap";
const x = Math.random();
const t = Date.now();
setTimeout(() => {}, 10);
const style = { transition: "opacity 0.3s", fontSize: interpolate(frame, [0, 10], [10, 20]) };
const s = spring({ frame, config: { damping: 200 } });
const y = interpolate(frame, [0, 30], [0, 1]);
<Composition durationInFrames={60} />
const local = useCurrentFrame() - beat.startFrame;
// Math.random() in a comment is fine
const url = "https://x"; Math.random();
const z = interpolate(frame, [0, 1], [0, 1], { extrapolateRight: "extend" });
const styled = { "transition": "opacity 1s" };
/* multi
   line */ Date.now();
"""
    found = lint_text(bad, "bad.tsx")
    ids = {f[3].split("]")[0][1:] for f in found}
    for expected in (
        "gsap",
        "random",
        "clock",
        "timer",
        "css-transition",
        "reflow",
        "spring-fps",
        "unclamped",
        "hand-duration",
        "global-frame",
    ):
        assert expected in ids, (expected, ids)
    assert not any(f[1] == 11 for f in found), "comment line must not be flagged"
    lines_by_rule = {(f[3].split("]")[0][1:], f[1]) for f in found}
    assert ("random", 12) in lines_by_rule, "// inside a string must not hide the call"
    assert ("unclamped", 13) in lines_by_rule, "extend is not clamp"
    assert ("css-transition", 14) in lines_by_rule, "quoted style keys count"
    assert ("clock", 16) in lines_by_rule, "line numbers must survive a multi-line comment"
    good = """
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const p = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 12 });
const o = interpolate(frame, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
const style = { opacity: o, transform: `translateY(${(1 - p) * 40}px)` };
const seed = random("dots");
<TransitionSeries.Sequence durationInFrames={beat.durationInFrames} />
const transition = beat.transitionType;
const link = "https://remotion.dev/docs";
"""
    assert lint_text(good, "good.tsx") == [], lint_text(good, "good.tsx")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "a.tsx").write_text(good)
        (d / "node_modules").mkdir()
        (d / "node_modules" / "x.ts").write_text(bad)
        assert collect([d]) == [d / "a.tsx"]
    print("self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    files = collect(args.paths or [Path("src")])
    if not files:
        print("nothing to lint (no .ts/.tsx files found)", file=sys.stderr)
        return 2
    errors = warns = 0
    for f in files:
        for severity, _line, where, message in lint_text(
            f.read_text(encoding="utf-8", errors="replace"), str(f)
        ):
            print(f"{'ERROR' if severity == 'error' else 'WARN '} {where}: {message}")
            if severity == "error":
                errors += 1
            else:
                warns += 1
    print(
        f"{'FAIL' if errors else 'OK'}: {errors} error(s), {warns} warning(s) in {len(files)} file(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
