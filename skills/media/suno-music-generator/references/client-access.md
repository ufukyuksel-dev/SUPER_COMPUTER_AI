# Chrome access by client

Use only tools actually available in the current session. The examples identify entry points, not stable element IDs or a frozen Suno layout. Provider setup/login restrictions belong to that tool's documentation.

## Codex: CUA

With the `mcp__cua_repl.js` surface, follow its first-call contract. For a named Chrome request without a supplied tab:

```javascript
let tab = await cua.createBrowserTab("chrome", "https://suno.com/create", {sessionName: "🎵 Suno"});
```

Read the returned documentation/state before another call. A specifically supplied tab should instead be selected according to the tool's tab-matching rules.

For an existing Suno tab, use `cua.getState()` to find its current browser/tab IDs and select it with `cua.getTab(tabId, {browser: browserId})`. On a connected browser tab, both `getAXState()` + element actions and `getScreenshot()` + coordinate actions are supported. Derive coordinates from that tab’s fresh screenshot, not a native window screenshot with a different size or origin.

When the returned documentation exposes `agent.browsers`, reuse that selected provider and its documented tab handle for `playwright.domSnapshot()` and semantic locators such as `getByRole("tab", {name: "Simple", exact: true})`. Read the actual menu first; v6 Pro may appear as a checked `menuitemradio` while the closed button says v6. Follow session naming and user-tab claiming requirements from that tool’s documentation. Do not assume these extended methods exist on an undocumented CUA wrapper.

If Chrome has no browser provider, inventory with `cua.getState()` and, when the native app is available, select it with `cua.getApp("com.google.Chrome")`. Observe with `getAXState()` or `getScreenshot()`. Use `click`, `setValue`, `paste` or key actions only as documented; get fresh state after actions. Reuse a relevant Suno tab or open a new tab through UI. Native app access is still Chrome; no browser/profile substitution is implied. If native window actions fail but the same signed-in Chrome tab is connected through the browser provider, continue through the tab’s DOM or screenshot controls. Treat a native-window failure separately from browser-tab capability.

## Claude: Playwright MCP, when registered

Confirm the exposed tool schemas and that the provider targets the user's Chrome session. A provider's isolated default browser is not automatically the requested Chrome profile. If this connection is missing, report it rather than silently switching browser/session.

Typical sequence, subject to the installed tool schemas:

1. `browser_navigate` to `https://suno.com/create`.
2. `browser_snapshot` and inspect the current page.
3. `browser_click` with the fresh element reference to choose the mode/model/toggle.
4. `browser_snapshot`; `browser_type` into the identified description field.
5. `browser_snapshot` to verify settings before a single Create click.
6. Use `browser_take_screenshot` when visual context is missing and the documented download workflow for the resulting file.

Re-derive references after navigation or UI changes. Do not invent arguments, mix Playwright references with CUA indices, or use hidden page/network state as a substitute for the visible workflow. Verified by Claude 2026-09-06: navigation and snapshot work; the default provider is not signed in to Suno.
