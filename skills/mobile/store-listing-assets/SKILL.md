---
name: store-listing-assets
description: Create localized app-store descriptions and polished screenshot artwork from real gameplay and an existing ASO design system, using GPT Image for raster artwork and the project's export pipeline for Google Play and App Store formats. Use for new modes, listing refreshes, and multilingual store visuals.
---

# Store listing assets

## Establish the source

Use the user's existing ASO/design system as the canonical composition and export source. Inspect its actual locale definitions, art files, gameplay sources, slide ordering, renderer and export controls. An old README's product claims or an export page's filename do not establish current behavior.
<!-- private:start -->
For WordFall read [the project reference](references/wordfall.md).
<!-- private:end -->

Compare the requested listing against the real app. Capture real gameplay in each target language and appropriate device family. Preserve the successful reference artwork; new modes should use its existing composition style and slide mechanism. Do not create a parallel design system.

## GPT Image workflow

Use the client's available image generation/editing capability and its applicable skill instructions: Codex uses built-in image_gen by default; Claude can use an image-generation MCP tool if one is registered. Check the actual session capabilities rather than assuming either tool exists. Do not switch to paid API/CLI batching without the user's selection of that path. When generation is unavailable, state the missing capability; do not substitute static output and call it equivalent quality.

For each localized artwork, inspect the reference images first and identify their roles:

1. Approved artwork: composition, brand palette, mascot identity and visual quality reference.
2. Real localized gameplay: accurate screen content, tiles, scores, labels and UI reference.
3. Exact target-language headline/copy: spelling, accents and capitalization to preserve.

Generate/edit one intended asset per request with explicit invariants. Preserve the approved style across languages; do not leave Turkish gameplay inside a supposedly localized image. New imagery may enhance the marketing composition but must not misrepresent gameplay or invent features. If generated UI or text is distorted, reject or revise it; do not silently accept it.

Inspect every selected output at readable resolution. Check localized text, UI fidelity, mascot identity, cropping, device framing, contrast and readability at store thumbnail size. Save selected images into the ASO project's asset source with language/slide identity; do not leave them only in the image tool's storage. Keep a compact provenance record with source gameplay, style reference, exact prompt, locale and final file.

## Export and review

Export through the established renderer at exact store dimensions. Adapting layout/resolution through that renderer is distinct from asking GPT Image to produce every device size independently. Missing image/font loading must fail export rather than quietly produce an incomplete PNG.

Maintain a locale × store × device × slide inventory. Validate pixel dimensions, format, alpha restrictions, order and locale mapping against current official requirements. Do not confuse Google Ads graphics with Play feature graphics or screenshots. Recheck both previews and the actual exported files, including tablet crops.

Prepare localized descriptions, subtitles/short descriptions, keywords and release notes based on current product behavior. Do not reuse unsupported numerical or popularity claims from old artwork. Preserve existing store locales and unrelated fields.

Hand off the validated exports to the repository's Fastlane directories together with an exact inventory. This skill prepares assets; it does not itself imply a binary upload or public release. Respect authorization already provided for listing updates.

Use [Apple screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/) and [Google Play preview assets](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en) for current format requirements.
