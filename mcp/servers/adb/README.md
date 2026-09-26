# adb MCP

An MCP server that lets an agent see and drive an Android device or emulator through `adb` (and optionally
`scrcpy`): device info, screenshots, UI hierarchy dumps and element search, taps/swipes/text input, intents,
waits, file push/pull, video recording and mirroring. Kotlin 2.2, Spring Boot 3.5, Spring AI 1.1 MCP server
(stdio by default, SSE profile available), JDK 21. Agent workflow: skill `mobile-ui-review` (bundle `mobile`).

> Imported into SUPER_COMPUTER_AI from the author's `ADB_MCP_SERVER` project (2026-09): source, tests, Gradle
> wrapper and the design spec (`docs/ADB_MCP_Server_MVP_Spec_v3_6.docx`). IDE files, build output, logs and
> captured artifacts were not imported.

## Prerequisites

- JDK 21 (the Gradle toolchain asks for 21).
- Android platform tools (`adb`) on `PATH` or in the Android SDK; a device with USB debugging, or an emulator.
- Optional: `scrcpy` for mirroring, recording and TCP/IP connect.

## Build, test, run

```sh
cd mcp/servers/adb
./gradlew test        # hermetic: no device needed; state goes to build/test-state
./gradlew bootJar     # -> build/libs/adb-mcp-server-0.0.1-SNAPSHOT.jar
java -jar build/libs/adb-mcp-server-0.0.1-SNAPSHOT.jar                 # stdio MCP
java -jar build/libs/adb-mcp-server-0.0.1-SNAPSHOT.jar --spring.profiles.active=sse   # SSE on 127.0.0.1:8080
```

Register it with `python3 scripts/install.py --mcp` (close Claude Code and Codex first; see `docs/installing.md`). By hand instead:

```sh
claude mcp add adb -- java -jar <repo>/mcp/servers/adb/build/libs/adb-mcp-server-0.0.1-SNAPSHOT.jar
```

```toml
# ~/.codex/config.toml
[mcp_servers.adb]
command = "java"
args = ["-jar", "<repo>/mcp/servers/adb/build/libs/adb-mcp-server-0.0.1-SNAPSHOT.jar"]
```

## State — never in the repository or the client's working directory

The server needs no credentials. Everything it writes goes to one private directory:

| What | Where (override) |
|---|---|
| Screenshots, videos, UI dumps, pulled files (`artifacts/`), log (`logs/adb-mcp-server.log`) | `~/.local/state/super-computer-ai/adb` (`ADB_MCP_STATE_DIR`, `-Dadb-mcp.state-dir=` or `--adb-mcp.state-dir=`), mode 0700 |
| Host files `push_file` may read | `<state>/transfers` (`ADB_MCP_TRANSFERS_DIR`) |

The state directory must be absolute (or start with `~/`). Whichever source sets it, it is made private before
logging starts. If any write location (`artifacts.*` including the subdirectories, `scrcpy.recording-dir`,
`logging.file.*`) really resolves outside it — absolute path, `..` or a symlink — start-up stops; move the whole state
directory instead. `scrcpy_start_record`'s optional `outputPath` must also lie inside the artifact directory. Artifacts older than 24 h or beyond 2 GB are removed automatically (`artifacts.*` in `application.yml`).
See `.env.example`.

## Safety switches

`src/main/resources/application.yml` → `security`: dangerous tools (`am_broadcast`, `push_file`,
`scrcpy_connect_tcpip`, `force_stop`) can be disabled one by one; device paths are limited to `/sdcard/` and
`/data/local/tmp/`; an intent allowlist can restrict `am_start`/`am_broadcast`. Override any key with Spring's
usual mechanisms (e.g. `--security.dangerous-tools.push-file.enabled=false`).

## Design

`docs/ADB_MCP_Server_MVP_Spec_v3_6.docx` is the MVP specification the code implements (tool catalogue, error
codes, device resolution, security model).
