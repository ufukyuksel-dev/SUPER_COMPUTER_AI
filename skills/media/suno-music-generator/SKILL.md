---
name: suno-music-generator
description: Create project-specific instrumental music, ambience and sound-effect candidates in Suno through Google Chrome Computer Use, then download and validate the audio in the target project. Use when asked to add, create or download music for a game or project, even when Suno is not named, unless the user requests another source or only existing-asset wiring.
---

# Suno Music Generator

Act as the project’s Suno adapter: inspect the scene → write the description → configure instrumental music and v6 Pro → submit → wait → select and download → validate and place the asset. A request such as “oyuna müzik ekleyelim” authorizes this creation-and-delivery workflow within the budget below; do not stop at writing a prompt or ask for confirmation at every ordinary step. Respect an explicitly different music source.

## Brief and mode

Read the current project's instructions, relevant scene notes and audio conventions. Establish the absolute project root, destination, audio type, mood, energy, listener perspective, desired duration, loop requirement and format. Infer creative details from the scene; ask for missing paths or choices that materially affect delivery. Use [prompt examples](references/prompt-examples.md) when needed. Underwater scenes are examples, not a fixed style.

- **Music bed:** Create → description-based mode, **v6 Pro + Instrumental** by default; current user choices override these defaults. Verify the model menu’s checked v6 Pro entry and instrumental configuration; the collapsed model button may display only v6. Do not confuse v6 Pro with v6-mini or v6-wild Pro. Enable Instrumental when a toggle exists. In the v6 Advanced form, if the UI explicitly says to leave lyrics empty for instrumental and provides no toggle, verify the empty Lyrics field instead and record that UI instruction. Leave lyrics empty and fill Song Description (or Styles in Advanced mode) with the scene, mood, energy, timbres, musical pacing, loop intent, desired length and no-vocals constraint. Keep it suitable for background gameplay rather than inventing lyrics. If the requested model is unavailable, ask before substituting.
- **Ambience or one-shot effect:** choose **Sounds** by default. Record whether model, Instrumental and duration controls exist. If no model selector exists, record “Sounds default”; the music default does not impose v6 on Sounds. Ask about this conflict only if the user explicitly required v6 for the non-music asset.
- If Sounds is missing, explain the limitation and offer description-mode generation with a no-melody/no-vocals prompt. Obtain agreement before using that substitute for a requested nonmusical effect; flag that it may produce music.

Set duration if an actual control exists, using its displayed limits. Otherwise duration in the prompt is a preference. Exact timing and seamless looping require checking the generated file; any necessary edit must be agreed when it changes the requested deliverable.

## Chrome Computer Use

Open `https://suno.com/create` in the user's Chrome session, or reuse the specified Suno tab. Use only the current client's documented browser/UI tools; read [client access](references/client-access.md) for the applicable path. Verify the Suno origin and current account before entering the prompt. A short scene description usually suffices; follow disclosure rules for confidential content or file uploads.

Observe → act → observe. Prefer accessibility targets from the latest state. If page controls are absent or ineffective, use a fresh screenshot and coordinates derived from it; refresh state after acting. Never store coordinates or element IDs as reusable selectors. Follow tool guidance for login and CAPTCHA. If the surface remains unavailable, report the exact blocker and keep the pending task state; do not replace Chrome with private APIs, cookie extraction or network replay.

Before Create, re-read the prompt, mode, model, Instrumental state where present, and duration setting. Do not confuse an instrumental prompt with an enabled instrumental toggle.

## Credits and submission

Read the visible balance and per-submission cost, including the displayed number of outputs; stop if cost exceeds balance or the user's budget. If a value is not exposed, report it as unknown rather than inventing it. With no tighter numeric user limit, an unknown balance permits the initial submission under the default below; report “unknown”.

Absent a tighter user limit, allow **one submission per cue and at most one retry** after reporting why it is needed. Report balance before and after each submission when visible. Extra submissions require an explicit allowance; purchases and upgrades need their own authorization. A normal request to generate audio does not need another confirmation for the initial submission within these limits.

Click Create once, then record the job/song reference, prompt and time. Inspect all candidates from that submission; do not assume it produces a fixed count. For slow or ambiguous completion, reconcile queue/history before retrying. Check status with bounded polling; after about five minutes without completion, report pending and retain the reference. A timeout or lost connection is not evidence that the job failed, and must not trigger a duplicate submission.

## Select, download and deliver

Match candidates to the submitted job. Listen when the available tool supports audio perception: assess scene fit, unwanted vocals, musical content in an ambience request, abrupt changes, and loop seams. Select the best candidate on that evidence; otherwise identify the selection as provisional.

Use the selected track's visible download menu. Choose the required format when offered; inspect restrictions and ask before a format substitution or paid upgrade. Confirm completion and correlate the local file using the download entry, filename and time, rather than choosing an arbitrary latest download.

Keep the original and copy to the project's audio directory with a unique descriptive filename; do not overwrite existing assets. If no audio directory is established, propose one and ask before placement. Run an available media probe on the **destination**, for example:

```sh
ffprobe -v error -show_entries format=duration,format_name:stream=codec_name,sample_rate,channels -of json "/absolute/project/audio/cue.mp3"
```

Check nonzero size, decodable audio, container/codec, channels, sample rate and actual duration against the brief. Probing does not prove byte identity or perceptual quality. If a tool is unavailable, report the missing check. Preserve the original for approved cropping, fades, loop edits or conversion; renaming an extension is not conversion.

For “add music to the game”, complete the documented import and playback wiring within the project's editing rules, then test playback when possible; for a download-only request, stop at the file. Distinguish **file placement**, **engine import** and **runtime playback**. Record provenance in the project's existing convention or an adjacent note using six lines:

```text
Suno: <clean URL/ID; no session tokens>
Prompt: <submitted description>
Model: <observed model or Sounds default; instrumental state if present>
Date: <generation date; credits before/after or unknown; submission count>
Files: <original → destination; edits or none>
Media: <probe summary; listening/loop/import/runtime checks or unverified>
```

For release-rights questions, check current official Suno terms for the account and generation context. Download availability alone does not establish rights.

## Evidence rules

- A click is not a verified state change; a pending job is not completed generation.
- Prompted duration/loopability is not measured duration or an audited seamless loop.
- A waveform, file extension or successful ffprobe is not listening, lossless-source proof or runtime playback.

Finish with the delivered path, selected output and checks actually performed; explicitly identify unresolved stages.
