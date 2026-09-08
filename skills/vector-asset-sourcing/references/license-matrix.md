# License matrix for icons, illustrations and fonts in rendered video

Checked 2026-09-08 on each vendor's own page. "Video" means a rendered MP4/GIF
published commercially (LinkedIn post, client deck). The license lives on the
individual file, not the site's homepage: record it per file in the manifest.

## Open icon sets (no attribution, commercial OK)

| Set | License | Grid / stroke | Notes |
| --- | --- | --- | --- |
| Lucide | ISC | 24 px, 2 px stroke, round caps | Feather successor; releases every few days, pin the version |
| Tabler Icons | MIT | 24 px, 2 px | 5,000+ outline + filled |
| Phosphor | MIT | 256-unit viewBox (24-grid design), 6 weights | pick one weight and stay on it |
| Heroicons | MIT | 24 outline (1.5 px) / 24 solid / 20 mini | Tailwind team |
| Iconoir | MIT | 24 px, 1.5 px | |
| Remix Icon | Apache-2.0 | 24 px | |
| Material Symbols | Apache-2.0 | 960-unit viewBox, variable | |
| Simple Icons | CC0-1.0 | brand logos | trademarks still belong to the brands |
| Eva Icons | MIT | 24 px | last update 2023 |
| line-md | MIT | 24 px, animated | ships per-frame SVGs (`svg-frames-120fps`) for offline renderers |
| useAnimations | MIT | 32 px, SVG + Lottie | ~90 animated icons |

Sources: lucide.dev/license, github.com/tabler/tabler-icons, github.com/phosphor-icons,
github.com/tailwindlabs/heroicons, iconoir.com, remixicon.com, fonts.google.com/icons,
simpleicons.org, github.com/cyberalien/line-md, github.com/useAnimations/react-useanimations.

## Illustrations and animated packs

| Source | Free tier | Video use | Record as |
| --- | --- | --- | --- |
| unDraw | all free | commercial OK, no attribution, no redistribution of the pack | `unDraw` |
| Storyset (Freepik) | free with attribution | credit "Storyset" visibly; Premium removes it | `Attribution-Free-Tier` + credit line, or `Paid-License` |
| Flaticon | free with attribution link | credit required; Premium removes | same |
| Icons8 | free with a visible link back | credit required; paid removes; free SVG exports are limited | same |
| Lordicon | ~9,000 free icons, attribution required | PRO ($8/mo annual) removes attribution; exports Lottie, GIF, MP4, SVG | same |
| LottieFiles public animations | Lottie Simple License | commercial, no attribution; marketplace files carry their own paid terms, filter to Free | `Lottie-Simple-License` |
| IconScout | "Free Commercial License" filter | check per pack; Lottie/dotLottie/GIF/MP4 exports | per pack |
| Rive Marketplace | CC BY 4.0 | attribution; production `.riv` export needs a paid Rive plan | `CC-BY-4.0` |
| Envato Elements / Creative Market | subscription or per-item | commercial tiers differ (Personal / Commercial / Extended); keep the receipt | `Paid-License` + `license_ref` |

Sources: undraw.co/license, storyset.com/terms, flaticon.com/legal, icons8.com/license,
lordicon.com/pricing, lottiefiles.com/page/license, iconscout.com/licenses,
rive.app/marketplace, elements.envato.com/license-terms, creativemarket.com/licenses.

## Traps

- **NC / ND / GPL / personal-use**: `CC-BY-NC-*` (some animated-effect packs, research
  datasets), `CC-BY-ND`, GPL icon sets, "free for personal use". The checker excludes them
  as a policy default for client work; whether a given use would be lawful is a separate
  question the checker does not answer.
- **Aggregators**: community reports describe aggregator sites (SVGRepo, the Noun Project)
  listing a different license than the original author's. Treat an aggregator label as a
  pointer and follow the source link before recording a license.
- **"Free" landing pages**: Flaticon, Storyset, Icons8 and Lordicon free tiers all require
  a visible credit; a subscription that lapses can strip rights to re-download, so keep the files
  and the receipt.
- **Brand logos** (Simple Icons, company marks): CC0 covers the drawing, not the trademark.
  Use only your own or your client's marks.
- **AI-generated icons**: provenance and copyrightability are contested; do not mix them with
  a licensed set in client work without the client's written OK.
- **Warez re-uploads** of paid After Effects packs exist; a "free download" of a Videohive pack
  is not a license.

## Fonts

Most Google Fonts are OFL-1.1, some are Apache-2.0 or Ubuntu Font License: check the
family page. All three allow embedding in video without a credit. Adobe Fonts and
foundry fonts need the license that came with them. Record every family in the
manifest's `fonts` list. `@remotion/google-fonts` fetches from Google at render time
(network needed); for offline or reproducible renders copy the `.ttf`/`.woff2` into
`public/fonts/`, record it as the font's `file`, and load it with `@remotion/fonts`.

## Supply chain

`@lottiefiles/lottie-player` 2.0.5–2.0.7 were published with wallet-draining code on
2024-10-30 after a maintainer token was phished; sites that resolved an unpinned CDN
build during the incident served it (wiz.io/blog/lottie-player-supply-chain-attack).
Use exact, reviewed versions with a lockfile (pinning alone is not a review), and copy
SVG/Lottie files into `public/` instead of loading anything at render time.
