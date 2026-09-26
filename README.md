<div align="center">

# SUPER_COMPUTER_AI

**Build your own super AI: one home for your coding agent's superpowers.**

[![CI](https://github.com/ufukyuksel-dev/SUPER_COMPUTER_AI/actions/workflows/ci.yml/badge.svg)](https://github.com/ufukyuksel-dev/SUPER_COMPUTER_AI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Skills](https://img.shields.io/badge/skills-23-22d3ee)
![MCP servers](https://img.shields.io/badge/MCP%20servers-6-a78bfa)
![Agent roles](https://img.shields.io/badge/agent%20roles-5-f472b6)
![Works with](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex-111827)

<img src="docs/assets/promo.gif" alt="SUPER_COMPUTER_AI promo: skills, MCP servers, agent roles and a one-command installer" width="800">

<sub>Full-quality video: [docs/assets/promo.mp4](docs/assets/promo.mp4) · rendered from code by
[tools/promo-video](tools/promo-video/)</sub>

</div>

One repository for everything that makes **Claude Code** and **Codex** more capable: **skills** (workflows the
agent follows), **agent roles**, global **instructions** and **MCP servers** (tools the agent can call). Pick the
capability you need, install it with one command, open a new session and ask.

Nothing secret lives here: credentials stay in `~/.config/super-computer-ai/credentials/` on your machine.

## Why

A coding agent out of the box can read and write code. Give it the right **tools** (MCP servers), **know-how**
(skills), **specialist roles** and **house rules** (instructions), and it can also run your ad campaigns, edit
your videos, test your Android app, browse the web and design, train and evaluate AI systems. This repo collects
those building blocks in one place, keeps them safe to publish, and installs them into Claude Code and Codex with
one reversible command.

```text
you ──► Claude Code / Codex ──► skills (how)      23 workflows: ads, mobile, media, browser, AI engineering
                               ├► MCP servers (do)  Google Ads · Meta · TikTok · Premiere Pro · Android ADB · Jev
                               ├► agent roles       architect · researcher · implementer · evaluator · dataset-curator
                               └► instructions      global rules and skill routing, written into a managed block
```

Real requests it handles once installed:

- *"List my Google Ads campaigns"* → reads the account through the `google-ads` MCP server.
- *"List my Meta ad accounts"* → uses the hosted Meta Ads MCP.
- *"Open a random website with Jev and read the title"* → drives Chrome through the `jev` MCP server.
- *"Design a support-ticket classifier and plan its evaluation"* → `ai-system-design` + specialist skills.

Google Ads writes go through **preview → apply** tool pairs, so the agent shows you the change before it makes it.

## What do you need?

| I want to… | Bundle | Install | You also need |
|---|---|---|---|
| Run **Google Ads** campaigns | `ads` | `python3 scripts/install.py --bundle ads --mcp` | Google Ads developer token + service account, an account config ([google-ads](mcp/servers/google-ads/README.md)) |
| Run **Meta** (Facebook/Instagram) ads | `ads` | same | A Meta System User token file ([meta-ads](mcp/remote/meta-ads/README.md)) |
| Run **TikTok** ads | `ads` | same | A TikTok for Business account; log in once per client ([tiktok-ads](mcp/remote/tiktok-ads/README.md)) |
| Edit video in **Adobe Premiere Pro** | `video-editing` | `python3 scripts/install.py --bundle video-editing --mcp` | Premiere Pro + the MCP Bridge panel ([premiere-pro](mcp/servers/premiere-pro/README.md)) |
| Drive an **Android** device, review mobile UI | `mobile` | `python3 scripts/install.py --bundle mobile --mcp` | JDK 21, `adb`, a device or emulator ([adb](mcp/servers/adb/README.md)) |
| Release apps to **Google Play / App Store**, make store assets | `mobile` | `python3 scripts/install.py --bundle mobile` | Your app repo, Fastlane/signing (see the skills) |
| Let an agent **browse websites** (Jev) | `browser` | `python3 scripts/install.py --bundle browser --mcp` | A TypeSafe API key, Chrome ([jev](mcp/servers/jev/README.md)) |
| Generate **music** with Suno | `media` | `python3 scripts/install.py --bundle media` | A Suno account in Chrome |
| **Design, build and evaluate AI systems** | `ai-engineering` | `python3 scripts/install.py --bundle ai-engineering` | — (14 skills + 5 agent roles) |
| Everything | all | `python3 scripts/install.py --mcp` | the union of the above |

`--bundle` adds to what you already have (repeatable); `--remove-bundle` removes. `--mcp` also registers the
bundle's MCP servers — see [Install](#install) for the one rule that comes with it.

## Install

Requirements: macOS or Linux, Python 3.9+ (the system `python3` is enough — the installer uses only the standard
library), plus whatever the servers you choose need (Node for Premiere, `uv` for Google Ads/Jev, JDK 21 for ADB).

```sh
git clone https://github.com/ufukyuksel-dev/SUPER_COMPUTER_AI.git && cd SUPER_COMPUTER_AI
python3 scripts/install.py --list                  # bundles and what each one installs
python3 scripts/install.py --dry-run --bundle ads  # see the plan, write nothing
python3 scripts/install.py --bundle ads            # skills, roles and instructions
```

**MCP servers (`--mcp`): close Claude Code and Codex first.** Claude Code rewrites its config file all the time, so
the installer registers MCP servers only while every Claude Code / Codex session and IDE extension is closed. Run
it from a plain terminal:

```sh
python3 scripts/install.py --bundle ads --mcp
```

Then open a **new** session. Everything the installer does is journaled: `--check` shows drift,
`--rollback <journal>` undoes a run, `--uninstall` removes only what it installed. Your other MCP servers,
settings and comments in `~/.claude.json` / `~/.codex/config.toml` are kept byte for byte. Details, safety model
and recovery: [docs/installing.md](docs/installing.md).

## Quick start per bundle

Each block: set up credentials → install → new session → an example request.

<details><summary><b>ads</b> — Google Ads, Meta, TikTok</summary>

- **Google Ads** has no default account: describe yours in the private overlay
  `~/.config/super-computer-ai/private/mcp/instances.json` (paths and IDs only — see
  [docs/installing.md](docs/installing.md#mcp-servers---mcp)), with the developer token and service account in the
  directory it points to. Writes are previewed and capped by your config.
- **Meta:** put a System User token in `~/.config/super-computer-ai/credentials/meta-ads/system-user-token.txt`
  (`chmod 600`).
- **TikTok:** nothing to store; after installing run `claude mcp login tiktok-ads` / `codex mcp login tiktok-ads`
  (or `/mcp` inside Claude Code).
- Install: `python3 scripts/install.py --bundle ads --mcp` → new session →
  *"Show last week's spend per campaign in Google Ads and Meta, then suggest one budget change (don't apply it)."*
</details>

<details><summary><b>video-editing</b> — Adobe Premiere Pro</summary>

```sh
cd mcp/servers/premiere-pro && npm ci && npm run build && npm run setup:cep && cd -
python3 scripts/install.py --bundle video-editing --mcp
```
Open Premiere → new session → *"Import ~/Movies/clip.mp4, put it on a new 1080p sequence and add a cross dissolve
between the first two cuts."*
</details>

<details><summary><b>mobile</b> — Android device control, store releases</summary>

```sh
(cd mcp/servers/adb && ./gradlew bootJar)
python3 scripts/install.py --bundle mobile --mcp
```
Connect a device (`adb devices`) → new session → *"Open the settings screen of com.example.app, take a screenshot and
compare it with design/settings.png."*
</details>

<details><summary><b>browser</b> — Jev</summary>

```sh
install -d -m 700 ~/.config/super-computer-ai/credentials/jev
cp mcp/servers/jev/.env.example ~/.config/super-computer-ai/credentials/jev/.env   # fill in TYPESAFE_API_KEY
chmod 600 ~/.config/super-computer-ai/credentials/jev/.env
(cd mcp/servers/jev && uv sync --locked && uv run playwright install chromium)
python3 scripts/install.py --bundle browser --mcp
```
New session → *"With Jev, open wikipedia.org, search for Bosphorus Bridge and tell me when it opened."*
</details>

<details><summary><b>media</b> — Suno music</summary>

`python3 scripts/install.py --bundle media` → sign in to Suno in Chrome → new session →
*"Create a calm 60-second loop for my game's menu and save it to assets/audio."*
</details>

<details><summary><b>ai-engineering</b> — design, build, evaluate AI systems</summary>

`python3 scripts/install.py --bundle ai-engineering` → new session →
*"Design a support-ticket classifier: pick a model, an eval set and a serving plan; stop before training."*
The `ai-system-design` skill plans; specialist skills (research, model selection, RAG, eval, serving, …) and the
`architect` / `researcher` / `implementer` / `evaluator` / `dataset-curator` roles do the rest.
</details>

## Secrets and private project data

| What | Where | Never |
|---|---|---|
| API keys, tokens, service accounts | `~/.config/super-computer-ai/credentials/<server>/` (dir `0700`, files `0600`) | in this repo, in client configs, in the overlay |
| Account IDs, config paths, per-project instances and notes | `~/.config/super-computer-ai/private/` (overlay; not a git repo) | in this repo |
| Runtime state (browser profiles, screenshots, logs, installer journals) | `~/.local/state/super-computer-ai/` | in any checkout |

Each server documents its variables in `.env.example`. CI runs a public-safety validator and gitleaks on every
change. See [SECURITY.md](SECURITY.md).

## Add your own

| Adding | Do this | Then |
|---|---|---|
| A **skill** | `python3 scripts/new_skill.py <name> --category <category> --bundle <bundle> --description "What it does. Use when …"` → edit `skills/<category>/<name>/SKILL.md` | `python3 scripts/skills/validate_skills.py && python3 scripts/install.py` |
| An **agent role** | add `agents/claude/<role>.md` and `agents/codex/<role>.toml`, list it in `agents/manifest.json` (with `bundles`) | `python3 scripts/skills/validate_skills.py && python3 scripts/install.py` |
| A global **instruction** | a Markdown file in `instructions/global/` (first line `<!-- bundles: a, b -->` limits it to bundles) | `python3 scripts/install.py` rewrites the managed block |
| An **MCP server** (your code) | `mcp/servers/<name>/` with README, `.env.example`, tests and lockfile; an entry in `mcp/registry.json` ([fields](mcp/README.md)); a skill that explains how to use it | `python3 -m unittest discover -s tests` (the registry test checks the env contract against your code), then `python3 scripts/install.py --mcp` |
| A **hosted MCP** | `mcp/remote/<name>/` (README + auth helper if needed) and a `registry.json` entry with `auth: oauth` or `headers_helper` | as above |

Names are kebab-case; skill names are unique across categories. Before committing: `python3 scripts/validate.py`
and `python3 scripts/skills/validate_skills.py` (details: [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md)).

## Repository layout

```
instructions/   rules for agents: global/ (every session), pipeline/, projects/
skills/         skills by category: ai-engineering, advertising, mobile, media, browser
agents/         agent roles for Claude (.md) and Codex (.toml)
mcp/            servers/ (our code), remote/ (hosted), registry.json (catalog)
scripts/        install.py, run_mcp.py (MCP launcher), validators, new_skill.py
tools/          helper tools that are neither skills nor MCP servers (e.g. promo-video)
tests/          repository tests (installer, registry, validators)
docs/           installing, migration notes
third_party/    vendored code with its own license
```

## License

MIT — see [LICENSE](LICENSE). Third-party code keeps its own license; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
