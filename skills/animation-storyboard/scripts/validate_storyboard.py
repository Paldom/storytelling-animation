#!/usr/bin/env python3
"""Validate a storyboard.json (contract v1) for a silent-autoplay vector animation.

The storyboard is the timing contract every later step (layout, motion, export,
QA) reads. This script owns the timing rules: seconds are quantised ONCE to
integer frames and every check (overlap, readable hold, budgets, loop period)
runs on those frames, so validation and rendering share one clock. The summary
publishes the canonical frame schedule downstream code must use.

Usage:
    python3 validate_storyboard.py storyboard.json            # human summary
    python3 validate_storyboard.py storyboard.json --json     # one JSON document on stdout
    python3 validate_storyboard.py storyboard.json --strict   # warnings fail too
    python3 validate_storyboard.py --self-test

Exit codes: 0 = valid, 1 = errors (or warnings with --strict), 2 = unreadable file.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

CONTRACT_VERSION = 1
# Reading policy. Sources: BBC subtitle guidelines 160-180 wpm = 0.33-0.375 s/word;
# Netflix timed-text 20 characters/s for adults; DCMP minimum 40 frames (1.33 s).
ENTER_S = 0.4  # a card spends this animating in before it is readable
EXIT_S = 0.3  # and this animating out
MIN_HOLD_S = 1.33  # floor for any text card (DCMP 40 frames)
PER_WORD_S = 0.35  # BBC mid-point
PER_CHAR_S = 1 / 20  # Netflix 20 cps: bites only on long words, URLs, unspaced scripts
MAX_WORDS = 8  # a card is a headline, not a subtitle
MAX_WORDS_VERBATIM = 20  # legal/brand sentences flagged "verbatim": true
MAX_CHARS = 64  # ~2 lines at phone scale
MAX_CHARS_VERBATIM = 160
MIN_FPS, MAX_FPS = 24, 60
MAX_BEAT_S = 600.0
TRANSITIONS = {"cut", "fade", "slide", "wipe", "morph", "none"}
OVERLAPPING = {"fade", "slide", "wipe", "morph"}
ROLES = {"hook", "body", "cta"}
TARGETS = {
    "linkedin-4x5",
    "linkedin-1x1",
    "linkedin-9x16",
    "linkedin-16x9",
    "pptx-16x9",
    "pptx-4k",
    "gif-loop",
    "custom",
}
ID_RE = re.compile(r"[a-z][a-z0-9-]{0,31}")  # Remotion composition ids allow no underscore
# Length budgets in seconds (hard minimum, warn above, hard maximum). These are this
# skill's POLICY, chosen from platform guidance (references/story-rules.md); the
# platforms' own upload limits are far larger.
BUDGETS: dict[str, tuple[float, float, float]] = {
    "linkedin": (3.0, 60.0, 90.0),
    "pptx": (1.0, 120.0, 300.0),
    "gif": (1.0, 8.0, 15.0),
    "custom": (1.0, 120.0, 900.0),
}


def to_frames(seconds: float, fps: int) -> int:
    """The one rounding rule: nearest frame, halves round up."""
    return math.floor(seconds * fps + 0.5)


MAX_ABS_NUMBER = 1e12  # anything larger is a typo, and huge ints overflow float math


def is_number(x: object, lo: float = 0.0, hi: float = float("inf")) -> bool:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return False
    if isinstance(x, int) and abs(x) > MAX_ABS_NUMBER:
        return False
    return math.isfinite(x) and abs(x) <= MAX_ABS_NUMBER and lo <= x <= hi


def is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def budget_for(target: str) -> tuple[float, float, float]:
    return BUDGETS.get(target.split("-", 1)[0], BUDGETS["custom"])


def reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not valid JSON (NaN/Infinity are not numbers here)")


def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    seen: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key {key!r}")
        seen[key] = value
    return seen


def check_header(sb: dict, errors: list[str]) -> tuple[int, list[str], bool]:
    if not (is_int(sb.get("version")) and sb["version"] == CONTRACT_VERSION):
        errors.append(f"version must be the integer {CONTRACT_VERSION}")
    fps = sb.get("fps")
    if not (is_int(fps) and MIN_FPS <= fps <= MAX_FPS):
        errors.append(f"fps must be an integer in {MIN_FPS}..{MAX_FPS}")
        fps = 30
    targets = sb.get("targets")
    if not (isinstance(targets, list) and targets and all(isinstance(t, str) for t in targets)):
        errors.append("targets must be a non-empty list of preset ids")
        targets = ["custom"]
    for t in targets:
        if t not in TARGETS:
            errors.append(f"unknown target {t!r}; known: {', '.join(sorted(TARGETS))}")
    if "custom" in targets:
        cs = sb.get("custom_size")
        ok = (
            isinstance(cs, dict)
            and is_int(cs.get("width"))
            and is_int(cs.get("height"))
            and cs["width"] > 0
            and cs["height"] > 0
            and cs["width"] % 2 == 0
            and cs["height"] % 2 == 0
        )
        if not ok:
            errors.append("target custom needs custom_size: {width, height} in even pixels")
    loop = sb.get("loop", False)
    if not isinstance(loop, bool):
        errors.append("loop must be true or false")
        loop = False
    if not isinstance(sb.get("title"), str) or not sb["title"].strip():
        errors.append("title must be a non-empty string (display only; ids name files)")
    if "brand" in sb and not isinstance(sb["brand"], dict):
        errors.append("brand must be an object when present")
    for key in ("max_duration_s", "exact_duration_s"):
        if key in sb and not is_number(sb[key], 0.5, 3600):
            errors.append(f"{key} must be a number of seconds (0.5..3600)")
    return fps, targets, loop


def check_beat(
    i: int,
    b: object,
    fps: int,
    loop: bool,
    n: int,
    ids: set[str],
    errors: list[str],
    warnings: list[str],
) -> dict | None:
    where = f"beat[{i}]"
    if not isinstance(b, dict):
        errors.append(f"{where}: must be an object")
        return None
    bid = b.get("id")
    if not (isinstance(bid, str) and ID_RE.fullmatch(bid)):
        errors.append(f"{where}: id must match {ID_RE.pattern} (it names the scene component)")
        bid = f"beat{i}"
    elif bid in ids:
        errors.append(f"{where}: duplicate id {bid!r}")
    ids.add(bid)
    where = f"beat {bid}"
    dur = b.get("duration_s")
    if not is_number(dur, 0.0, MAX_BEAT_S) or dur <= 0:
        errors.append(f"{where}: duration_s must be a number in (0, {MAX_BEAT_S:g}]")
        dur = 1.0
    frames = to_frames(dur, fps)
    if frames <= 0:
        errors.append(f"{where}: duration {dur}s rounds to 0 frames at {fps} fps")
        frames = 1
    if abs(dur * fps - frames) > 1e-6:
        warnings.append(
            f"{where}: duration {dur}s is not whole frames at {fps} fps; scheduled as {frames} frames"
        )
    role = b.get("role", "body")
    if not (isinstance(role, str) and role in ROLES):
        errors.append(f"{where}: role must be one of {sorted(ROLES)}")
        role = "body"
    text = b.get("text", "")
    if not isinstance(text, str):
        errors.append(f"{where}: text must be a string")
        text = ""
    verbatim = b.get("verbatim", False)
    if not isinstance(verbatim, bool):
        errors.append(f"{where}: verbatim must be true or false")
        verbatim = False
    words = text.split()
    max_words = MAX_WORDS_VERBATIM if verbatim else MAX_WORDS
    max_chars = MAX_CHARS_VERBATIM if verbatim else MAX_CHARS
    if len(words) > max_words:
        errors.append(
            f"{where}: {len(words)} words on screen (max {max_words}{' for verbatim text' if verbatim else ''})"
        )
    if len(text) > max_chars:
        errors.append(f"{where}: {len(text)} chars on screen (max {max_chars})")
    for key in ("visual", "motion"):
        if not isinstance(b.get(key), str) or not b[key].strip():
            errors.append(f"{where}: {key} must be a non-empty description")
    tr = b.get("transition", {"type": "cut", "overlap_s": 0})
    if not isinstance(tr, dict):
        errors.append(f"{where}: transition must be an object")
        tr = {"type": "cut", "overlap_s": 0}
    ttype = tr.get("type", "cut")
    if not (isinstance(ttype, str) and ttype in TRANSITIONS):
        errors.append(f"{where}: transition.type must be one of {sorted(TRANSITIONS)}")
        ttype = "cut"
    overlap = tr.get("overlap_s", 0)
    if not is_number(overlap, 0.0, MAX_BEAT_S):
        errors.append(f"{where}: transition.overlap_s must be a number >= 0")
        overlap = 0
    overlap_f = to_frames(overlap, fps)
    is_last = i == n - 1
    if ttype in OVERLAPPING and overlap_f <= 0:
        errors.append(f"{where}: a {ttype} transition needs overlap_s of at least one frame")
    if ttype not in OVERLAPPING and overlap_f > 0:
        errors.append(f"{where}: a {ttype} transition cannot have overlap")
    if is_last and overlap_f > 0 and not loop:
        errors.append(f"{where}: the last beat has nothing to overlap into (loop is false)")
    return {
        "id": bid,
        "role": role,
        "frames": frames,
        "words": len(words),
        "chars": len(text),
        "text": text,
        "verbatim": verbatim,
        "transition": ttype,
        "overlap_out_f": overlap_f,
    }


def validate(sb: dict) -> tuple[list[str], list[str], dict]:
    """Return (errors, warnings, summary). The summary is the canonical frame schedule."""
    errors: list[str] = []
    warnings: list[str] = []
    fps, targets, loop = check_header(sb, errors)
    beats = sb.get("beats")
    min_beats = 1 if loop else 2
    if not (isinstance(beats, list) and len(beats) >= min_beats):
        errors.append(f"beats must be a list of at least {min_beats} beat(s)")
        return errors, warnings, {}
    ids: set[str] = set()
    rows = [
        r
        for i, b in enumerate(beats)
        if (r := check_beat(i, b, fps, loop, len(beats), ids, errors, warnings))
    ]
    if len(rows) != len(beats):
        return errors, warnings, {}

    enter_f, exit_f = to_frames(ENTER_S, fps), to_frames(EXIT_S, fps)
    start = 0
    for i, r in enumerate(rows):
        if i > 0:
            overlap_in = rows[i - 1]["overlap_out_f"]
        else:
            overlap_in = rows[-1]["overlap_out_f"] if loop else 0
        overlap_out = r["overlap_out_f"]
        if overlap_in + overlap_out >= r["frames"]:
            errors.append(
                f"beat {r['id']}: overlaps ({overlap_in + overlap_out} frames) swallow the beat ({r['frames']} frames)"
            )
        readable_f = r["frames"] - enter_f - exit_f - overlap_in - overlap_out
        required_s = (
            max(MIN_HOLD_S, PER_WORD_S * r["words"], PER_CHAR_S * r["chars"]) if r["words"] else 0.0
        )
        required_f = math.ceil(required_s * fps - 1e-9)
        if r["words"] and readable_f < required_f:
            errors.append(
                f"beat {r['id']}: readable hold {readable_f} frames ({readable_f / fps:.2f}s) < required "
                f"{required_f} frames ({required_f / fps:.2f}s) for {r['words']} words / {r['chars']} chars "
                f"(frames - enter {enter_f} - exit {exit_f} - overlaps)"
            )
        r.update(
            {
                "start_f": start,
                "start_s": round(start / fps, 4),
                "duration_s": round(r["frames"] / fps, 4),
                "overlap_in_f": overlap_in,
                "readable_f": readable_f,
                "required_f": required_f,
            }
        )
        start += r["frames"] - overlap_out
    total_f = start
    total_s = total_f / fps

    if rows[0]["role"] != "hook":
        errors.append("the first beat must have role 'hook'")
    if not rows[0]["words"]:
        errors.append(
            "the hook beat needs on-screen text: autoplay is muted, text is the narration"
        )
    if not loop and rows[-1]["role"] != "cta":
        warnings.append("the last beat is not role 'cta'; explainers end on a still call to action")
    if loop and rows[-1]["transition"] not in OVERLAPPING:
        warnings.append(
            "loop is true but the last beat cuts back to the first: the motion step must match pose and velocity at the seam"
        )

    for t in targets:
        lo, warn_at, hi = budget_for(t)
        if total_s < lo:
            errors.append(f"target {t}: total {total_s:.2f}s is below the minimum {lo}s")
        elif total_s > hi:
            errors.append(
                f"target {t}: total {total_s:.2f}s exceeds this skill's maximum policy of {hi}s"
            )
        elif total_s > warn_at:
            warnings.append(f"target {t}: total {total_s:.2f}s is above the recommended {warn_at}s")
    max_s = sb.get("max_duration_s")
    if is_number(max_s, 0.5, 3600) and total_f > to_frames(max_s, fps):
        errors.append(f"total {total_s:.2f}s exceeds the requested max_duration_s {max_s}")
    exact_s = sb.get("exact_duration_s")
    if is_number(exact_s, 0.5, 3600) and total_f != to_frames(exact_s, fps):
        errors.append(
            f"total {total_f} frames is not the requested exact_duration_s {exact_s} ({to_frames(exact_s, fps)} frames)"
        )

    summary = {
        "title": sb.get("title"),
        "fps": fps,
        "targets": targets,
        "custom_size": sb.get("custom_size"),
        "loop": loop,
        "total_frames": total_f,
        "total_s": round(total_s, 4),
        "enter_frames": enter_f,
        "exit_frames": exit_f,
        "beats": rows,
    }
    return errors, warnings, summary


def load(path: Path) -> dict:
    data = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=no_duplicate_keys,
        parse_constant=reject_constant,
    )
    if not isinstance(data, dict):
        raise ValueError("storyboard must be a JSON object")
    return data


def _good() -> dict:
    def beat(bid: str, role: str, dur: float, text: str, tr: dict | None) -> dict:
        b = {"id": bid, "role": role, "duration_s": dur, "text": text, "visual": "v", "motion": "m"}
        if tr is not None:
            b["transition"] = tr
        return b

    return {
        "version": 1,
        "title": "t",
        "fps": 30,
        "targets": ["linkedin-4x5"],
        "loop": False,
        "beats": [
            beat("a", "hook", 3, "Five words on the screen", {"type": "fade", "overlap_s": 0.5}),
            beat("b", "body", 4, "Two words", {"type": "cut", "overlap_s": 0}),
            beat("c", "cta", 3, "Try it", None),
        ],
    }


def _mutated(**changes: object) -> dict:
    sb = _good()
    for path, value in changes.items():
        target: object = sb
        keys = path.split(".")
        for k in keys[:-1]:
            target = target[int(k)] if k.isdigit() else target[k]
        last = keys[-1]
        if last.isdigit():
            target[int(last)] = value
        else:
            target[last] = value
    return sb


def self_test() -> None:
    e, _, s = validate(_good())
    assert not e, e
    assert s["total_frames"] == 285 and s["total_s"] == 9.5, s
    a = s["beats"][0]
    assert a["readable_f"] == 90 - 12 - 9 - 15 and a["required_f"] == 53, a
    # quantised hold: 2.47 s hook, 5 words, 0.04 s fade -> 74 - 12 - 9 - 1 = 52 < 53
    sb = _good()
    sb["beats"][0].update({"duration_s": 2.47, "transition": {"type": "fade", "overlap_s": 0.04}})
    e, _, _ = validate(sb)
    assert any("readable hold 52 frames" in x for x in e), e
    e, _, _ = validate(_mutated(**{"beats.1.text": "one two three four five six seven eight nine"}))
    assert any("9 words" in x for x in e), e
    sb = _good()
    sb["beats"][1].update(
        {
            "text": "one two three four five six seven eight nine ten",
            "verbatim": True,
            "duration_s": 6,
        }
    )
    e, _, _ = validate(sb)
    assert not e, e
    e, _, _ = validate(_mutated(**{"beats.1.text": "a" * 60, "beats.1.duration_s": 3}))
    assert any("60 chars" in x for x in e), e  # character rate: 3 s < 60/20
    e, _, _ = validate(_mutated(**{"beats.0.duration_s": True, "fps": 29.97, "version": True}))
    assert sum(k in "\n".join(e) for k in ("duration_s", "fps", "version")) == 3, e
    for bad in (
        {"beats.0.role": []},
        {"beats.0.transition": {"type": [], "overlap_s": "x"}},
        {"beats.0.id": None},
        {"beats.0.duration_s": 1e308},
        {"brand": 3},
        {"targets": ["linkdin-4x5"]},
    ):
        e, _, _ = validate(_mutated(**bad))
        assert e, bad
    e, _, _ = validate(_mutated(**{"beats.1.duration_s": 0.001, "beats.1.text": ""}))
    assert any("0 frames" in x for x in e), e
    e, _, _ = validate(_mutated(**{"beats.0.transition": {"type": "fade", "overlap_s": 0}}))
    assert any("at least one frame" in x for x in e), e
    e, _, _ = validate(_mutated(targets=["gif-loop"], **{"beats.1.duration_s": 20}))
    assert any("exceeds" in x for x in e), e
    e, _, _ = validate(_mutated(max_duration_s=9))
    assert any("max_duration_s" in x for x in e), e
    e, _, _ = validate(_mutated(exact_duration_s=9.5))
    assert not e, e
    e, _, _ = validate(_mutated(targets=["custom"]))
    assert any("custom_size" in x for x in e), e
    e, _, _ = validate(_mutated(targets=["custom"], custom_size={"width": 1440, "height": 1440}))
    assert not e, e
    # single-card loop: 8 s card, wrap fade 0.5 s -> period 225 frames = 7.5 s
    one = {
        "version": 1,
        "title": "loop",
        "fps": 30,
        "targets": ["pptx-16x9"],
        "loop": True,
        "exact_duration_s": 7.5,
        "beats": [
            {
                "id": "card",
                "role": "hook",
                "duration_s": 8,
                "text": "Quarterly review",
                "visual": "v",
                "motion": "m",
                "transition": {"type": "fade", "overlap_s": 0.5},
            }
        ],
    }
    e, w, s = validate(one)
    assert not e and not w, (e, w)
    assert s["total_frames"] == 225 and s["beats"][0]["overlap_in_f"] == 15, s
    e, _, _ = validate(_mutated(**{"beats.0.role": "body"}))
    assert any("role 'hook'" in x for x in e), e
    for absurd in (
        {"max_duration_s": 1e308},
        {"exact_duration_s": 1e308},
        {"beats.0.duration_s": 10**400},
        {"beats.0.transition": {"type": "fade", "overlap_s": 10**400}},
        {"beats.0.id": "hook\n"},
        {"beats.0.id": "hook_1"},
    ):
        e, _, s = validate(_mutated(**absurd))
        assert e, absurd
        json.dumps(s, allow_nan=False)
    e, _, s = validate(
        _mutated(
            **{
                "beats.0.duration_s": 2.45,
                "beats.1.duration_s": 2.45,
                "beats.0.transition": {"type": "cut", "overlap_s": 0},
                "beats.0.text": "Hi",
                "beats.1.text": "Hi",
            }
        )
    )
    assert not e and s["beats"][0]["frames"] + s["beats"][1]["frames"] == 148, (
        e,
        s,
    )  # per-beat rounding, not 147
    try:
        json.loads('{"a": NaN}', parse_constant=reject_constant)
    except ValueError as exc:
        assert "NaN" in str(exc)
    else:
        raise AssertionError("NaN must be rejected")
    try:
        json.loads('{"a": 1, "a": 2}', object_pairs_hook=no_duplicate_keys)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate keys must be rejected")
    print("self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("storyboard", nargs="?", type=Path)
    ap.add_argument(
        "--json", action="store_true", help="print only the machine-readable summary on stdout"
    )
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.storyboard is None:
        ap.error("storyboard path required")
    try:
        sb = load(args.storyboard)
    except (OSError, ValueError) as exc:
        print(f"ERROR cannot read {args.storyboard}: {exc}", file=sys.stderr)
        return 2
    errors, warnings, summary = validate(sb)
    for line in errors:
        print(f"ERROR {line}", file=sys.stderr)
    for line in warnings:
        print(f"WARN  {line}", file=sys.stderr)
    failed = bool(errors) or (args.strict and bool(warnings))
    status = f"{'FAIL' if failed else 'OK'}: {len(errors)} error(s), {len(warnings)} warning(s)"
    if args.json:
        print(json.dumps(summary, indent=2, allow_nan=False))
        print(status, file=sys.stderr)
        return 1 if failed else 0
    if summary:
        print(
            f"{summary['title']}: {summary['total_frames']} frames = {summary['total_s']}s @ {summary['fps']} fps, "
            f"{len(summary['beats'])} beats, targets {', '.join(summary['targets'])}{', loop' if summary['loop'] else ''}"
        )
        for r in summary["beats"]:
            print(
                f"  {r['id']:<10} {r['role']:<5} start {r['start_f']:>5}f  {r['frames']:>4}f  words={r['words']:<2} "
                f"readable={r['readable_f']}f need={r['required_f']}f"
            )
    print(status)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
