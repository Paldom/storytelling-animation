#!/usr/bin/env python3
"""Check an assets manifest for a rendered vector animation: declarations and file hygiene.

Fails closed on what it can see: every asset needs a known license id and a
source; attribution licenses need the credit line; non-commercial, no-derivative
and copyleft ids are excluded by policy; SVG and Lottie files are parsed and
rejected when they carry scripts, event handlers, external references (href,
url(...), fonts), rasters, or autonomous animation (SMIL, CSS animations,
expressions), none of which render deterministically frame by frame.

It validates declarations and file structure. It does not certify legal
permission, and it is a hygiene gate, not a security boundary.

Usage:
    python3 check_assets.py assets/manifest.json --root .                       # check
    python3 check_assets.py assets/manifest.json --root . --write-attribution ATTRIBUTION.md
    python3 check_assets.py --self-test

Exit codes: 0 = clean, 1 = findings, 2 = unreadable manifest. Stdlib only.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

MANIFEST_VERSION = 1
MAX_SVG_BYTES = 512 * 1024
MAX_LOTTIE_BYTES = 2 * 1024 * 1024
SVG_NS = "http://www.w3.org/2000/svg"
KINDS = {"icon", "illustration", "lottie", "shape"}
FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}
# license id -> credit required in the delivered media. Ids follow SPDX where one
# exists. Redistribution notices (MIT/ISC/Apache NOTICE) apply when you ship the
# source files, not the rendered video; keep the license text next to the files.
LICENSES: dict[str, bool] = {
    "ISC": False,
    "MIT": False,
    "Apache-2.0": False,
    "BSD-2-Clause": False,
    "BSD-3-Clause": False,
    "CC0-1.0": False,
    "OFL-1.1": False,
    "Ubuntu-Font-1.0": False,
    "Unlicense": False,
    "CC-BY-4.0": True,
    "CC-BY-3.0": True,
    "Lottie-Simple-License": False,  # LottieFiles public animations
    "unDraw": False,  # unDraw open license: commercial use, no credit, no pack redistribution
    "Attribution-Free-Tier": True,  # Flaticon / Storyset / Icons8 / Lordicon free tiers
    "Paid-License": False,  # purchased or subscription terms: needs license_ref
    "Own-Work": False,  # drawn for this project
}
# Excluded by this skill's policy for client work (a conservative default, not a
# legal finding): non-commercial, no-derivatives, copyleft, personal-use terms.
EXCLUDED_LICENSE_RE = re.compile(r"\bNC\b|\bND\b|NonCommercial|NoDeriv|\bGPL|personal", re.I)
BANNED_SVG_TAGS = {
    "script",
    "foreignObject",
    "image",
    "animate",
    "animateTransform",
    "animateMotion",
    "set",
    "audio",
    "video",
    "iframe",
    "use",  # <use href="#..."> is fine in browsers but hides geometry from draw-on animation
}
URL_REF_RE = re.compile(r"url\s*\(\s*['\"]?\s*([^'\")]*)", re.I)
CSS_BAD_RE = re.compile(r"@import|@keyframes|\banimation\b|\btransition\b", re.I)


def tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_bounded(path: Path, limit: int) -> bytes | None:
    """Read at most limit+1 bytes; None means the file is over the limit."""
    with path.open("rb") as fh:
        raw = fh.read(limit + 1)
    return None if len(raw) > limit else raw


def bad_url_refs(value: str) -> list[str]:
    """url(...) references that are not local fragments."""
    return [m for m in URL_REF_RE.findall(value) if not m.strip().startswith("#")]


def check_svg(path: Path) -> tuple[list[str], list[float]]:
    """Return (problems, stroke widths seen on elements)."""
    widths: list[float] = []
    raw = read_bounded(path, MAX_SVG_BYTES)
    if raw is None:
        return [f"larger than {MAX_SVG_BYTES} bytes (raster in disguise or unoptimised)"], widths
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in raw:
        return ["not UTF-8 XML (UTF-16 or NUL bytes); re-save as UTF-8"], widths
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return ["contains a DTD or entity declaration (icons never need one)"], widths
    try:
        # S314: stdlib expat is what a dependency-free skill has. The input is
        # size-bounded, UTF-8 only, DTD/entity declarations are rejected above, and
        # ElementTree does not fetch external entities. Hygiene gate, not a sandbox.
        root = ET.fromstring(raw)  # noqa: S314
    except ET.ParseError as exc:
        return [f"not well-formed XML: {exc}"], widths
    problems: list[str] = []
    if root.tag != "{" + SVG_NS + "}svg":
        problems.append("root element is not <svg> in the SVG namespace")
    if not root.get("viewBox"):
        problems.append("missing viewBox (cannot scale to the frame)")
    for el in root.iter():
        name = tag_name(el.tag)
        if name in BANNED_SVG_TAGS:
            problems.append(
                f"<{name}> is not allowed (scripts, rasters, SMIL, embeds and <use> do not render deterministically)"
            )
        if name == "style" and el.text:
            if CSS_BAD_RE.search(el.text):
                problems.append(
                    "<style> contains @import or CSS animation/transition (wall-clock driven)"
                )
            problems.extend(
                f"<style> references an external resource url({u})" for u in bad_url_refs(el.text)
            )
        for attr, value in el.attrib.items():
            local = tag_name(attr)
            if local.lower().startswith("on"):
                problems.append(f"event handler attribute {local}")
            if local == "href" and not value.startswith("#"):
                problems.append(f"external reference href={value[:60]!r}")
            if local == "style" and CSS_BAD_RE.search(value):
                problems.append("inline style contains CSS animation/transition")
            problems.extend(
                f"{local}=url({u}) references an external resource" for u in bad_url_refs(value)
            )
            if local == "stroke-width":
                with contextlib.suppress(ValueError):
                    widths.append(float(value))
    return problems, widths


def find_expressions(node: object, path: str = "") -> list[str]:
    """Property objects with an "x" expression string, found on the decoded tree."""
    found: list[str] = []
    if isinstance(node, dict):
        if isinstance(node.get("x"), str) and node.get("x").strip():
            found.append(path or "<root>")
        for k, v in node.items():
            found.extend(find_expressions(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found.extend(find_expressions(v, f"{path}[{i}]"))
    return found


def check_lottie(path: Path) -> list[str]:
    raw = read_bounded(path, MAX_LOTTIE_BYTES)
    if raw is None:
        return [f"larger than {MAX_LOTTIE_BYTES} bytes"]
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return [f"not valid UTF-8 JSON: {exc}"]
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["not a Lottie animation (top level is not an object)"]
    fr, ip, op, w, h = (data.get(k) for k in ("fr", "ip", "op", "w", "h"))
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    if not (
        num(fr)
        and fr > 0
        and num(ip)
        and num(op)
        and op > ip
        and num(w)
        and w > 0
        and num(h)
        and h > 0
    ):
        problems.append("missing or invalid fr/ip/op/w/h (frame rate, in/out point, size)")
    if not isinstance(data.get("layers"), list) or not data["layers"]:
        problems.append("layers must be a non-empty list")
        return problems
    for asset in data.get("assets") or []:
        if isinstance(asset, dict) and ("p" in asset or "u" in asset or "e" in asset):
            problems.append(
                f"asset {asset.get('id')!r} is an image asset (vector-only policy; embedded or external)"
            )
    for layer in data["layers"]:
        if isinstance(layer, dict) and layer.get("ty") in (2, 6, 9):
            problems.append(
                f"layer {layer.get('nm')!r} is an image/audio/video layer (vector-only policy)"
            )
    fonts = data.get("fonts")
    if isinstance(fonts, dict):
        for f in fonts.get("list") or []:
            if isinstance(f, dict) and (f.get("fPath") or f.get("origin") not in (None, 0)):
                problems.append(f"font {f.get('fName')!r} loads from an external path")
    exprs = find_expressions(data)
    if exprs:
        problems.append(
            f"contains After Effects expressions at {exprs[0]} (+{len(exprs) - 1} more); they do not evaluate in frame renders"
        )
    return problems


def resolve_inside(root: Path, rel: str) -> Path | None:
    """Resolve a manifest path under root, or None if it escapes or is absolute."""
    if not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts:
        return None
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def check_entry(
    a: object,
    where: str,
    root: Path,
    is_font: bool,
    errors: list[str],
    warnings: list[str],
    credits: list[dict],
    widths_by_pack: dict[str, list[float]],
    packs: set[str],
) -> None:
    if not isinstance(a, dict):
        errors.append(f"{where}: must be an object")
        return
    label = str(a.get("file") or a.get("family") or where)
    lic = a.get("license")
    if not isinstance(lic, str) or not lic:
        errors.append(f"{label}: license missing (unknown rights fail closed)")
        return
    if lic not in LICENSES:
        if EXCLUDED_LICENSE_RE.search(lic):
            errors.append(
                f"{label}: license {lic!r} is excluded by policy (non-commercial, no-derivative, copyleft or personal-use terms)"
            )
        else:
            errors.append(
                f"{label}: license {lic!r} is not a known id; read the terms, then add it to LICENSES with its credit rule"
            )
        return
    src = a.get("source")
    if not isinstance(src, str) or not src.startswith(("http://", "https://", "own:")):
        errors.append(
            f"{label}: source must be the URL the file came from (or own:<who> for original work)"
        )
    if lic == "Paid-License" and not isinstance(a.get("license_ref"), str):
        errors.append(
            f"{label}: Paid-License needs license_ref (order id, plan, or license file path)"
        )
    if LICENSES[lic] or a.get("attribution_required") is True:
        credit = a.get("attribution")
        if not isinstance(credit, str) or not credit.strip():
            errors.append(
                f"{label}: {lic} requires a credit; put the exact credit line in 'attribution'"
            )
        else:
            credits.append({"label": label, "attribution": credit.strip(), "source": src})
    if is_font:
        if not isinstance(a.get("family"), str) or not a["family"].strip():
            errors.append(f"{where}: fonts need a family name")
        if "file" in a:
            p = resolve_inside(root, str(a["file"]))
            if p is None or not p.is_file():
                errors.append(f"{label}: font file not found under {root}")
            elif p.suffix.lower() not in FONT_SUFFIXES:
                errors.append(f"{label}: font files must be {', '.join(sorted(FONT_SUFFIXES))}")
        else:
            warnings.append(
                f"{label}: no local font file; a Google Fonts load needs network at render time"
            )
        return
    kind = a.get("kind", "icon")
    if kind not in KINDS:
        errors.append(f"{label}: kind must be one of {sorted(KINDS)}")
        kind = "icon"
    pack = a.get("pack")
    if not isinstance(pack, str) or not pack.strip():
        errors.append(f"{label}: pack is required (the set it came from, or 'own')")
        pack = "?"
    if pack != "own" and lic != "Own-Work" and not isinstance(a.get("version"), str):
        warnings.append(f"{label}: no pack version recorded; pin the release you copied from")
    rel = a.get("file")
    if not isinstance(rel, str) or not rel:
        errors.append(f"{where}: file is required (path relative to --root)")
        return
    path = resolve_inside(root, rel)
    if path is None:
        errors.append(f"{label}: path must be relative and stay inside {root}")
        return
    if not path.is_file():
        errors.append(f"{label}: file not found under {root}")
        return
    suffix = path.suffix.lower()
    if suffix == ".svg":
        problems, widths = check_svg(path)
        if kind == "icon":
            widths_by_pack[pack].extend(widths)
            packs.add(pack)
    elif suffix == ".json":
        problems = check_lottie(path)
    else:
        problems = [
            f"unsupported asset type {suffix}; vector video assets are .svg or Lottie .json"
        ]
    errors.extend(f"{label}: {p}" for p in problems)


def check_manifest(manifest: dict, root: Path) -> tuple[list[str], list[str], list[dict]]:
    errors: list[str] = []
    warnings: list[str] = []
    credits: list[dict] = []
    if manifest.get("version") != MANIFEST_VERSION:
        errors.append(f"manifest version must be {MANIFEST_VERSION}")
    assets = manifest.get("assets")
    fonts = manifest.get("fonts", [])
    if not isinstance(assets, list) or not assets:
        errors.append("manifest.assets must be a non-empty list")
        return errors, warnings, credits
    if not isinstance(fonts, list):
        errors.append("manifest.fonts must be a list when present")
        fonts = []
    widths_by_pack: dict[str, list[float]] = defaultdict(list)
    packs: set[str] = set()
    for i, a in enumerate(assets):
        check_entry(
            a, f"assets[{i}]", root, False, errors, warnings, credits, widths_by_pack, packs
        )
    for i, f in enumerate(fonts):
        check_entry(f, f"fonts[{i}]", root, True, errors, warnings, credits, widths_by_pack, packs)
    icon_packs = packs - {"own"}
    if len(icon_packs) > 1:
        warnings.append(
            f"{len(icon_packs)} icon packs mixed ({', '.join(sorted(icon_packs))}); grids and stroke weights will not match"
        )
    for pack, widths in widths_by_pack.items():
        distinct = sorted({round(w, 2) for w in widths})
        if len(distinct) > 1:
            warnings.append(
                f"pack {pack}: stroke-width varies across files ({distinct}); pick one weight"
            )
    return errors, warnings, credits


def write_attribution(credits: list[dict], out: Path) -> None:
    lines = [
        "# Attribution",
        "",
        "Credits that must accompany this animation (post text, slide, or on screen as the license requires):",
        "",
    ]
    lines.extend(f"- {c['attribution']} ({c['label']}, {c['source']})" for c in credits)
    if not credits:
        lines.append("- none required")
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(out)


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ok.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><defs><linearGradient id="g"/></defs><circle cx="12" cy="12" r="10" fill="url(#g)"/></svg>'
        )
        (root / "bad.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="24" height="24"><style>@keyframes a{}</style><script>alert(1)</script><image xlink:href="http://x/y.png"/><rect onclick="x" stroke-width="1.5" fill="url(https://x/p.svg#g)"/><animate attributeName="x"/></svg>'
        )
        (root / "utf16.svg").write_bytes("﻿<svg/>".encode("utf-16"))
        (root / "big.svg").write_bytes(b"<svg" + b" " * (MAX_SVG_BYTES + 10))
        (root / "ok.json").write_text(
            json.dumps(
                {
                    "v": "5.12.2",
                    "fr": 30,
                    "ip": 0,
                    "op": 30,
                    "w": 100,
                    "h": 100,
                    "layers": [{"ty": 4, "nm": "shape"}],
                    "assets": [],
                }
            )
        )
        (root / "bad.json").write_text(
            json.dumps(
                {
                    "fr": 0,
                    "layers": [{"ty": 2, "nm": "img"}, {"ks": {"o": {"x": "var $bm_rt = 1"}}}],
                    "assets": [{"id": "i", "u": "images/", "p": "img_0.png"}],
                    "fonts": {"list": [{"fName": "F", "fPath": "https://x/f.ttf"}]},
                }
            )
        )
        (root / "Inter.ttf").write_bytes(b"\x00\x01\x00\x00")
        manifest = {
            "version": 1,
            "assets": [
                {
                    "file": "ok.svg",
                    "pack": "Lucide",
                    "version": "0.577.0",
                    "source": "https://lucide.dev/icons/circle",
                    "license": "ISC",
                },
                {
                    "file": "bad.svg",
                    "pack": "Lucide",
                    "version": "0.577.0",
                    "source": "https://example.com",
                    "license": "ISC",
                },
                {"file": "utf16.svg", "pack": "own", "source": "own:me", "license": "Own-Work"},
                {"file": "big.svg", "pack": "own", "source": "own:me", "license": "Own-Work"},
                {
                    "file": "ok.json",
                    "kind": "lottie",
                    "pack": "LottieFiles",
                    "version": "1",
                    "source": "https://lottiefiles.com/x",
                    "license": "Lottie-Simple-License",
                },
                {
                    "file": "bad.json",
                    "kind": "lottie",
                    "pack": "own",
                    "source": "own:me",
                    "license": "Own-Work",
                },
                {
                    "file": "ok.svg",
                    "kind": "illustration",
                    "pack": "Storyset",
                    "version": "1",
                    "source": "https://storyset.com/x",
                    "license": "Attribution-Free-Tier",
                },
                {"file": "ok.svg", "pack": "X", "source": "https://x", "license": "CC-BY-NC-4.0"},
                {"file": "ok.svg", "pack": "Y", "source": "https://y", "license": "Paid-License"},
                {"file": "../ok.svg", "pack": "Z", "source": "https://z", "license": "MIT"},
                {"source": "https://q", "license": "MIT"},
                {"file": "missing.svg", "pack": "Z", "source": "https://z"},
            ],
            "fonts": [
                {
                    "family": "Inter",
                    "file": "Inter.ttf",
                    "source": "https://fonts.google.com/specimen/Inter",
                    "license": "OFL-1.1",
                },
                {
                    "family": "Roboto",
                    "source": "https://fonts.google.com/specimen/Roboto",
                    "license": "Apache-2.0",
                },
            ],
        }
        errors, warnings, credits = check_manifest(manifest, root)
        joined = "\n".join(errors)
        for needle in (
            "<script>",
            "<image>",
            "<animate>",
            "onclick",
            "@import or CSS animation",
            "url(https://x/p.svg#g)",
            "missing viewBox",
            "not UTF-8 XML",
            "larger than",
            "invalid fr/ip/op",
            "image/audio/video layer",
            "image asset",
            "external path",
            "expressions at",
            "requires a credit",
            "excluded by policy",
            "needs license_ref",
            "stay inside",
            "file is required",
            "license missing",
        ):
            assert needle in joined, f"expected finding {needle!r} in:\n{joined}"
        hygiene = [
            e
            for e in errors
            if e.startswith(("ok.svg: ", "ok.json: "))
            and not any(k in e for k in ("credit", "excluded", "license_ref"))
        ]
        assert not hygiene, hygiene
        assert any("packs mixed" in w for w in warnings) and any(
            "stroke-width varies" in w for w in warnings
        ), warnings
        assert any("no local font file" in w for w in warnings), warnings
        assert credits == [], credits
        clean = {
            "version": 1,
            "assets": [
                {
                    "file": "ok.svg",
                    "pack": "Lucide",
                    "version": "0.577.0",
                    "source": "https://lucide.dev/icons/circle",
                    "license": "ISC",
                }
            ],
        }
        errors, warnings, credits = check_manifest(clean, root)
        assert not errors and not warnings, (errors, warnings)
        credited = {
            "version": 1,
            "assets": [
                {
                    "file": "ok.svg",
                    "kind": "illustration",
                    "pack": "Storyset",
                    "version": "1",
                    "source": "https://storyset.com/x",
                    "license": "Attribution-Free-Tier",
                    "attribution": "Illustration by Storyset",
                }
            ],
        }
        errors, _, credits = check_manifest(credited, root)
        assert not errors and credits[0]["attribution"] == "Illustration by Storyset", (
            errors,
            credits,
        )
        write_attribution(credits, root / "ATTRIBUTION.md")
        assert "Illustration by Storyset" in (root / "ATTRIBUTION.md").read_text()
    print("self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("manifest", nargs="?", type=Path)
    ap.add_argument(
        "--root",
        type=Path,
        help="project root that asset paths are relative to (default: the manifest's folder)",
    )
    ap.add_argument(
        "--write-attribution", type=Path, metavar="FILE", help="write the credit lines to FILE"
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.manifest is None:
        ap.error("manifest path required")
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR cannot read {args.manifest}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(manifest, dict):
        print("ERROR manifest must be a JSON object", file=sys.stderr)
        return 2
    root = (args.root or args.manifest.parent).resolve()
    errors, warnings, credits = check_manifest(manifest, root)
    for line in errors:
        print(f"ERROR {line}", file=sys.stderr)
    for line in warnings:
        print(f"WARN  {line}", file=sys.stderr)
    if args.write_attribution and not errors:
        if args.write_attribution.resolve() == args.manifest.resolve():
            print("ERROR --write-attribution must not overwrite the manifest", file=sys.stderr)
            return 1
        write_attribution(credits, args.write_attribution)
        print(f"wrote {args.write_attribution} ({len(credits)} credit line(s))")
    n = len(manifest.get("assets") or [])
    print(
        f"{'FAIL' if errors else 'OK'}: {len(errors)} error(s), {len(warnings)} warning(s), {n} asset(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
