# MCAddonCompanion PyWebView Frontend — Design Spec

**Date:** 2026-05-17  
**Status:** Approved  
**Replaces:** CustomTkinter UI (Plans 1 & 2)

---

## Goal

Replace the CustomTkinter UI layer with a PyWebView window backed by a Vue 3 SPA. All Python backend logic is preserved unchanged. The HTML/CSS/JS frontend matches the Claude Design prototype exactly and is forward-compatible with a future Tauri migration.

---

## Architecture

```
main.py                  — PyWebView window creation, Api class, headless CLI paths
frontend/
  index.html             — SPA shell: nav + router outlet + footer
  style.css              — CSS custom properties (design tokens) + utility layer
  app.js                 — Vue 3 app, routing, progress event handler
  vue.esm-browser.js     — Vue 3 bundled locally (no CDN)
  pages/
    home.js              — Home page component
    schematic_sync.js    — Schematic Sync page component
    instance_sync.js     — Instance Sync page component
    pack_registry.js     — Pack Registry page component (Repos/Publish/Browse tabs)
core/                    — unchanged (state, gitlab, prism, sharing, updater, progress)
modules/                 — sync logic preserved; page.py files become unused (can be deleted later)
```

### Key decisions

- **SPA routing:** Vue reactive `page` ref controls which component is mounted. No URL routing needed.
- **Python↔JS bridge:** `window.pywebview.api.method()` returns a Promise. All methods return JSON-serializable dicts/lists.
- **Progress streaming (hybrid):** Long-running ops (sync, publish) emit events via `window.evaluate_js('window.__onProgress(event)')`. Vue subscribes on mount.
- **No build toolchain:** Vue 3 loaded as a local ESM file. PyInstaller bundles `frontend/` as a data directory.

---

## Design Tokens (CSS custom properties)

```css
:root {
  /* Backgrounds */
  --bg-0: #14141c;
  --bg-1: #1a1a26;
  --bg-2: #20212f;
  --bg-3: #272938;
  --line: #2c2e3e;
  --line-strong: #383b50;

  /* Text */
  --text-0: #ebecf2;
  --text-1: #b6b8c7;
  --text-2: #80839a;
  --text-3: #5b5e74;

  /* Accent */
  --accent: #8a5cf6;
  --accent-hi: #9d77f7;
  --accent-soft: #1e1535;

  /* Status */
  --ok: #6fae8a;       --ok-soft: #1a2e25;
  --warn: #c9a25b;     --warn-soft: #2e2415;
  --err: #c97070;      --err-soft: #2e1a1a;
  --run: #8a7fc9;      --run-soft: #1e1c35;
  --off: #5b5e74;

  /* Radius */
  --r-card: 10px;
  --r-btn: 4px;
  --r-input: 4px;

  /* Spacing (8-pt grid) */
  --pad-page-x: 28px;
  --pad-page-y: 24px;
  --pad-card: 16px;
  --gap-card: 16px;
  --gap-section: 20px;
  --top-bar-h: 48px;
  --footer-h: 28px;

  /* Typography */
  --font-ui: "Segoe UI", "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", "Consolas", monospace;
}
```

### Utility classes

```css
/* Layout */
.flex          { display: flex; }
.flex-col      { display: flex; flex-direction: column; }
.items-center  { align-items: center; }
.justify-between { justify-content: space-between; }
.gap-sm        { gap: 8px; }
.gap-md        { gap: var(--gap-card); }
.gap-lg        { gap: var(--gap-section); }
.fill          { flex: 1 1 0; min-width: 0; }
.scroll-y      { overflow-y: auto; }

/* Cards */
.card {
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: var(--r-card);
  padding: var(--pad-card);
}

/* Typography */
.kicker {
  font-size: 9px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--text-2);
}
.h1    { font-size: 18px; font-weight: 700; color: var(--text-0); }
.body  { font-size: 10px; color: var(--text-1); }
.mono  { font-family: var(--font-mono); font-size: 9px; color: var(--text-2); }

/* Buttons */
.btn-primary {
  background: var(--accent); color: #fff;
  border: none; border-radius: var(--r-btn);
  padding: 6px 14px; font-size: 10px; font-weight: 700; cursor: pointer;
}
.btn-primary:hover { background: var(--accent-hi); }
.btn-ghost {
  background: transparent; color: var(--text-0);
  border: 1px solid var(--line); border-radius: var(--r-btn);
  padding: 6px 14px; font-size: 10px; font-weight: 700; cursor: pointer;
}
.btn-ghost:hover { background: var(--bg-2); }

/* Inputs */
.input {
  background: var(--bg-0); color: var(--text-0);
  border: 1px solid var(--line); border-radius: var(--r-input);
  padding: 6px 10px; font-size: 9px; width: 100%; box-sizing: border-box;
}
.input:focus { outline: none; border-color: var(--accent); }
```

---

## Python Api Class

Lives in `main.py`. All methods are synchronous from Python's perspective; PyWebView wraps them as Promises in JS.

```python
class Api:
    def __init__(self, window_ref: list):
        self._win = window_ref  # [webview.Window] — set after window creation

    def _emit(self, event: dict) -> None:
        """Push a progress event to the frontend."""
        import json
        if self._win[0]:
            self._win[0].evaluate_js(f"window.__onProgress({json.dumps(event)})")

    # ── Home ──────────────────────────────────────────────────────────
    def get_home_data(self) -> dict:
        """Returns sync overview for all configured instances."""

    # ── Schematic Sync ────────────────────────────────────────────────
    def get_schematic_data(self) -> dict:
        """Returns instances list + autosync_instances."""
    def set_autosync(self, name: str, enabled: bool) -> None:
        """Toggle autosync for one instance."""
    def run_schematic_sync(self, name: str) -> None:
        """Triggers sync in a thread, emits progress events."""

    # ── Instance Sync ─────────────────────────────────────────────────
    def get_instance_sync_data(self) -> dict:
        """Returns is_configured, defaults, sync_path, instances list."""
    def set_instance_default(self, key: str, value: bool) -> None:
    def set_instance_override(self, name: str, key: str, value: bool) -> None:

    # ── Pack Registry ─────────────────────────────────────────────────
    def get_repos(self) -> list:
    def save_repo(self, repo: dict) -> dict:
        """Resolves project_id from URL+PAT, persists, returns saved repo."""
    def delete_repo(self, repo_id: str) -> None:
    def get_packs(self, repo_id: str) -> list:
    def get_versions(self, repo_id: str, pack_name: str) -> list:
    def publish_pack(self, params: dict) -> None:
        """Builds zip + uploads, emits progress events."""
    def install_pack(self, params: dict) -> None:

    # ── Updater ───────────────────────────────────────────────────────
    def check_update(self) -> dict | None:
    def dismiss_update(self) -> None:
```

### Progress event format

```json
// Step update
{"type": "step", "step": 0, "state": "running", "detail": ""}
{"type": "step", "step": 0, "state": "ok", "detail": "142 MB"}
{"type": "step", "step": 0, "state": "error", "detail": "timeout"}

// Summary
{"type": "summary", "text": "Published v20260517.", "tone": "ok"}

// Reset
{"type": "reset"}
```

---

## Frontend Components

### `index.html` shell

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MCAddonCompanion</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="app"></div>
  <script type="module" src="app.js"></script>
</body>
</html>
```

### `app.js` — Vue root

```js
import { createApp, ref, provide } from './vue.esm-browser.js'
import HomePage from './pages/home.js'
import SchematicSyncPage from './pages/schematic_sync.js'
import InstanceSyncPage from './pages/instance_sync.js'
import PackRegistryPage from './pages/pack_registry.js'

const PAGES = {
  home: HomePage,
  schematic_sync: SchematicSyncPage,
  instance_sync: InstanceSyncPage,
  pack_registry: PackRegistryPage,
}

const NAV = [
  { key: 'home',           label: 'Home' },
  { key: 'schematic_sync', label: 'Schematic Sync' },
  { key: 'instance_sync',  label: 'Instance Sync' },
  { key: 'pack_registry',  label: 'Pack Registry' },
]

createApp({
  components: PAGES,
  setup() {
    const page = ref('home')
    const progress = ref({})     // keyed by context string
    const updateInfo = ref(null)

    // Global progress handler — Python calls window.__onProgress(event)
    window.__onProgress = (event) => {
      if (event.type === 'reset') { progress.value = {}; return }
      progress.value = { ...progress.value, ...event }
    }

    // Check for update on load
    window.addEventListener('pywebviewready', async () => {
      const info = await window.pywebview.api.check_update()
      if (info) updateInfo.value = info
    })

    return { page, progress, updateInfo, NAV, PAGES }
  },
  template: `
    <div class="app-shell">
      <header class="top-bar">
        <div class="top-bar-left">
          <div class="logo-box">M</div>
          <span class="app-name">MCAddonCompanion</span>
        </div>
        <nav class="top-bar-nav">
          <button v-for="n in NAV" :key="n.key"
            class="nav-btn" :class="{ active: page === n.key }"
            @click="page = n.key">{{ n.label }}</button>
        </nav>
        <div class="top-bar-right">
          <span v-if="updateInfo" class="update-badge" @click="page = 'settings'">
            Update available
          </span>
          <span class="version">v{{ version }}</span>
        </div>
      </header>

      <main class="content">
        <component :is="PAGES[page]" :progress="progress" />
      </main>

      <footer class="footer">
        MCAddonCompanion · © 2026 Comsicare
      </footer>
    </div>
  `
}).mount('#app')
```

### Page component pattern

Each page in `pages/*.js` follows this structure:

```js
import { ref, onMounted } from '../vue.esm-browser.js'

export default {
  props: ['progress'],
  setup(props) {
    const data = ref(null)
    const loading = ref(true)

    onMounted(async () => {
      data.value = await window.pywebview.api.get_page_data()
      loading.value = false
    })

    return { data, loading }
  },
  template: `<!-- page HTML -->`
}
```

---

## Top Bar Design

```
┌─────────────────────────────────────────────────────────────────┐
│ [M]  MCAddonCompanion   Home  Schematic Sync  Instance Sync  Pack Registry    v0.2.0 │
└─────────────────────────────────────────────────────────────────┘
```

- Height: 48px, background: `--bg-1`, bottom border: `1px solid --line`
- Logo box: 28×28px, `--accent` background, `--r-btn` radius, white "M"
- App name: 14px bold, `--text-0`
- Nav buttons: `--r-btn` radius, active state: `--accent-soft` bg + `--accent` text + `--accent` border
- Version: `--text-3`, far right

---

## Home Page Layout

```
Sync Overview                              [Refresh]  [Sync All]
┌─────────────────────────────────────────────────────────────────┐
│ INSTANCE          SCHEMATIC SYNC   EXIT SYNC   STARTUP SYNC     │
├─────────────────────────────────────────────────────────────────┤
│ [CC] Create Comb… ● On             ● On         ○ Off   [Sync]  │
│ [CE] Create Exp…  ○ Off            ● On         ○ Off   [Sync]  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Build & CI Changes

### `requirements.txt`
```
pywebview>=5.0
```
Remove: `customtkinter>=5.2.0`

### `MCAddonCompanion.spec`
```python
datas = [("frontend", "frontend")]
# Remove: collect_data_files("customtkinter")
```

### `.gitlab-ci.yml` build_linux before_script
```yaml
- apt-get install -y -qq git binutils libwebkit2gtk-4.1-dev python3-gi gir1.2-webkit2-4.1
- pip install pyinstaller pywebview --quiet
```

### `.github/workflows/build-windows.yml`
No changes — Edge WebView2 is pre-installed on Windows 10+ and 11.

### `installer.iss`
No changes — PyInstaller output structure is the same (`--onedir`).

---

## Headless CLI paths (preserved in main.py)

`--autosync "Name"` and `--startup "Name"` must still work without opening a window. These bypass PyWebView entirely:

```python
if "--autosync" in sys.argv or "--startup" in sys.argv:
    # run headless sync, sys.exit()
    # never calls webview.start()
```

---

## Testing

- `tests/test_api.py` — unit tests for each `Api` method using mocked state
- `tests/test_updater_streams.py` — existing, unchanged
- `tests/test_ui_tokens.py` — can be deleted (CTk design system gone)
- Manual: launch app, click each nav tab, verify page renders, trigger a sync

---

## Files to Delete After Migration

- `core/ui.py` — CTk design system (replaced by CSS)
- `core/progress.py` — CTk progress panel (replaced by JS progress component)
- `modules/*/page.py` — CTk module pages (logic moved to `Api` class)
- `assets/` — icon PNGs (replaced by CSS/SVG)
