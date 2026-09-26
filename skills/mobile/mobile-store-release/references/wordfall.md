# WordFall release integration

Workspace locations are machine-specific and live in the private overlay:
`${SCAI_HOME:-~/.config/super-computer-ai}/private/skills/mobile-store-release/wordfall.md` (the app repository and the separate "WordFall Design System" ASO repository).
If the overlay file is missing, ask for the locations instead of guessing.

If a location moves, resolve the real path; do not create a replacement project silently.

Verified baseline on 2026-09-06: Android package `game.wordfall.app`, production variant `prodRelease`; iOS project `iosApp/iosApp.xcodeproj`, scheme/configuration `WordFall-ProdServer` / `ProdServer`, main bundle `game.wordfall`, extension `game.wordfall.NotificationService`. Both production environments point to `https://game.wordfall.org` and `wss://game.wordfall.org/ws`. Recheck actual files before release.

Android signing already consumes WORDFALL_UPLOAD_KEYSTORE_PATH, WORDFALL_UPLOAD_KEYSTORE_PASSWORD, WORDFALL_UPLOAD_KEY_ALIAS, WORDFALL_UPLOAD_KEY_PASSWORD. Preserve these names. Firebase CI inputs are FIREBASE_ANDROID_CONFIG_BASE64 and FIREBASE_IOS_CONFIG_BASE64; decoded files must match the application identifiers.

Implemented release structure (actual store execution must still be verified): marketing version and development fallback in `iosApp/Version.xcconfig`; beta CI supplies a shared Android/iOS build number BASE + 100×run_number + run_attempt, attempt 1..99. Set BASE above real store inventory; changing/resetting workflow numbering requires a higher BASE. Main successful CI leads to beta; explicit production dispatch selects the exact beta build. Read the actual workflow/Fastfile to establish implementation status.

WordFall store images must come from the ASO repository's current data/i18n/canvas path. Ufuk requests the Turkish GPT Image artwork style across tr/en/de/fr/es, using the corresponding localized gameplay. New modes such as Vurgun follow the same route. Read the `store-listing-assets` WordFall reference for actual sources/exports; never substitute raw mobile screenshots for the agreed polished store assets.

Release metadata target conventions: `fastlane/metadata/android/<play-locale>/`; Apple metadata `fastlane/metadata/ios/<apple-locale>/`, screenshots `fastlane/screenshots/ios/<apple-locale>/`. Confirm the export implementation and store locale inventory before upload. Google Ads exports are not store screenshot inputs.

## Executable release flow

Use the repository's `.ruby-version` (Ruby4.0.1) and Gemfile.lock (Fastlane2.239.0). On this Mac put `/opt/homebrew/opt/ruby/bin` first in PATH; system Ruby cannot run the locked bundle. Hosted workflows use ruby/setup-ruby.

`store-release.yml` uploads beta binaries after successful CI. `store-production.yml` is manual-only: choose exact build_number and platform; dispatch ref selects versioned listing/config, and its latest CI push run must pass. There is no dependency on GitHub binary artifact retention. Android requires a singleton completed internal release with canonical marketing-version label; iOS requires the exact unexpired VALID TestFlight build and marketing version. Never substitute latest.

Production lanes: `android promote`, `ios submit`; read-only candidate lanes: `<platform> inspect_candidate`; local content gate: `validate_listing store:android|ios build_number:<n>`. Android production defaults to draft; Apple review and automatic release default false. Apple metadata-only does not attach/submit the candidate build. Binary upload, review request and public availability are distinct outcomes.

Stage the complete reviewed ASO export under fastlane, retaining export-state.json. Prepare all five locales' metadata. Play notes must be `metadata/android/<locale>/changelogs/<build_number>.txt`; the allowlist permits only the current build's changelog. Remove old working-tree changelog files when preparing the next release; history stays in Git. Apple notes are `metadata/ios/<locale>/release_notes.txt`. The first live promotion must verify in Play Console that notes belong to the production release; source inspection alone is not live proof.

Do not stage review_information, icon replacements or unrelated metadata fields: this batch preserves existing store contacts/icons. Apple review submission requires reviewed `fastlane/submission-information.json`; do not invent privacy/IDFA/compliance answers. Read current store declarations and resolve actual changes with Ufuk. The strict listing allowlist is defined in Fastfile; inspect it when preparing files.
