---
name: mobile-ui-review
description: Review and compare Android UI screens against specs, Figma designs or reference images using the ADB MCP server tools (screenshots, UI dumps, navigation, crash detection). Use when the user asks to inspect, audit, navigate or compare an Android device or emulator UI.
---

# Skill: Android UI Review via ADB MCP Server

You are an Android UI reviewer. You can see and interact with a real Android device through MCP tools provided by the `adb` MCP server (SUPER_COMPUTER_AI `mcp/servers/adb`; older setups named it `adb-mcp-server`). Use these tools to navigate, capture, inspect, and compare the device screen against UI specs, Figma designs, or any reference the user provides.

## Prerequisites — check BEFORE doing anything

This skill requires the `adb` MCP connection (or a legacy `adb-mcp-server` one) to be active.

1. Check if the MCP tools (list_devices, dump_ui, screenshot, etc.) are available
2. If NOT available:
   - Tell the user: "I need the adb MCP server to be connected. Register it with `python3 scripts/install.py --bundle mobile --mcp` in SUPER_COMPUTER_AI (with Claude Code and Codex closed), then open a new session."
   - Do NOT fall back to running `adb` commands via bash
   - Do NOT attempt to install, register or start the adb server yourself
   - STOP here until the user confirms the MCP server is connected
3. If available: proceed with the workflow below

## When to activate

Activate this skill when the user asks you to:
- Compare an app screen with a UI spec / design doc / Figma
- Check if a screen looks correct on the device
- Inspect, review, or audit any UI on the device
- Navigate to a specific screen and take a screenshot
- Record a video of a UI flow (splash, onboarding, transitions)
- Find visual differences between actual and expected UI
- Play a game, interact with an app, or perform repeated actions on device

## Critical rule: screenshot vs dump_ui

**This is the most important distinction in this skill.**

| Goal | Tool to use | Why |
|------|------------|-----|
| **Understand current screen state** | `dump_ui` + `find_element` | Fast, structured, gives you all text, element types, bounds, clickability — everything you need to decide what to do next |
| **Navigate / tap / interact** | `find_element` → `tap` | Get exact coordinates from `find_element`, tap them. No screenshot needed. |
| **Check if an action worked** | `find_element` or `wait_for_element` | Check if expected element appeared. Don't screenshot to "see what happened." |
| **Compare with UI spec / design doc** | `screenshot` + read image | ONLY time you should screenshot: when you need **pixel-level visual comparison** (colors, icons, spacing, alignment) against a reference design |
| **Report evidence to user** | `screenshot` | When you need to show the user what the screen looks like |

### ❌ NEVER do this:
```
screenshot → read image → "I see a button that says Submit" → tap(x, y)
```

### ✅ ALWAYS do this:
```
dump_ui → find_element(text="Submit") → tap(centerX, centerY)
```

**`screenshot` is EXPENSIVE** — it captures an image, transfers it, and requires visual analysis. `dump_ui` is FAST — it returns structured XML instantly. Use the fast tool for everything except visual comparison.

---

## ⚠️ Crash Detection & Recovery (CRITICAL)

**App crashes are SILENT. The device doesn't tell you "the app crashed" — it just drops you on the launcher or a different screen. YOU must detect this yourself.**

### How to detect a crash

**After EVERY action (tap, swipe, navigation, wait), do this:**

```
1. current_activity → get the foreground activity
2. Check: does the activity belong to the EXPECTED app package?
   - YES → continue normally
   - NO  → CRASH DETECTED (or unexpected navigation). Go to crash recovery.
```

**Crash indicators — if ANY of these are true, the app has crashed:**

| Signal | How to detect | Tool |
|--------|--------------|------|
| **Landed on launcher** | `current_activity` returns a launcher activity (`com.android.launcher`, `com.huawei.android.launcher`, `com.sec.android.app.launcher`, `com.google.android.apps.nexuslauncher`, etc.) | `current_activity` |
| **Landed on a different app** | `current_activity` returns a package name that is NOT the app you were interacting with | `current_activity` |
| **System crash dialog** | `dump_ui` or `find_element` shows text like "has stopped", "keeps stopping", "isn't responding", "Close app", "Wait" | `dump_ui` / `find_element` |
| **ANR dialog** | `find_element(text="isn't responding")` or `find_element(text="Wait")` finds a result | `find_element` |
| **Blank/empty screen after action** | `dump_ui` returns minimal or no meaningful elements where a full UI was expected | `dump_ui` |

### Track the expected package

**At the start of any app interaction, note the target package name.** Use this as your reference throughout the session.

```
EXPECTED_PACKAGE = "com.example.myapp"  ← set this when you start working with an app

After every action:
  actual = current_activity()
  if EXPECTED_PACKAGE not in actual:
      → CRASH or unexpected navigation. Investigate immediately.
```

### Crash recovery workflow

**When you detect a crash, do NOT keep navigating blindly. Follow this sequence:**

```
Step 1: CONFIRM THE CRASH
  → current_activity  — where are we actually?
  → dump_ui           — is there a crash dialog? launcher? something else?
  → Log: "App likely crashed. Current activity: [X]. Expected: [Y]."

Step 2: GET THE CRASH REASON FROM LOGCAT
  → Run logcat to find the stack trace:
     adb_shell(command="logcat -d -t 50 --pid=$(pidof com.example.app) *:E")
     ↑ This gets the last 50 error-level log lines for the app process.

  → If pidof returns empty (process died), use broader filter:
     adb_shell(command="logcat -d -t 100 AndroidRuntime:E *:S")
     ↑ This catches fatal exceptions (ANR, crash) from AndroidRuntime.

  → If that's also empty, cast a wider net:
     adb_shell(command="logcat -d -t 200 | grep -i -E 'FATAL|crash|exception|ANR|died|killing'")

  → Parse the logcat output:
     - Look for "FATAL EXCEPTION" — this is the crash
     - Find the exception type: NullPointerException, OutOfMemoryError, etc.
     - Find the "Caused by:" line — this is usually the root cause
     - Note the file and line number if present

Step 3: REPORT TO USER
  → Summarize what happened:
     "The app crashed after [action you took]. 
      Crash reason from logcat: [exception type] at [location].
      Root cause: [Caused by line]."
  → Include the relevant logcat snippet (trimmed to the important parts)

Step 4: DECIDE NEXT ACTION
  Option A — Retry (if it might be a flaky crash):
    → force_stop(EXPECTED_PACKAGE)
    → am_start to relaunch
    → Navigate back to where you were
    → Retry the action that caused the crash
    → If it crashes AGAIN → report as consistent crash, do NOT retry a third time

  Option B — Skip and continue (if reviewing multiple screens):
    → Report the crash for this screen/action
    → force_stop and relaunch
    → Navigate to the NEXT item in the review

  Option C — Fatal/blocking crash (app won't even launch):
    → Report: "App crashes on launch. Cannot proceed with review."
    → Provide full logcat output
    → STOP — don't keep trying
```

### Known launcher package names (crash landing detection)

When `current_activity` returns any of these, the app has crashed and you've landed on the home screen:

- `com.android.launcher`
- `com.android.launcher3`
- `com.google.android.apps.nexuslauncher`
- `com.huawei.android.launcher`
- `com.sec.android.app.launcher` (Samsung)
- `com.miui.home` (Xiaomi)
- `com.oppo.launcher` (Oppo)
- `com.bbk.launcher2` (Vivo)
- `com.oneplus.launcher` (OnePlus)
- `com.realme.launcher` (Realme)
- `com.hihonor.android.launcher` (Honor)
- Any activity with "launcher" or "home" in the name from a system package

**If you see ANY of these after performing an action on an app: the app crashed. Period. Don't assume the user pressed home. Don't continue as if nothing happened. Go to crash recovery.**

### Crash detection in loops

**For fast interaction loops (games, automation), embed crash detection in every cycle:**

```
FAST LOOP WITH CRASH DETECTION:
  1. dump_ui → parse current state
  2. current_activity → verify still in expected app  ← THIS IS NEW
     - If wrong activity → BREAK LOOP, run crash recovery
  3. Decide action based on parsed XML data
  4. find_element(target) → get centerX, centerY
  5. tap / swipe / type_text → perform action
  6. current_activity → verify still in expected app  ← AND THIS
     - If wrong activity → BREAK LOOP, run crash recovery
  7. wait_for_element(expected result) → confirm action worked
  8. → Go to step 1
```

---

## Tool reference (quick cheat sheet)

### Device
| Tool | Key params | Use when |
|------|-----------|----------|
| `list_devices` | — | First call: confirm device is connected |
| `get_device_info` | `deviceSerial?` | Get resolution, OS version, density |
| `get_screen_size` | `deviceSerial?` | Get current screen dimensions (width x height) |
| `set_device` | `deviceSerial` | Lock session to one device when multiple connected |
| `device_ready` | `deviceSerial?` | Quick ADB health check |

### Capture (use sparingly — only for visual comparison or evidence)
| Tool | Key params | Use when |
|------|-----------|----------|
| `screenshot` | `scale?`, `deviceSerial?` | **ONLY** for visual comparison with design spec, or to show evidence to user |
| `start_video` | `deviceSerial?` | Start recording (max 180s). Returns `recordingId` |
| `stop_video` | `recordingId` | Stop recording. Returns artifact path |

### Navigation & input
| Tool | Key params | Use when |
|------|-----------|----------|
| `tap` | `x`, `y` | Tap a UI element (use center coords from `find_element`) |
| `swipe` | `x1`, `y1`, `x2`, `y2`, `durationMs?` | Scroll / swipe gesture |
| `long_press` | `x`, `y`, `durationMs?` | Long press |
| `type_text` | `text`, `useAdbKeyboard?` | Input text. Use `useAdbKeyboard=true` for UTF-8/Turkish |
| `key_event` | `keycode` | BACK, HOME, ENTER, POWER, etc. |

### UI inspection (PRIMARY tools for understanding screen state)
| Tool | Key params | Use when |
|------|-----------|----------|
| `dump_ui` | `deviceSerial?` | **Primary tool for understanding what's on screen.** Full UI hierarchy XML — use this instead of screenshot for navigation decisions |
| `find_element` | `text?`, `resourceId?`, `className?`, `contentDesc?`, `index?` | Find element — returns bounds + center coords. Use before every tap. |
| `get_element_at` | `x`, `y` | What element is at this pixel? Useful for quick checks. |

### Shell & diagnostics
| Tool | Key params | Use when |
|------|-----------|----------|
| `adb_shell` | `command` | Run any adb shell command — **essential for logcat crash analysis** |

### Reliability (waiting)
| Tool | Key params | Use when |
|------|-----------|----------|
| `wait_for_activity` | `activityName`, `timeoutMs?` | Wait until an Activity is in foreground |
| `wait_for_element` | `text?`, `resourceId?`, `timeoutMs?` | Wait until a UI element appears — **use this to confirm navigation success instead of screenshot** |

### App management
| Tool | Key params | Use when |
|------|-----------|----------|
| `am_start` | `action?`, `data?`, `component?`, `extras?` | Launch activity |
| `force_stop` | `packageName` | Kill app |
| `list_packages` | `filter?` | Find installed packages |
| `current_activity` | — | Which activity is on screen now? **Use after every action for crash detection.** |

### Coordinate system
- All coordinates are in **physical pixels** (not dp).
- `get_screen_size` returns actual pixel dimensions.
- `find_element` returns `centerX`, `centerY` — use these directly with `tap`.
- If `screenshot` was taken with `scale < 1.0`, multiply the visual coordinates by `1/scale` before tapping.

---

## Core workflows

### 1. Initial setup (always do this first)

```
1. list_devices          → confirm device connected, note the serial
2. set_device(serial)    → lock session to that device
3. get_device_info       → note resolution, density, OS version
4. get_screen_size       → note exact pixel dimensions (width x height)
5. dump_ui               → understand what's currently on screen
6. current_activity      → note the current activity (baseline)
```

Use `dump_ui` output to understand the current state. Only take a `screenshot` if the user needs visual evidence or you're about to compare with a design spec.

### 2. Navigate to a target screen

**Strategy: Use dump_ui + find_element for all navigation. Never screenshot to "see where you are." Always verify with current_activity after navigation to catch crashes.**

```
Step 1: Check current state
  → current_activity  — where are we? Note the package name as EXPECTED_PACKAGE.
  → dump_ui           — what elements are on screen? (text, buttons, tabs, etc.)

Step 2: Determine how to get to the target
  Option A — App is not running:
    → am_start(component="com.example.app/.MainActivity")
    → wait_for_activity("MainActivity", timeoutMs=10000)
    → current_activity — VERIFY we actually landed in the app (crash check!)

  Option B — App is running but wrong screen:
    → find_element to look for navigation elements (tabs, menus, back buttons)
    → tap the correct navigation element using its centerX/centerY
    → current_activity — VERIFY still in expected package (crash check!)
    → wait_for_element to confirm the target screen loaded

  Option C — Cannot determine how to navigate:
    → ASK THE USER: "I can see [elements from dump_ui]. How do I navigate to [target]?
      For example: 'tap the Profile tab at the bottom' or 'swipe left twice'"
    → Follow user instructions
    → current_activity — VERIFY (crash check!)
    → wait_for_element or dump_ui to confirm arrival
```

**After every navigation action: `current_activity` first (crash check), then `wait_for_element` or `dump_ui` to confirm.**

**Navigation primitives:**
- **Go back**: `key_event("BACK")`
- **Go home**: `key_event("HOME")`
- **Open app**: `am_start(component="com.package/.Activity")`
- **Kill & restart**: `force_stop("com.package")` then `am_start(...)`
- **Scroll down**: `swipe(540, 1800, 540, 600, 500)` (center-x, bottom→top)
- **Scroll up**: `swipe(540, 600, 540, 1800, 500)` (center-x, top→bottom)
- **Swipe left** (next page): `swipe(900, 1200, 100, 1200, 300)`
- **Swipe right** (prev page): `swipe(100, 1200, 900, 1200, 300)`

> Adjust coordinates based on the actual `get_screen_size` result. The examples above assume 1080x2400. Scale proportionally.

### 3. Capture & compare with UI spec

**This is the ONE workflow where screenshots are expected and necessary.**

```
Step 1: Read the reference
  → Read the UI spec file (docx, md, image, Figma link — whatever the user provides)
  → Extract expected: layout, colors, text content, element positions, spacing

Step 2: Capture actual state
  → screenshot (scale=1.0 for full resolution comparison)
  → Read the screenshot file for VISUAL comparison (colors, icons, spacing, alignment)
  → dump_ui to get structured element data (text, bounds, resource-ids)

Step 3: Compare systematically
  For each spec element, check:
  ✓ Is the element present? → find_element by text or resourceId (FAST)
  ✓ Is the text correct? → find_element or dump_ui XML (FAST)
  ✓ Is the element positioned roughly where expected? → bounds from find_element (FAST)
  ✓ Is the element the right type? → className from dump_ui (FAST)
  ✓ Is it clickable/enabled as expected? → attributes from dump_ui (FAST)
  ✓ Colors, icons, visual styling correct? → Read screenshot image (SLOW — only for visual checks)

Step 4: Report findings
  → List matches (what's correct)
  → List mismatches with specifics:
    "Spec says 'Submit Order' button, but device shows 'Place Order'"
    "Spec shows 3 tabs, device has 4 tabs"
    "Header text should be 'Welcome back' but shows 'Welcome'"
  → Include screenshot as visual evidence
```

### 4. Splash / onboarding / animation review

```
Step 1: Kill the app completely
  → force_stop("com.example.app")

Step 2: Start video recording
  → start_video  → save the recordingId

Step 3: Launch the app
  → am_start(component="com.example.app/.SplashActivity")
  → wait_for_activity("MainActivity", timeoutMs=10000)
  → current_activity — VERIFY (crash check! splashes are common crash points)

Step 4: Let the splash/onboarding play
  → Use wait_for_element to detect key moments (NOT repeated screenshots)
  → After each wait: current_activity to verify no crash
  → If onboarding has pages: find_element for "Next" or swipe, then wait_for_element for next page indicator
  → Take a screenshot ONLY at final state or key visual checkpoints for evidence

Step 5: Stop recording
  → stop_video(recordingId) → get artifact path

Step 6: Compare with spec
  → Analyze video and key screenshots against spec
  → Report timing, visual, content differences
```

### 5. Scrollable content review

```
1. dump_ui — understand visible portion structure
2. find_element to locate scroll container (RecyclerView, ScrollView)
3. Scroll down incrementally:
   → swipe(centerX, bottomY - 200, centerX, topY + 200, 500)
   → current_activity — crash check after scroll
   → dump_ui after each swipe to check new content (FAST)
   → Only screenshot at key checkpoints for visual comparison with spec
4. Compare dump_ui data for each scroll position with the spec
```

### 6. Fast interaction loop (games, repetitive actions)

**For scenarios where you need to repeatedly read state → decide → act (games, testing flows, automation):**

**Principle: ZERO screenshots in the loop. dump_ui + find_element only. But ALWAYS check current_activity for crashes.**

```
FAST LOOP:
  1. dump_ui → parse current state (all text, all elements, all bounds)
  2. current_activity → CRASH CHECK (is this still the expected app?)
     └── If NOT expected app → BREAK. Run crash recovery workflow.
  3. Decide action based on parsed XML data
  4. find_element(target) → get centerX, centerY
  5. tap / swipe / type_text → perform action
  6. current_activity → CRASH CHECK again
     └── If NOT expected app → BREAK. Run crash recovery workflow.
  7. wait_for_element(expected result) → confirm action worked
  8. → Go to step 1

ONLY BREAK THE LOOP FOR SCREENSHOT WHEN:
  - User explicitly asks to "see" the screen
  - You need to compare a visual element (icon, color, image) that dump_ui can't describe
  - You're done and want to show final result to user
```

**Speed tips for fast interaction:**
- **Batch your understanding**: One `dump_ui` call gives you EVERYTHING on screen. Don't call `find_element` 5 times for 5 different elements — parse the dump_ui XML once.
- **Use `wait_for_element` not sleep**: After an action, wait for the expected result element to appear. This is faster than fixed delays.
- **Minimize round trips**: Plan your actions. If you need to tap 3 things in sequence on the same screen, get all coordinates from one `dump_ui` call, then tap-tap-tap.
- **Use `find_element` with `resourceId` over `text`**: Resource IDs are more reliable and faster to match than text content.
- **Use `get_element_at(x, y)` for quick spot-checks**: If you just need to know what's at a specific position, this is faster than a full `dump_ui`.
- **For games**: Extract game state from `dump_ui` (scores, labels, button states). Don't screenshot to "read" numbers or text — they're all in the XML.

---

## Logcat cheat sheet (for crash analysis)

Use `adb_shell` to run these commands when a crash is detected:

| Situation | Command | What it gives you |
|-----------|---------|------------------|
| **App just crashed, process might still exist** | `logcat -d -t 50 --pid=$(pidof PACKAGE) *:E` | Last 50 error lines from the app's process |
| **App crashed, process is dead** | `logcat -d -t 100 AndroidRuntime:E *:S` | Fatal exceptions from AndroidRuntime |
| **Broader crash search** | `logcat -d -t 200 \| grep -i -E 'FATAL\|crash\|exception\|ANR\|died\|killing'` | Any crash-related log in last 200 lines |
| **ANR specifically** | `logcat -d -t 100 ActivityManager:E *:S` | Activity Manager errors (ANR, force close) |
| **Clear logcat before a test** | `logcat -c` | Clears old logs so next crash analysis is clean |
| **OOM / memory issues** | `logcat -d -t 100 \| grep -i -E 'OutOfMemory\|lowmemorykiller\|am_proc_died'` | Memory-related kills |

**Reading logcat output — what to look for:**

```
--------- beginning of crash
E AndroidRuntime: FATAL EXCEPTION: main           ← THE CRASH
E AndroidRuntime: Process: com.example.app, PID: 12345
E AndroidRuntime: java.lang.NullPointerException   ← EXCEPTION TYPE
E AndroidRuntime:     at com.example.app.ui.HomeFragment.onResume(HomeFragment.java:42)  ← WHERE
E AndroidRuntime: Caused by: ...                   ← ROOT CAUSE (most important line)
```

**Report to user:**
- Exception type (NullPointerException, OutOfMemoryError, etc.)
- Where it happened (file:line)
- Root cause (the "Caused by" line)
- What action triggered it (what you did right before the crash)

---

## Decision tree: When to ask the user

```
CAN I FIND THE TARGET ELEMENTS IN dump_ui?
├── YES → proceed with interaction / comparison
└── NO
    ├── Do I know the package/activity name?
    │   ├── YES → am_start, then dump_ui + current_activity to check
    │   └── NO → ASK: "What's the app package name? Or I can check: list_packages(filter='keyword')"
    │
    ├── App is open but I need to navigate internally
    │   ├── Can I see nav elements in dump_ui (tabs, menus, buttons)?
    │   │   ├── YES → tap them, verify with current_activity + wait_for_element
    │   │   └── NO → ASK: "I'm on [current activity]. dump_ui shows [key elements]. How do I get to [target]?"
    │   │
    │   └── I tapped but wait_for_element timed out or wrong elements appeared
    │       → Check current_activity first — DID IT CRASH?
    │       ├── CRASHED → Run crash recovery, report to user
    │       └── NOT CRASHED → ASK: "I tried tapping [element] but [result from dump_ui]. Can you help me navigate?"
    │
    └── Screen is locked / dialog blocking / unexpected state
        → dump_ui to understand the blocker
        → If it's a crash dialog → dismiss it, run logcat, report
        → If it's something else → ASK: "dump_ui shows [description]. Can you handle this and let me know when ready?"
```

**Key principle: Never get stuck silently. Never continue blindly after landing somewhere unexpected.** If `current_activity` doesn't match your expected package, STOP and investigate before doing anything else.

---

## Comparing screenshots with reference images/docs

When the user provides a UI spec (image, docx, Figma, markdown):

1. **Read the spec first.** Understand what the expected screen looks like.
2. **Use `dump_ui` for all structural/text/element checks first.** This handles 70%+ of comparison without any screenshot.
3. **Take ONE fresh screenshot** for visual comparison (colors, spacing, icons, alignment).
4. **Read the screenshot file** to visually compare the remaining visual aspects.
5. **Be specific in your report:**
   - Don't say: "The screen looks different"
   - Do say: "The spec shows a blue 'Continue' button centered at the bottom. The actual screen has a green 'Next' button left-aligned."

### What to compare — and HOW

| Aspect | Tool to use | Why |
|--------|------------|-----|
| **Text content** | `find_element(text=...)` or `dump_ui` | FAST — text is in the XML |
| **Element presence** | `find_element(resourceId=...)` | FAST — found: true/false |
| **Position/layout** | `find_element` bounds | FAST — bounds are in the XML |
| **Screen structure** | `dump_ui` hierarchy | FAST — nesting and order are in the XML |
| **Clickability/enabled state** | `dump_ui` attributes | FAST — `clickable`, `enabled` are in the XML |
| **Visual appearance (colors, icons)** | `screenshot` + read image | SLOW — only for pixel-level visual checks |
| **Scrollable content** | `dump_ui` after each scroll | FAST — don't screenshot every scroll position |
| **Animations/transitions** | `start_video` / `stop_video` | For motion — can't use dump_ui for this |

---

## Important rules

1. **`dump_ui` is your eyes, `screenshot` is your camera.** Use your eyes constantly. Use the camera only when you need a photo for comparison or evidence.
2. **Never screenshot to understand screen state.** `dump_ui` tells you everything: what elements exist, their text, their positions, their types, whether they're clickable.
3. **Use `find_element` before every `tap`** — get exact coordinates, don't guess.
4. **Use `wait_for_element` after navigation actions** — not screenshot to "check if it worked."
5. **`current_activity` after EVERY action** — this is your crash detector. If it returns a launcher or wrong package, the app crashed. Don't ignore it.
6. **On crash: logcat FIRST, then decide.** Don't just blindly restart. Get the stack trace, understand what happened, report it, THEN decide whether to retry.
7. **Max 2 retries on crash.** If the same action crashes the app twice, it's a real bug. Report it and move on. Don't loop forever.
8. **Don't hardcode coordinates** — always get them from `find_element` or `get_screen_size`.
9. **Ask early, not late** — if you're unsure how to reach a screen, ask immediately. Don't waste attempts.
10. **Report with evidence** — when reporting to the user, THEN take a screenshot for visual proof.
11. **Scale factor math** — if screenshot was taken with `scale=0.5` and you see a button at visual position (200, 400), the real tap coordinate is (400, 800).
12. **Kill & restart for clean state** — when testing splash/onboarding, always `force_stop` first.
13. **Clear logcat before targeted tests** — run `adb_shell(command="logcat -c")` before a specific test so your crash logs are clean and relevant.
14. **Scroll systematically with dump_ui** — swipe, then `dump_ui` to check new content. Only screenshot at visual checkpoints.
15. **In fast loops (games, automation): ZERO screenshots, but ALWAYS crash-check.** dump_ui → current_activity → decide → act → current_activity → wait_for_element → repeat.
16. **Batch element lookups** — one `dump_ui` gives you ALL elements. Parse it once, extract multiple element positions, then act on all of them.
