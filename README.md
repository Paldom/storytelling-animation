<p align="center">
  <img src="assets/icon.svg" alt="storytelling-animation icon" width="128"/>
</p>

# Storytelling Animation

Agent Skills that take a written brief and produce a smooth vector storytelling animation, sized and encoded for LinkedIn, PowerPoint or any resolution, with a verifier gate after every step.

[![CI](https://github.com/Paldom/storytelling-animation/actions/workflows/ci.yml/badge.svg)](https://github.com/Paldom/storytelling-animation/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![skills.sh](https://skills.sh/b/Paldom/storytelling-animation)](https://skills.sh/Paldom/storytelling-animation)

## Demo

![The bundled example storyboard rendered through the pipeline: five text-card beats, fade transitions, a still CTA](assets/demo/example.gif)

The example above is `skills/animation-storyboard/assets/storyboard.example.json` run through layout, motion and export as the GIF preset; its contact sheet from the QA step is `assets/demo/contact-sheet.png`. Both regenerate from `assets/demo/regenerate.sh`.

## Quick start

```bash
npx skills add Paldom/storytelling-animation
```

Then describe the video to your agent, or invoke the pipeline by name:

```text
/storytelling-animation Teams waste hours copying data between tools. Our connector syncs it in one click. CTA: try it free at example.com. Targets: LinkedIn 4:5 and a PowerPoint slide. Brand: dark navy, off-white text, blue accent, Inter.
```

A single step works on its own too:

```text
/animation-storyboard turn this brief into a 30 second storyboard for a LinkedIn post
/animation-export-presets render the finished composition for LinkedIn and as an 8 second GIF loop
/animation-frame-qa review out/linkedin-4x5.mp4 before I post it
```

Requirements on the machine that renders: Node 18+, ffmpeg and ffprobe on PATH, Python 3.10+. The video engine is Remotion; it is free for individuals, companies of up to three people and non-profits, and needs a Company License otherwise (the export step refuses to render until the basis is recorded).

### Other ways to install

```bash
npx skills add Paldom/storytelling-animation -a codex -a pi   # target specific agents
gh skill install Paldom/storytelling-animation                # GitHub CLI >= 2.90
gh skill install Paldom/storytelling-animation <skill> --pin <tag>
```

```text
/plugin marketplace add Paldom/storytelling-animation
/plugin install storytelling-animation@storytelling-animation
```

## Skills

| Skill | Ask it when | Invoke |
| --- | --- | --- |
| [storytelling-animation](skills/storytelling-animation/) | you have a brief and want the finished animation, every step gated, delivered for LinkedIn, PowerPoint or a custom size | `/storytelling-animation <brief>` |
| [animation-storyboard](skills/animation-storyboard/) | you have a brief or message and need the beats, on-screen text and timing of a short silent animation | `/animation-storyboard <brief>` |
| [vector-asset-sourcing](skills/vector-asset-sourcing/) | you need icons, illustrations or Lottie files for the video and want them licensed, consistent and clean | `/vector-asset-sourcing <what the scenes need>` |
| [vector-scene-layout](skills/vector-scene-layout/) | the storyboard is done and you need the Remotion project, design tokens and static scenes that stay legible on a phone | `/vector-scene-layout` |
| [smooth-motion-choreography](skills/smooth-motion-choreography/) | the scenes exist and need animating, or motion feels jerky, flickers, strobes, or a loop jumps at the seam | `/smooth-motion-choreography` |
| [animation-export-presets](skills/animation-export-presets/) | the animation is done and you need MP4 or GIF files for LinkedIn, PowerPoint, or a custom size, checked against the platform's specs | `/animation-export-presets` |
| [animation-frame-qa](skills/animation-frame-qa/) | a render exists and you want to check it the way a viewer sees it: phone-width stills, safe areas, seams, flashes | `/animation-frame-qa out/linkedin-4x5.mp4` |

## The pipeline

The six single-purpose skills hand artefacts to each other; the orchestrator runs them in order and stops at the first gate that does not pass.

1. **[Required]** Storyboard: brief to `storyboard.json`, a frame-timing contract with reading holds per text card.
2. **[Required]** Assets: one licensed icon pack, a manifest with a license per file, credits written out.
3. **[Required]** Layout: Remotion project, design tokens per target (safe areas, type scale, strokes), one static scene per beat, stills checked at phone width.
4. **[Required]** Motion: frame-driven choreography with easing and spring presets, transitions, loop seams, a flicker linter.
5. **[Required]** Export: one master per composition, one checked deliverable per preset (LinkedIn 4:5, 1:1, 9:16, 16:9; PowerPoint 1080p and 4K; GIF; custom).
6. **[Required]** QA: contact sheet, phone-width stills per beat, safe-area overlays, seam strip, luminance report, decisions recorded before sign-off.
7. **[Optional]** Paste [docs/setup-prompt.md](docs/setup-prompt.md) as a `/goal` to run the whole sequence unattended.

Every preset and every number traces to a source: LinkedIn and Microsoft help pages, ffmpeg and Remotion documentation, BBC and Netflix reading-speed guidance, Material and Carbon motion tokens. The sources live in each skill's `references/`.

## Repository structure

```
skills/                  # distributed skills, one folder per skill (SKILL.md + evals/ + scripts/ + references/)
docs/                    # authoring guide, eval methodology, README standard, deployment, setup prompt
scripts/                 # the gate: validator, eval scorer, self-checks
assets/                  # icon and demo (with its regeneration script)
skills.sh.json           # skills.sh repo-page customization (groupings)
.claude/                 # agentic dev setup: hooks + bundled add-skill / publish-repo skills
.claude-plugin/          # plugin + marketplace manifests (makes this repo installable)
.local/                  # gitignored working area: sources, research, PROMPT.md
```

## Working on this repo with an agent

This repo is agent-native: canonical agent instructions live in
[AGENTS.md](AGENTS.md) (CLAUDE.md imports it), hooks validate and lint every write,
`make check` runs the full gate, and CI enforces the same on every PR. The bundled
`add-skill` skill walks the eval-first authoring workflow in
[docs/skill-authoring.md](docs/skill-authoring.md); the README shape is
[docs/readme-standard.md](docs/readme-standard.md). `make hooks` installs the
commit-time layer. Maintainers drive sessions with their own gitignored
`.local/PROMPT.md`.

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the skill-proposal
process, the authoring workflow, and the PR checklist. Please note the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Support

Questions, ideas, or something not working? Start with [SUPPORT.md](SUPPORT.md) —
bugs and skill proposals have [issue templates](../../issues/new/choose), and
security concerns go through [SECURITY.md](SECURITY.md) (never a public issue).

## License

[MIT](LICENSE) © 2026 Paldom

<!-- attribution:start -->
---

[![Built with skillskit](https://img.shields.io/badge/built%20with-skillskit-F5A623)](https://github.com/Paldom/skillskit)

Scaffolded with [skillskit](https://github.com/Paldom/skillskit) — eval-first Agent
Skills tooling. This line is yours to delete; nothing checks for it.
<!-- attribution:end -->
