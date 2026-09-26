---
name: mobile-store-release
description: Prepare and run Android Google Play and iOS App Store releases using an existing mobile repository, Fastlane, signing credentials, and CI. Use for store uploads, beta distribution, release automation, and publishing updated listings; not for backend deployment.
---

# Mobile store release

Treat build, upload, review submission, and public availability as separate states. A successful command is not evidence that the app is publicly available.

## Discover the actual release contract

Read the repository's Fastfile, Gemfile/lockfile, workflows, Android variants and signing configuration, Xcode shared schemes/configurations, and version sources before choosing commands. Reuse the existing setup; do not initialize over it. An API upload key is not an app signing key. iOS extensions need matching versions, entitlements, and distribution provisioning as well as the main app.

For WordFall, read [the project reference](references/wordfall.md). Its ASO source is a separate design repository; do not invent an independent screenshot pipeline.

Resolve app identifiers and current store state through read-only access. Inspect credential presence and names without printing private keys, passwords, JSON credentials or encoded values. Existing local version numbers are not proof of the highest store build. Preserve user authorization from the conversation; ask only for an actual missing decision, credential access, or required declaration.

## Build and distribute

- Run the pinned Ruby/Bundler and `bundle exec fastlane`; validate actual lane names with `lanes` before invoking them. Do not claim a planned lane exists.
- Select the production Android variant and iOS scheme explicitly, including for production-backed beta builds. Never upload a local/test backend build as production.
- Use the repository's monotonic build numbering contract. Store track queries may omit drafts or processing builds; they are not a reliable reservation mechanism. Retries and concurrent jobs must not reuse a consumed number.
- Verify the actual AAB/IPA identifiers, version, signing and environment. For iOS inspect the embedded extension too. Keep signing material outside version control and remove transient CI keychains/files even on failure. Do not revoke certificates as a routine repair.
- Upload beta first when that is the agreed release flow. Record commit SHA, marketing version, build number, artifact and destination. Verify the exact build in Play internal/TestFlight.
- For production, promote/select that exact validated build. Do not silently select the latest build or rebuild a different binary. Report Android and iOS results independently; rerun only the intended platform/action.

## Listing and submission

Use the existing ASO export process, or `store-listing-assets` if available, for new/changed visual assets. A metadata-only request must not rebuild or upload a binary. Read the existing listing first and show the concrete changed fields and assets before applying changes when review is needed.

Check the current Apple/Google submission requirements against the actual app and existing declarations. Do not infer IDFA purposes or privacy answers merely from SDK dependency names. Inspect consent/ATT/SDK initialization and ask for business facts that cannot be established from code or account state. Preserve unrelated locales and listing fields.

Keep review submission and automatic release flags explicit. Review delays are not failed uploads. If access is blocked, finish available local checks and report the exact unresolved external step; do not equate offline validation with store acceptance.

## Evidence

Report changed files, tests actually run, CI run URL, exact store build IDs and current status. Separate setup completed, binary uploaded, waiting for review, and publicly released. Never claim a pipeline is operational based only on a skill file or YAML syntax check.

Current action details: [Play upload](https://docs.fastlane.tools/actions/upload_to_play_store/), [Apple delivery](https://docs.fastlane.tools/actions/upload_to_app_store/), [ASC API authentication](https://docs.fastlane.tools/app-store-connect-api/). Open the relevant official page when relying on behavior that could have changed.
