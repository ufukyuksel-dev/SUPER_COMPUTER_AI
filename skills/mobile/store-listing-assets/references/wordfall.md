# WordFall ASO source and delivery

Canonical artwork/export project: the "WordFall Design System" ASO repository. Consumer: the WordFall app repository.
Their machine-specific locations live in the private overlay: `${SCAI_HOME:-~/.config/super-computer-ai}/private/skills/store-listing-assets/wordfall.md`.
If the overlay file is missing, ask for the locations instead of guessing.

## Verified source inventory (2026-09-06)

- `aso/i18n.jsx`: tr, en, de, fr, es and localized slide text.
- `aso/data.jsx`: slide data, `TR_STORE_SLIDES`, `TR_FEATURE_SLIDE`.
- `aso/assets/store/tr_1.png` through `tr_5.png`, `tr_feature.png`: Ufuk's approved Turkish GPT Image artwork references. Inspect the actual bitmap before matching it.
- `aso/assets/gameplay/`: existing gameplay images, with `_en`, `_de`, `_fr`, `_es` suffixes for localized modes; unsuffixed files are Turkish sources in the current structure. Verify the actual image's language before use.
- `aso/app.jsx`: current UI, asset preload, locale-dependent slide selection, format matrix and ZIP export.
- `aso/canvas-render.jsx`: actual canvas rendering; `aso/slides.jsx`: DOM preview.

The first Turkish bitmap was visually inspected: deep purple/blue luminous backdrop, gold rim lighting, large lime/white headline, layered real gameplay panels, glossy letter tiles and the Wiffle mascot. This user-approved ASO reference takes precedence over the older general README's prohibition on purple gradients/background imagery. Preserve the relevant ASO style instead of applying obsolete general UI guidance to marketing artwork.

At initial inspection only Turkish selects the ready-made artwork; other languages use static translated layouts. Ufuk explicitly requested GPT Image quality for **all five languages**, using their real gameplay with the Turkish set as the style reference. Preserve the good Turkish artwork; add/update content as needed. Vurgun was absent from the initial ASO mode/data search and needs current localized gameplay captures and an artwork entry through the existing slide path.

`aso/export.html` now uses shared data/i18n/store-config/canvas sources. `store-config.js` owns dimensions, localized gameplay manifest and slide selection for both GUI and export. Old README mode counts/popularity claims remain unverified; use current app facts.

From the ASO repository run `npm ci`, `npx playwright install chromium`, then `npm run export:store -- --lang all --output <empty-output-directory>`. A single-language mechanics check uses `--lang tr`. The exporter requires registered GPT Image artwork for requested locales and fails on static fallbacks. Register visually verified artwork in ASO_STORE_ART/ASO_FEATURE_ART in data.jsx. Output contains Fastlane-relative paths and export-state.json; copy the complete reviewed set under the app's fastlane directory. Do not copy partial or failed exports.

Every format is encoded as RGB PNG without an alpha channel (pngjs colorType2); opaque RGBA is insufficient for Apple. Inventory records alpha:false. Google Ads is excluded. Font/image failures and nonempty output destinations are errors. The tested Turkish mechanics sample does not establish content readiness: current tr_1 contains malformed small gameplay text; repair it using current real screenshots before submission. Check mode labels and feature/icon consistency as part of visual review.

## Format and locale contract

| ASO dimension | Pixels | Store destination |
|---|---|---|
| gp | 1080×1920 | Play phoneScreenshots |
| gp7 | 1200×1920 | Play sevenInchScreenshots |
| gp10 | 1600×2560 | Play tenInchScreenshots |
| feat | 1024×500 | Play featureGraphic.png |
| ios | 1284×2778 | Apple iPhone 6.5-inch slot |
| ipad | 2064×2752 | Apple iPad 13-inch slot |
| gads | 1064×557 | Advertising only; exclude from store upload |

The shared ios label now says6.5inches; store classification follows actual dimensions and Apple's current table. Verify specs again at release, rather than trusting the label.

| ASO locale | Apple locale | Play locale |
|---|---|---|
| tr | tr | tr-TR |
| en | en-US | en-US |
| de | de-DE | de-DE |
| fr | fr-FR | fr-FR |
| es | es-ES | es-ES |

Reconcile these proposed region mappings with the existing live listing before writing fields. Deliver Play PNGs to `fastlane/metadata/android/<locale>/images/<screenshot-type>/` and `images/featureGraphic.png`. Deliver Apple PNGs to `fastlane/screenshots/ios/<locale>/` with device/slot and ordered slide names. Preserve the source art in Design System; Fastlane receives derived exports.

The user's scope includes both stores' phone and tablet sets in all five languages. Do not reduce that scope to Turkish, phone-only, or static translations. Do not independently generate a whole new composition for each device: reuse the existing ASO renderer and validate its exported crop/fit.
