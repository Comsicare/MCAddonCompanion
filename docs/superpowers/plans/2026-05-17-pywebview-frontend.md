# PyWebView Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the CustomTkinter UI with a PyWebView window backed by a Vue 3 SPA that matches the Claude Design prototype exactly.

**Architecture:** PyWebView creates a native OS WebView window serving `frontend/index.html`. A Python `Api` class exposes all backend operations as JS-callable methods. Long-running operations stream progress events via `window.evaluate_js`. Vue 3 loaded from a local ESM file — no build toolchain.

**Tech Stack:** Python 3.11, pywebview>=5.0, Vue 3 (ESM bundle), CSS custom properties, PyInstaller (onedir).

**Design spec:** `docs/superpowers/specs/2026-05-17-pywebview-frontend-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Modify | Replace customtkinter with pywebview |
| `main.py` | Rewrite | Api class + PyWebView window creation + headless CLI paths |
| `frontend/index.html` | Create | SPA shell |
| `frontend/style.css` | Create | Design tokens + utility layer |
| `frontend/vue.esm-browser.js` | Download | Vue 3 ESM bundle |
| `frontend/app.js` | Create | Vue root app, routing, progress handler |
| `frontend/pages/home.js` | Create | Home page component |
| `frontend/pages/schematic_sync.js` | Create | Schematic Sync page component |
| `frontend/pages/instance_sync.js` | Create | Instance Sync page component |
| `frontend/pages/pack_registry.js` | Create | Pack Registry page component |
| `MCAddonCompanion.spec` | Modify | Bundle frontend/ instead of CTk assets |
| `.gitlab-ci.yml` | Modify | webkit2gtk deps, swap customtkinter→pywebview |
| `tests/test_api.py` | Create | Unit tests for Api class |

---

### Task 1: Swap dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Replace the contents of `requirements.txt` with:
```
pywebview>=5.0
```

- [ ] **Step 2: Install pywebview**

Run: `venv\Scripts\pip install pywebview`
Expected: `Successfully installed pywebview-5.x.x` (or already satisfied)

- [ ] **Step 3: Verify import**

Run: `venv\Scripts\python -c "import webview; print('pywebview ok')"`
Expected: `pywebview ok`

- [ ] **Step 4: Download Vue 3 ESM bundle**

Run:
```bash
mkdir -p frontend/pages
curl -L "https://unpkg.com/vue@3/dist/vue.esm-browser.js" -o frontend/vue.esm-browser.js
```
Expected: `frontend/vue.esm-browser.js` created, ~200KB.

If curl is not available on Windows, download manually from `https://unpkg.com/vue@3/dist/vue.esm-browser.js` and save to `frontend/vue.esm-browser.js`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt frontend/vue.esm-browser.js
git commit -m "feat: swap customtkinter for pywebview, add Vue 3 ESM bundle"
```

---

### Task 2: Create frontend shell (index.html + style.css + app.js)

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/style.css`
- Create: `frontend/app.js`

- [ ] **Step 1: Create frontend/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MCAddonCompanion</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="app"></div>
  <script type="module" src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create frontend/style.css**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg-0: #14141c;
  --bg-1: #1a1a26;
  --bg-2: #20212f;
  --bg-3: #272938;
  --line: #2c2e3e;
  --line-strong: #383b50;
  --text-0: #ebecf2;
  --text-1: #b6b8c7;
  --text-2: #80839a;
  --text-3: #5b5e74;
  --accent: #8a5cf6;
  --accent-hi: #9d77f7;
  --accent-soft: #1e1535;
  --ok: #6fae8a;       --ok-soft: #1a2e25;
  --warn: #c9a25b;     --warn-soft: #2e2415;
  --err: #c97070;      --err-soft: #2e1a1a;
  --run: #8a7fc9;      --run-soft: #1e1c35;
  --off: #5b5e74;
  --r-card: 10px;
  --r-btn: 4px;
  --r-input: 4px;
  --pad-page-x: 28px;
  --pad-page-y: 24px;
  --pad-card: 16px;
  --gap-card: 16px;
  --gap-section: 20px;
  --top-bar-h: 48px;
  --footer-h: 28px;
  --font-ui: "Segoe UI", "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", "Consolas", monospace;
}

html, body, #app { height: 100%; }
body { background: var(--bg-0); color: var(--text-1); font-family: var(--font-ui); font-size: 10px; }

/* App shell */
.app-shell { display: flex; flex-direction: column; height: 100vh; }
.content { flex: 1 1 0; overflow-y: auto; }

/* Top bar */
.top-bar {
  height: var(--top-bar-h);
  background: var(--bg-1);
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  padding: 0 var(--pad-card);
  gap: 12px;
  flex-shrink: 0;
}
.top-bar-left { display: flex; align-items: center; gap: 8px; }
.logo-box {
  width: 28px; height: 28px;
  background: var(--accent);
  border-radius: var(--r-btn);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; color: #fff;
}
.app-name { font-size: 14px; font-weight: 700; color: var(--text-0); }
.top-bar-nav { display: flex; align-items: center; gap: 4px; margin-left: 16px; }
.nav-btn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--r-btn);
  color: var(--text-1);
  font-family: var(--font-ui);
  font-size: 10px; font-weight: 700;
  padding: 5px 12px;
  cursor: pointer;
  transition: background 0.1s, color 0.1s, border-color 0.1s;
}
.nav-btn:hover { background: var(--bg-2); }
.nav-btn.active {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: var(--accent);
}
.top-bar-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.version { font-size: 9px; color: var(--text-3); }
.update-badge {
  font-size: 9px; font-weight: 700;
  background: var(--accent-soft); color: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--r-btn);
  padding: 3px 8px; cursor: pointer;
}

/* Footer */
.footer {
  height: var(--footer-h);
  background: var(--bg-1);
  border-top: 1px solid var(--line);
  display: flex; align-items: center;
  padding: 0 var(--pad-card);
  font-size: 9px; color: var(--text-3);
  flex-shrink: 0;
}

/* Page layout */
.page { padding: var(--pad-page-y) var(--pad-page-x); display: flex; flex-direction: column; gap: var(--gap-section); height: 100%; }
.page-heading { display: flex; flex-direction: column; gap: 2px; }
.page-heading-row { display: flex; align-items: flex-end; justify-content: space-between; }

/* Cards */
.card {
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: var(--r-card);
}
.card-header {
  display: flex; align-items: center; gap: 8px;
  padding: var(--pad-card) var(--pad-card) 6px;
  border-bottom: 1px solid var(--line);
}
.card-body { padding: var(--pad-card); }

/* Typography */
.kicker {
  font-size: 9px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--text-2);
}
.h1 { font-size: 18px; font-weight: 700; color: var(--text-0); }
.h2 { font-size: 11px; font-weight: 700; color: var(--text-0); }
.stat { font-size: 21px; font-weight: 700; color: var(--text-0); }
.secondary { font-size: 9px; color: var(--text-3); }
.mono { font-family: var(--font-mono); font-size: 9px; color: var(--text-2); }
.text-0 { color: var(--text-0); }
.text-1 { color: var(--text-1); }
.text-2 { color: var(--text-2); }
.text-3 { color: var(--text-3); }
.text-accent { color: var(--accent); }
.text-ok { color: var(--ok); }
.text-err { color: var(--err); }
.text-warn { color: var(--warn); }

/* Buttons */
.btn-primary {
  background: var(--accent); color: #fff;
  border: none; border-radius: var(--r-btn);
  padding: 6px 14px; font-family: var(--font-ui);
  font-size: 10px; font-weight: 700; cursor: pointer;
}
.btn-primary:hover { background: var(--accent-hi); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary.sm { padding: 4px 10px; font-size: 9px; }
.btn-ghost {
  background: transparent; color: var(--text-0);
  border: 1px solid var(--line); border-radius: var(--r-btn);
  padding: 6px 14px; font-family: var(--font-ui);
  font-size: 10px; font-weight: 700; cursor: pointer;
}
.btn-ghost:hover { background: var(--bg-2); }
.btn-ghost.sm { padding: 4px 10px; font-size: 9px; }

/* Inputs */
.input {
  background: var(--bg-0); color: var(--text-0);
  border: 1px solid var(--line); border-radius: var(--r-input);
  padding: 6px 10px; font-family: var(--font-ui);
  font-size: 9px; width: 100%;
}
.input:focus { outline: none; border-color: var(--accent); }
select.input { cursor: pointer; }

/* Toggle switch */
.toggle { position: relative; width: 36px; height: 20px; cursor: pointer; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-track {
  position: absolute; inset: 0;
  background: var(--bg-3); border-radius: 10px;
  transition: background 0.15s;
}
.toggle input:checked + .toggle-track { background: var(--accent); }
.toggle-thumb {
  position: absolute; top: 3px; left: 3px;
  width: 14px; height: 14px;
  background: #fff; border-radius: 50%;
  transition: transform 0.15s;
}
.toggle input:checked ~ .toggle-thumb { transform: translateX(16px); }

/* Status pill */
.pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: var(--r-btn);
  font-size: 9px; font-weight: 700;
}
.pill-ok   { background: var(--ok-soft);   color: var(--ok); }
.pill-err  { background: var(--err-soft);  color: var(--err); }
.pill-warn { background: var(--warn-soft); color: var(--warn); }
.pill-run  { background: var(--run-soft);  color: var(--run); }
.pill-off  { background: var(--bg-2);      color: var(--text-3); }

/* Avatar */
.avatar {
  width: 32px; height: 32px; flex-shrink: 0;
  background: var(--bg-3); border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-mono); font-size: 9px; color: var(--text-2);
}

/* Table */
.table { width: 100%; border-collapse: collapse; }
.table th {
  font-size: 9px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--text-3); text-align: left; padding: 8px 12px;
  border-bottom: 1px solid var(--line);
}
.table td { padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: middle; }
.table tr:last-child td { border-bottom: none; }
.table tr:hover td { background: var(--bg-2); }

/* Two-column layout */
.two-col { display: flex; gap: var(--gap-card); flex: 1 1 0; min-height: 0; }
.col-left { flex-shrink: 0; }
.col-right { flex: 1 1 0; min-width: 0; }

/* Progress panel */
.progress-panel { display: flex; flex-direction: column; gap: 8px; padding: var(--pad-card); }
.progress-row { display: flex; align-items: center; gap: 8px; }
.progress-icon { width: 16px; text-align: center; font-size: 12px; }
.progress-label { flex: 1; font-size: 10px; color: var(--text-1); }
.progress-detail { font-family: var(--font-mono); font-size: 9px; color: var(--text-3); }
.progress-summary { font-size: 9px; color: var(--text-3); padding: 8px var(--pad-card); border-top: 1px solid var(--line); }

/* Sub-tabs */
.sub-tabs {
  display: flex; gap: 2px;
  background: var(--bg-1); border: 1px solid var(--line);
  border-radius: 6px; padding: 3px;
}
.sub-tab {
  background: transparent; border: none; border-radius: 4px;
  color: var(--text-2); font-family: var(--font-ui);
  font-size: 10px; padding: 4px 12px; cursor: pointer;
}
.sub-tab:hover { background: var(--bg-2); color: var(--text-0); }
.sub-tab.active { background: var(--bg-2); color: var(--text-0); }

/* Scrollable list */
.list-scroll { overflow-y: auto; flex: 1 1 0; }
.list-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-radius: var(--r-btn);
  cursor: pointer; color: var(--text-0); font-size: 10px;
}
.list-item:hover { background: var(--bg-2); }
.list-item.active { background: var(--bg-2); }

/* Utility */
.flex { display: flex; }
.flex-col { display: flex; flex-direction: column; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.gap-sm { gap: 8px; }
.gap-md { gap: var(--gap-card); }
.gap-lg { gap: var(--gap-section); }
.fill { flex: 1 1 0; min-width: 0; }
.w-full { width: 100%; }
.mt-sm { margin-top: 8px; }
.mt-md { margin-top: var(--gap-card); }
.sep { height: 1px; background: var(--line); margin: 8px 0; }
.loading { color: var(--text-3); font-size: 10px; padding: 24px; text-align: center; }
.empty { color: var(--text-3); font-size: 10px; padding: 24px; text-align: center; }
```

- [ ] **Step 3: Create frontend/app.js**

```js
import { createApp, ref, defineAsyncComponent } from './vue.esm-browser.js'
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

const VERSION = document.title  // overwritten by Python on load

createApp({
  setup() {
    const page = ref('home')
    const progress = ref({})
    const updateInfo = ref(null)
    const version = ref('')

    // Global progress handler — Python calls window.__onProgress(event)
    window.__onProgress = (event) => {
      if (event.type === 'reset') {
        progress.value = {}
        return
      }
      progress.value = { ...progress.value, ...event }
    }

    window.addEventListener('pywebviewready', async () => {
      try {
        const info = await window.pywebview.api.check_update()
        if (info) updateInfo.value = info
        const v = await window.pywebview.api.get_version()
        version.value = v
      } catch (e) {
        console.warn('pywebview API not ready:', e)
      }
    })

    return { page, progress, updateInfo, version, NAV, PAGES }
  },
  template: `
    <div class="app-shell">
      <header class="top-bar">
        <div class="top-bar-left">
          <div class="logo-box">M</div>
          <span class="app-name">MCAddonCompanion</span>
        </div>
        <nav class="top-bar-nav">
          <button
            v-for="n in NAV" :key="n.key"
            class="nav-btn" :class="{ active: page === n.key }"
            @click="page = n.key">{{ n.label }}</button>
        </nav>
        <div class="top-bar-right">
          <span v-if="updateInfo" class="update-badge">Update available</span>
          <span class="version">v{{ version }}</span>
        </div>
      </header>

      <main class="content">
        <component :is="PAGES[page]" :progress="progress" @navigate="page = $event" />
      </main>

      <footer class="footer">
        MCAddonCompanion v{{ version }} · © 2026 Comsicare
      </footer>
    </div>
  `
}).mount('#app')
```

- [ ] **Step 4: Verify the shell opens in a browser**

Open `frontend/index.html` directly in Chrome/Edge.
Expected: Black background, "MCAddonCompanion" top bar, 4 nav buttons, footer. No JS errors in DevTools console. (pywebview API won't work yet — that's fine.)

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/style.css frontend/app.js
git commit -m "feat: add PyWebView SPA shell — index.html, style.css, app.js"
```

---

### Task 3: Create placeholder page components

**Files:**
- Create: `frontend/pages/home.js`
- Create: `frontend/pages/schematic_sync.js`
- Create: `frontend/pages/instance_sync.js`
- Create: `frontend/pages/pack_registry.js`

Create stub components so the router works end-to-end before we fill in the real content.

- [ ] **Step 1: Create frontend/pages/home.js**

```js
export default {
  props: ['progress'],
  template: `<div class="page"><div class="loading">Home page — loading…</div></div>`
}
```

- [ ] **Step 2: Create frontend/pages/schematic_sync.js**

```js
export default {
  props: ['progress'],
  template: `<div class="page"><div class="loading">Schematic Sync — loading…</div></div>`
}
```

- [ ] **Step 3: Create frontend/pages/instance_sync.js**

```js
export default {
  props: ['progress'],
  template: `<div class="page"><div class="loading">Instance Sync — loading…</div></div>`
}
```

- [ ] **Step 4: Create frontend/pages/pack_registry.js**

```js
export default {
  props: ['progress'],
  template: `<div class="page"><div class="loading">Pack Registry — loading…</div></div>`
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/pages/
git commit -m "feat: add stub page components for SPA routing"
```

---

### Task 4: Rewrite main.py — Api class + PyWebView window

**Files:**
- Rewrite: `main.py`

Read `main.py` fully before writing. Preserve:
- `_configure_logging()`
- Venv bootstrap block
- `_plan_instance()`, `_execute_instance_plan()`, `run_sync_with_progress()`, `run_sync_all_with_progress()`
- Headless `--autosync` and `--startup` CLI paths
- `repair_hooks()`

Replace:
- All CTk/tkinter imports and the `App` class
- `_build_home_page()` (moves to `frontend/pages/home.js`)
- The `webview.start()` call is the new entry point

- [ ] **Step 1: Write tests/test_api.py**

```python
# tests/test_api.py
import sys
sys.path.insert(0, ".")
import unittest.mock as mock


def _make_api():
    """Create an Api instance with a null window ref."""
    win_ref = [None]
    # Import Api — patch webview so it doesn't need a display
    with mock.patch.dict("sys.modules", {"webview": mock.MagicMock()}):
        # Re-import to get Api without webview side effects
        import importlib
        import main as m
        importlib.reload(m)
        return m.Api(win_ref)


def test_get_version():
    from core.config import VERSION
    api = _make_api()
    assert api.get_version() == VERSION


def test_get_home_data_returns_dict():
    api = _make_api()
    result = api.get_home_data()
    assert isinstance(result, dict)
    assert "instances" in result


def test_get_schematic_data_returns_dict():
    api = _make_api()
    result = api.get_schematic_data()
    assert isinstance(result, dict)
    assert "instances" in result
    assert "autosync_instances" in result


def test_get_instance_sync_data_returns_dict():
    api = _make_api()
    result = api.get_instance_sync_data()
    assert isinstance(result, dict)
    assert "is_configured" in result


def test_get_repos_returns_list():
    api = _make_api()
    result = api.get_repos()
    assert isinstance(result, list)
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `venv\Scripts\pytest tests/test_api.py -v`
Expected: FAIL — `Api` not defined in `main.py` yet.

- [ ] **Step 3: Rewrite main.py**

```python
import logging
import logging.handlers
import os
import pathlib
import sys
import json
import threading
from pathlib import Path


def _configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    if sys.platform == "win32":
        log_dir = pathlib.Path(os.environ.get("APPDATA", ".")) / "MCAddonCompanion"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", str(pathlib.Path.home() / ".local/share"))
        log_dir = pathlib.Path(xdg) / "MCAddonCompanion"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "mcaddoncompanion.log"
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    if not getattr(sys, "frozen", False):
        root.addHandler(logging.StreamHandler())


_configure_logging()

if not getattr(sys, "frozen", False):
    _VENV = Path(__file__).parent / "venv"
    if sys.platform == "win32":
        _VENV_PYTHON = _VENV / "Scripts" / "pythonw.exe"
    else:
        _VENV_PYTHON = _VENV / "bin" / "python"

    def _ensure_venv():
        if _VENV.exists() and sys.executable != str(_VENV_PYTHON):
            import subprocess
            subprocess.Popen([str(_VENV_PYTHON)] + sys.argv)
            sys.exit(0)

    def _create_venv():
        import venv, subprocess
        print("Creating venv...")
        venv.create(str(_VENV), with_pip=True)
        reqs = Path(__file__).parent / "requirements.txt"
        if reqs.exists() and reqs.read_text().strip():
            pip = str(_VENV / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip"))
            subprocess.check_call([pip, "install", "-r", str(reqs)])

    if not _VENV.exists():
        _create_venv()
    _ensure_venv()

import webview

from core.config import INSTANCES_DIR, VERSION
from core.prism import get_minecraft_dir, is_prism_running, patch_exit_commands
from core.state import (
    load_state, save_state,
    get_instance_sync_config, save_instance_sync_config,
    get_instance_effective_settings, is_instance_sync_configured,
    get_pack_registry_repos, save_pack_registry_repos, make_repo_id,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sync orchestration (headless + GUI shared)
# ---------------------------------------------------------------------------

def _plan_instance(instance_name: str, mode: str) -> dict:
    state = load_state()
    plan: dict = {"schematic": False, "instance_task": None,
                  "cfg": None, "settings": None, "mc_dir": None, "sync_dir": None}
    if mode == "exit":
        plan["schematic"] = instance_name in state.get("schematic_sync", {}).get("autosync_instances", [])
    if is_instance_sync_configured():
        cfg = get_instance_sync_config()
        settings = get_instance_effective_settings(cfg, instance_name)
        if settings["enabled"]:
            instances_path = Path(cfg["instances_path"])
            sync_path = Path(cfg["sync_path"])
            mc_dir = get_minecraft_dir(instances_path, instance_name)
            sync_dir = sync_path / "instance_sync" / instance_name
            if mc_dir:
                plan.update(cfg=cfg, settings=settings, mc_dir=mc_dir, sync_dir=sync_dir)
                if mode == "exit" and settings["exit_sync"]:
                    plan["instance_task"] = "Exit Sync"
                elif mode == "startup" and settings["startup_sync"]:
                    plan["instance_task"] = "Startup Sync"
    return plan


def _execute_instance_plan(emit, inst: str, plan: dict):
    """Execute a pre-planned sync, emitting progress events via emit()."""
    from modules.schematic_sync.page import run_autosync as _ss_run_autosync
    from modules.instance_sync.sync import (
        is_blacklisted, read_manifest, write_manifest, _file_stat, _append_changelog
    )
    import shutil
    from datetime import datetime

    step = 0

    if plan["schematic"]:
        emit({"type": "step", "step": step, "state": "running", "detail": ""})
        result = _ss_run_autosync([inst])
        errors = result.get("errors", [])
        emit({"type": "step", "step": step, "state": "error" if errors else "ok",
              "detail": f"{result.get('pulled', 0) + result.get('pushed', 0)} files"})
        step += 1

    mc_dir = plan["mc_dir"]
    sync_dir = plan["sync_dir"]

    if plan["instance_task"] == "Exit Sync":
        emit({"type": "step", "step": step, "state": "running", "detail": "Scanning"})
        old_manifest = read_manifest(sync_dir)
        all_files = [(src, src.relative_to(mc_dir).as_posix())
                     for src in mc_dir.rglob("*") if src.is_file()]
        to_copy = [(src, rel) for src, rel in all_files if not is_blacklisted(rel)]
        emit({"type": "step", "step": step, "state": "ok", "detail": f"{len(to_copy)} files"})
        step += 1

        emit({"type": "step", "step": step, "state": "running", "detail": ""})
        copied, errors, new_manifest = 0, [], {}
        for src, rel in to_copy:
            dest = sync_dir / rel
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dest))
                new_manifest[rel] = _file_stat(dest)
                copied += 1
            except Exception as e:
                errors.append(f"{rel}: {e}")
        for stale_rel in set(old_manifest) - set(new_manifest):
            try:
                stale = sync_dir / stale_rel
                if stale.exists():
                    stale.unlink()
            except Exception as e:
                errors.append(f"prune {stale_rel}: {e}")
        write_manifest(sync_dir, new_manifest)
        _append_changelog(sync_dir.parent / ".changelog", {
            "instance": inst, "mode": "exit",
            "timestamp": datetime.utcnow().isoformat(),
            "copied": copied, "errors": errors,
        })
        emit({"type": "step", "step": step, "state": "error" if errors else "ok",
              "detail": f"{copied} copied"})
        step += 1

    elif plan["instance_task"] == "Startup Sync":
        from modules.instance_sync.sync import run_startup_sync
        cfg = plan["cfg"]
        emit({"type": "step", "step": step, "state": "running", "detail": ""})
        result = run_startup_sync(inst, cfg)
        errors = result.get("errors", [])
        emit({"type": "step", "step": step, "state": "error" if errors else "ok",
              "detail": f"{result.get('restored', 0)} files"})


def repair_hooks():
    state = load_state()
    inst_sync = state.get("instance_sync", {})
    if not is_instance_sync_configured():
        return
    cfg = get_instance_sync_config()
    enabled = [n for n, v in cfg.get("instances", {}).items() if v.get("enabled", False)]
    if enabled:
        patch_exit_commands(enabled, __file__, Path(cfg["instances_path"]))


# ---------------------------------------------------------------------------
# Api class — exposed to JS via pywebview
# ---------------------------------------------------------------------------

class Api:
    def __init__(self, window_ref: list):
        self._win = window_ref  # list so it's mutable before window is created

    def _emit(self, event: dict) -> None:
        if self._win[0]:
            self._win[0].evaluate_js(f"window.__onProgress({json.dumps(event)})")

    def get_version(self) -> str:
        return VERSION

    # ── Home ──────────────────────────────────────────────────────────

    def get_home_data(self) -> dict:
        state = load_state()
        autosync = state.get("schematic_sync", {}).get("autosync_instances", [])
        inst_sync = state.get("instance_sync", {})
        instances_cfg = inst_sync.get("instances", {})
        defaults = inst_sync.get("defaults", {"exit_sync": True, "startup_sync": False})

        all_instances = sorted(
            d.name for d in INSTANCES_DIR.iterdir()
            if d.is_dir() and not d.name.endswith(".tmp")
        ) if INSTANCES_DIR.exists() else []

        rows = []
        for name in all_instances:
            inst_cfg = instances_cfg.get(name, {})
            eff = get_instance_effective_settings({"defaults": defaults, "instances": instances_cfg}, name) if is_instance_sync_configured() else {}
            rows.append({
                "name": name,
                "schematic_sync": name in autosync,
                "exit_sync": eff.get("exit_sync", False),
                "startup_sync": eff.get("startup_sync", False),
            })
        return {"instances": rows}

    def sync_instance(self, name: str, mode: str) -> None:
        plan = _plan_instance(name, mode)
        def _run():
            self._emit({"type": "reset"})
            _execute_instance_plan(self._emit, name, plan)
            self._emit({"type": "summary", "text": "Sync complete.", "tone": "ok"})
        threading.Thread(target=_run, daemon=True).start()

    def sync_all(self, mode: str) -> None:
        state = load_state()
        instances = sorted(
            d.name for d in INSTANCES_DIR.iterdir()
            if d.is_dir() and not d.name.endswith(".tmp")
        ) if INSTANCES_DIR.exists() else []
        def _run():
            self._emit({"type": "reset"})
            for name in instances:
                plan = _plan_instance(name, mode)
                _execute_instance_plan(self._emit, name, plan)
            self._emit({"type": "summary", "text": "All synced.", "tone": "ok"})
        threading.Thread(target=_run, daemon=True).start()

    # ── Schematic Sync ────────────────────────────────────────────────

    def get_schematic_data(self) -> dict:
        state = load_state()
        autosync = state.get("schematic_sync", {}).get("autosync_instances", [])
        instances = sorted(
            d.name for d in INSTANCES_DIR.iterdir()
            if d.is_dir() and not d.name.endswith(".tmp")
        ) if INSTANCES_DIR.exists() else []
        return {"instances": instances, "autosync_instances": autosync}

    def set_autosync(self, name: str, enabled: bool) -> None:
        state = load_state()
        lst = state.setdefault("schematic_sync", {}).setdefault("autosync_instances", [])
        if enabled:
            if name not in lst:
                lst.append(name)
        else:
            state["schematic_sync"]["autosync_instances"] = [x for x in lst if x != name]
        save_state(state)

    def run_schematic_sync(self, name: str) -> None:
        from modules.schematic_sync.page import run_autosync
        def _run():
            self._emit({"type": "reset"})
            self._emit({"type": "step", "step": 0, "state": "running", "detail": ""})
            result = run_autosync([name])
            errors = result.get("errors", [])
            files = result.get("pulled", 0) + result.get("pushed", 0)
            self._emit({"type": "step", "step": 0,
                        "state": "error" if errors else "ok", "detail": f"{files} files"})
            tone = "error" if errors else "ok"
            self._emit({"type": "summary",
                        "text": f"Synced {files} files." if not errors else f"Errors: {errors[0]}",
                        "tone": tone})
        threading.Thread(target=_run, daemon=True).start()

    def get_schematic_counts(self, name: str) -> dict:
        from core.config import EXTENSIONS
        mc_dir = get_minecraft_dir(INSTANCES_DIR, name)
        counts = {ext: 0 for ext in EXTENSIONS}
        if mc_dir:
            for ext in EXTENSIONS:
                counts[ext] = len(list(mc_dir.rglob(f"*{ext}")))
        return counts

    # ── Instance Sync ─────────────────────────────────────────────────

    def get_instance_sync_data(self) -> dict:
        configured = is_instance_sync_configured()
        if not configured:
            return {"is_configured": False}
        state = load_state()
        inst_sync = state.get("instance_sync", {})
        defaults = inst_sync.get("defaults", {"exit_sync": True, "startup_sync": False})
        sync_path = inst_sync.get("sync_path", "")
        instances_cfg = inst_sync.get("instances", {})
        all_instances = sorted(
            d.name for d in INSTANCES_DIR.iterdir()
            if d.is_dir() and not d.name.endswith(".tmp")
        ) if INSTANCES_DIR.exists() else []
        rows = []
        for name in all_instances:
            inst_cfg = instances_cfg.get(name, {})
            rows.append({
                "name": name,
                "exit_sync": inst_cfg.get("exit_sync") if inst_cfg.get("exit_sync") is not None else defaults["exit_sync"],
                "startup_sync": inst_cfg.get("startup_sync") if inst_cfg.get("startup_sync") is not None else defaults.get("startup_sync", False),
                "enabled": inst_cfg.get("enabled", True),
            })
        return {
            "is_configured": True,
            "defaults": defaults,
            "sync_path": sync_path,
            "instances": rows,
        }

    def set_instance_default(self, key: str, value: bool) -> None:
        state = load_state()
        state.setdefault("instance_sync", {}).setdefault("defaults", {})[key] = value
        save_state(state)

    def set_instance_override(self, name: str, key: str, value: bool) -> None:
        state = load_state()
        state.setdefault("instance_sync", {}).setdefault("instances", {}).setdefault(name, {})[key] = value
        save_state(state)

    # ── Pack Registry ─────────────────────────────────────────────────

    def get_repos(self) -> list:
        return get_pack_registry_repos()

    def save_repo(self, repo: dict) -> dict:
        import urllib.request
        from urllib.parse import urlparse
        url = repo.get("url", "").strip()
        pat = repo.get("pat_token", "").strip()
        name = repo.get("name", "").strip()
        pkg = repo.get("package_name", "mc-packs").strip()
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        project_path = parsed.path.strip("/").replace("/", "%2F")
        req = urllib.request.Request(
            f"{base_url}/api/v4/projects/{project_path}",
            headers={"PRIVATE-TOKEN": pat},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        project_id = str(data["id"])
        repos = get_pack_registry_repos()
        rid = repo.get("id") or make_repo_id()
        repo_obj = {
            "id": rid, "name": name, "base_url": base_url,
            "project_id": project_id, "upload_token": pat,
            "read_token": pat, "package_name": pkg,
        }
        existing_ids = [r["id"] for r in repos]
        if rid in existing_ids:
            repos = [repo_obj if r["id"] == rid else r for r in repos]
        else:
            repos.append(repo_obj)
        save_pack_registry_repos(repos)
        return repo_obj

    def delete_repo(self, repo_id: str) -> None:
        repos = [r for r in get_pack_registry_repos() if r["id"] != repo_id]
        save_pack_registry_repos(repos)

    def get_packs(self, repo_id: str) -> list:
        from core.gitlab import GitLabClient
        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            return []
        client = GitLabClient(repo["base_url"], repo["project_id"],
                              repo.get("upload_token"), repo.get("read_token"))
        return sorted(set(client.list_all_packages()))

    def get_versions(self, repo_id: str, pack_name: str) -> list:
        from core.gitlab import GitLabClient
        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            return []
        client = GitLabClient(repo["base_url"], repo["project_id"],
                              repo.get("upload_token"), repo.get("read_token"))
        return sorted(client.list_packages(pack_name), reverse=True)

    def publish_pack(self, params: dict) -> None:
        import tempfile, json as _json
        from datetime import datetime, timezone
        from core.gitlab import GitLabClient
        from core.sharing import build_export_zip, get_export_file_list
        from core.config import INSTANCES_DIR as INST_DIR

        repo_id = params["repo_id"]
        inst_name = params["instance_name"]
        categories = params.get("categories", {})
        metadata_in = params.get("metadata", {})

        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            self._emit({"type": "summary", "text": "Repo not found.", "tone": "error"})
            return

        mc_dir = get_minecraft_dir(INST_DIR, inst_name)
        if not mc_dir:
            self._emit({"type": "summary", "text": "Instance not found.", "tone": "error"})
            return

        def _run():
            try:
                self._emit({"type": "reset"})
                instance_dir = INST_DIR / inst_name
                file_list = get_export_file_list(mc_dir, categories, [])
                version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                pkg = repo.get("package_name", "mc-packs")
                zip_filename = f"{pkg}-{version}.zip"
                metadata = {
                    "instance_name": inst_name, "version": version,
                    **metadata_in, "categories": [k for k, v in categories.items() if v],
                }
                self._emit({"type": "step", "step": 0, "state": "running", "detail": ""})
                with tempfile.TemporaryDirectory() as tmp:
                    zip_path = Path(tmp) / zip_filename
                    build_export_zip(inst_name, mc_dir, instance_dir, file_list, zip_path)
                    size_mb = zip_path.stat().st_size / 1_048_576
                    self._emit({"type": "step", "step": 0, "state": "ok", "detail": f"{size_mb:.1f} MB"})
                    client = GitLabClient(repo["base_url"], repo["project_id"],
                                         repo.get("upload_token"), repo.get("read_token"))
                    self._emit({"type": "step", "step": 1, "state": "running", "detail": ""})
                    client.upload_file_path(pkg, version, zip_filename, zip_path)
                    self._emit({"type": "step", "step": 1, "state": "ok", "detail": ""})
                    self._emit({"type": "step", "step": 2, "state": "running", "detail": ""})
                    client.upload_file(pkg, version, "metadata.json",
                                       _json.dumps(metadata, indent=2).encode(),
                                       content_type="application/json")
                    self._emit({"type": "step", "step": 2, "state": "ok", "detail": ""})
                self._emit({"type": "summary", "text": f"Published {pkg} v{version}.", "tone": "ok"})
            except Exception as e:
                self._emit({"type": "summary", "text": f"Error: {e}", "tone": "error"})

        threading.Thread(target=_run, daemon=True).start()

    def install_pack(self, params: dict) -> None:
        import urllib.request, zipfile, io
        from core.gitlab import GitLabClient
        from core.sharing import read_export_zip, get_import_file_list, extract_zip

        repo_id = params["repo_id"]
        pack_name = params["pack_name"]
        version = params["version"]
        inst_name = params["instance_name"]

        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            return

        def _run():
            try:
                client = GitLabClient(repo["base_url"], repo["project_id"],
                                      repo.get("upload_token"), repo.get("read_token"))
                zip_filename = f"{pack_name}-{version}.zip"
                url = client.build_download_url(pack_name, version, zip_filename)
                with urllib.request.urlopen(url) as resp:
                    data = resp.read()
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    manifest = read_export_zip(zf)
                    files = get_import_file_list(zf, manifest)
                    extract_zip(zf, files, INSTANCES_DIR / inst_name)
                self._emit({"type": "summary", "text": f"Installed {pack_name} v{version}.", "tone": "ok"})
            except Exception as e:
                self._emit({"type": "summary", "text": f"Install failed: {e}", "tone": "error"})

        threading.Thread(target=_run, daemon=True).start()

    def read_instance_meta(self, inst_name: str) -> dict:
        try:
            mmc = INSTANCES_DIR / inst_name / "mmc-pack.json"
            if mmc.exists():
                data = json.loads(mmc.read_text(encoding="utf-8"))
                mc_ver = next((c["version"] for c in data.get("components", [])
                               if c.get("uid") == "net.minecraft"), "")
                loader = next((c["uid"].split(".")[-1] for c in data.get("components", [])
                               if c.get("uid", "").startswith("net.") and "minecraft" not in c.get("uid", "")), "")
                return {"mc_version": mc_ver, "loader": loader}
        except Exception:
            pass
        return {"mc_version": "", "loader": ""}

    def get_all_instances(self) -> list:
        if not INSTANCES_DIR.exists():
            return []
        return sorted(d.name for d in INSTANCES_DIR.iterdir()
                      if d.is_dir() and not d.name.endswith(".tmp"))

    # ── Updater ───────────────────────────────────────────────────────

    def check_update(self) -> dict | None:
        try:
            from core.updater import check_for_update
            return check_for_update()
        except Exception as e:
            log.warning("Update check failed: %s", e)
            return None

    def dismiss_update(self) -> None:
        pass  # future: persist dismissed version to state


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _headless_autosync(name: str) -> None:
    state = load_state()
    instances = [d.name for d in INSTANCES_DIR.iterdir() if d.is_dir()] if INSTANCES_DIR.exists() else []
    if name not in instances:
        log.error("Instance %r not found", name)
        sys.exit(1)
    plan = _plan_instance(name, "exit")
    def _noop(event): pass
    _execute_instance_plan(_noop, name, plan)
    sys.exit(0)


def _headless_startup(name: str) -> None:
    instances = [d.name for d in INSTANCES_DIR.iterdir() if d.is_dir()] if INSTANCES_DIR.exists() else []
    if name not in instances:
        log.error("Instance %r not found", name)
        sys.exit(1)
    plan = _plan_instance(name, "startup")
    def _noop(event): pass
    _execute_instance_plan(_noop, name, plan)
    sys.exit(0)


if __name__ == "__main__":
    if "--autosync" in sys.argv:
        idx = sys.argv.index("--autosync")
        _headless_autosync(sys.argv[idx + 1])

    if "--startup" in sys.argv:
        idx = sys.argv.index("--startup")
        _headless_startup(sys.argv[idx + 1])

    repair_hooks()

    win_ref: list = [None]
    api = Api(win_ref)

    frontend_dir = Path(__file__).parent / "frontend"
    window = webview.create_window(
        "MCAddonCompanion",
        url=str(frontend_dir / "index.html"),
        js_api=api,
        width=1100,
        height=720,
        min_size=(800, 600),
    )
    win_ref[0] = window

    webview.start(debug=not getattr(sys, "frozen", False))
```

- [ ] **Step 4: Run tests**

Run: `venv\Scripts\pytest tests/test_api.py -v`
Expected: All 5 tests pass.

- [ ] **Step 5: Run app and verify it opens**

Run: `venv\Scripts\python main.py`
Expected: A native window opens showing the SPA shell with nav tabs. All tabs clickable. Pages show loading placeholder. No Python errors in console.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_api.py
git commit -m "feat: rewrite main.py with PyWebView Api class and webview window"
```

---

### Task 5: Home page component

**Files:**
- Rewrite: `frontend/pages/home.js`

- [ ] **Step 1: Rewrite frontend/pages/home.js**

```js
import { ref, onMounted } from '../vue.esm-browser.js'

export default {
  props: ['progress'],
  emits: ['navigate'],
  setup(props, { emit }) {
    const data = ref(null)
    const loading = ref(true)

    const load = async () => {
      loading.value = true
      data.value = await window.pywebview.api.get_home_data()
      loading.value = false
    }

    onMounted(load)

    const syncInstance = async (name) => {
      await window.pywebview.api.sync_instance(name, 'exit')
    }

    const syncAll = async () => {
      await window.pywebview.api.sync_all('exit')
    }

    const initials = (name) => name.split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('')

    return { data, loading, load, syncInstance, syncAll, initials }
  },
  template: `
    <div class="page">
      <div class="page-heading">
        <span class="kicker">Overview</span>
        <div class="page-heading-row">
          <h1 class="h1">Sync Overview</h1>
          <div class="flex gap-sm">
            <button class="btn-ghost sm" @click="load">↻ Refresh</button>
            <button class="btn-primary sm" @click="syncAll">Sync All</button>
          </div>
        </div>
      </div>

      <div v-if="loading" class="loading">Loading…</div>

      <div v-else-if="!data || !data.instances.length" class="card">
        <div class="empty">No instances configured for sync yet.</div>
      </div>

      <div v-else class="card" style="overflow: hidden;">
        <table class="table" style="width:100%">
          <thead>
            <tr>
              <th>Instance</th>
              <th>Schematic Sync</th>
              <th>Exit Sync</th>
              <th>Startup Sync</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="inst in data.instances" :key="inst.name">
              <td>
                <div class="flex items-center gap-sm">
                  <div class="avatar">{{ initials(inst.name) }}</div>
                  <span class="text-0">{{ inst.name }}</span>
                </div>
              </td>
              <td>
                <span :class="inst.schematic_sync ? 'pill pill-ok' : 'pill pill-off'">
                  {{ inst.schematic_sync ? '● On' : '○ Off' }}
                </span>
              </td>
              <td>
                <span :class="inst.exit_sync ? 'pill pill-ok' : 'pill pill-off'">
                  {{ inst.exit_sync ? '● On' : '○ Off' }}
                </span>
              </td>
              <td>
                <span :class="inst.startup_sync ? 'pill pill-ok' : 'pill pill-off'">
                  {{ inst.startup_sync ? '● On' : '○ Off' }}
                </span>
              </td>
              <td style="text-align:right">
                <button class="btn-ghost sm" @click="syncInstance(inst.name)">Sync</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `
}
```

- [ ] **Step 2: Launch app and verify Home page**

Run: `venv\Scripts\python main.py`
Expected: Home page shows instance table with On/Off pills and Sync buttons. Clicking "Sync" triggers a sync.

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/home.js
git commit -m "feat: implement Home page with sync overview table"
```

---

### Task 6: Schematic Sync page component

**Files:**
- Rewrite: `frontend/pages/schematic_sync.js`

- [ ] **Step 1: Rewrite frontend/pages/schematic_sync.js**

```js
import { ref, onMounted, computed } from '../vue.esm-browser.js'

const SYNC_STEPS = [
  'Scan instance folder',
  'Diff against archive',
  'Copy .nbt files',
  'Copy .litematic files',
  'Copy .schematic files',
]

const STEP_ICONS = { pending: '◌', running: '⟳', ok: '✓', error: '✗' }
const STEP_COLORS = { pending: 'var(--text-3)', running: 'var(--accent)', ok: 'var(--ok)', error: 'var(--err)' }

export default {
  props: ['progress'],
  setup(props) {
    const data = ref(null)
    const loading = ref(true)
    const selected = ref(null)
    const counts = ref({})
    const syncing = ref(false)

    const steps = ref(SYNC_STEPS.map(label => ({ label, state: 'pending', detail: '' })))
    const summary = ref(null)

    onMounted(async () => {
      data.value = await window.pywebview.api.get_schematic_data()
      loading.value = false
      if (data.value.instances.length) select(data.value.instances[0])
    })

    // Watch for progress events
    const origHandler = window.__onProgress
    window.__onProgress = (event) => {
      if (origHandler) origHandler(event)
      if (event.type === 'reset') {
        steps.value = SYNC_STEPS.map(label => ({ label, state: 'pending', detail: '' }))
        summary.value = null
      } else if (event.type === 'step') {
        if (steps.value[event.step]) {
          steps.value[event.step].state = event.state
          steps.value[event.step].detail = event.detail || ''
        }
      } else if (event.type === 'summary') {
        summary.value = event
        syncing.value = false
      }
    }

    const select = async (name) => {
      selected.value = name
      counts.value = await window.pywebview.api.get_schematic_counts(name)
    }

    const toggleAutosync = async (name, val) => {
      await window.pywebview.api.set_autosync(name, val)
      data.value = await window.pywebview.api.get_schematic_data()
    }

    const runSync = async () => {
      if (!selected.value || syncing.value) return
      syncing.value = true
      steps.value = SYNC_STEPS.map(label => ({ label, state: 'pending', detail: '' }))
      summary.value = null
      await window.pywebview.api.run_schematic_sync(selected.value)
    }

    const isAuto = computed(() =>
      data.value ? data.value.autosync_instances.includes(selected.value) : false
    )

    const initials = (name) => name.split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('')

    return { data, loading, selected, counts, steps, summary, syncing, isAuto, select, toggleAutosync, runSync, initials, STEP_ICONS, STEP_COLORS }
  },
  template: `
    <div class="page">
      <div class="page-heading">
        <span class="kicker">Schematic Sync</span>
        <h1 class="h1">Schematic Sync</h1>
      </div>

      <div v-if="loading" class="loading">Loading…</div>

      <div v-else class="two-col fill">
        <!-- Left: instance list -->
        <div class="col-left card flex-col" style="width:240px">
          <div class="card-header">
            <span class="kicker">Instances</span>
            <span class="h2">{{ data.instances.length }}</span>
          </div>
          <div class="list-scroll">
            <div
              v-for="name in data.instances" :key="name"
              class="list-item" :class="{ active: selected === name }"
              @click="select(name)">
              <div class="avatar" style="width:24px;height:24px;font-size:8px">{{ initials(name) }}</div>
              <span>{{ name }}</span>
            </div>
          </div>
        </div>

        <!-- Right: detail -->
        <div class="col-right flex-col gap-md" v-if="selected">
          <!-- Header -->
          <div class="flex items-center justify-between">
            <div>
              <div class="kicker">Instance</div>
              <div class="h2">{{ selected }}</div>
            </div>
            <label class="flex items-center gap-sm" style="cursor:pointer">
              <span class="secondary">Autosync on exit</span>
              <label class="toggle">
                <input type="checkbox" :checked="isAuto" @change="toggleAutosync(selected, $event.target.checked)">
                <div class="toggle-track"></div>
                <div class="toggle-thumb"></div>
              </label>
            </label>
          </div>

          <!-- Stats -->
          <div class="card">
            <div class="card-body flex gap-md">
              <div v-for="(count, ext) in counts" :key="ext">
                <div class="kicker">{{ ext.replace('.','').toUpperCase() }} Files</div>
                <div class="stat">{{ count }}</div>
              </div>
            </div>
          </div>

          <!-- Progress + action -->
          <div class="flex gap-md fill">
            <!-- Progress panel -->
            <div class="card fill">
              <div class="card-header"><span class="kicker">Progress</span></div>
              <div class="progress-panel">
                <div v-for="(step, i) in steps" :key="i" class="progress-row">
                  <span class="progress-icon" :style="{ color: STEP_COLORS[step.state] }">{{ STEP_ICONS[step.state] }}</span>
                  <span class="progress-label">{{ step.label }}</span>
                  <span class="progress-detail">{{ step.detail }}</span>
                </div>
              </div>
              <div v-if="summary" class="progress-summary"
                :style="{ color: summary.tone === 'ok' ? 'var(--ok)' : 'var(--err)' }">
                {{ summary.text }}
              </div>
            </div>

            <!-- Action card -->
            <div class="card" style="min-width:140px">
              <div class="card-body flex-col gap-sm">
                <span class="kicker">Actions</span>
                <button class="btn-primary sm" :disabled="syncing" @click="runSync">
                  {{ syncing ? '⟳ Syncing…' : '↻ Sync now' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="col-right empty">Select an instance</div>
      </div>
    </div>
  `
}
```

- [ ] **Step 2: Launch and verify**

Run: `venv\Scripts\python main.py`, click Schematic Sync.
Expected: Left panel shows instance list. Click an instance — right panel shows stats + progress panel + Sync button. Clicking Sync updates progress rows in real time.

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/schematic_sync.js
git commit -m "feat: implement Schematic Sync page with two-column layout and live progress"
```

---

### Task 7: Instance Sync page component

**Files:**
- Rewrite: `frontend/pages/instance_sync.js`

- [ ] **Step 1: Rewrite frontend/pages/instance_sync.js**

```js
import { ref, onMounted } from '../vue.esm-browser.js'

export default {
  props: ['progress'],
  setup() {
    const data = ref(null)
    const loading = ref(true)

    onMounted(async () => {
      data.value = await window.pywebview.api.get_instance_sync_data()
      loading.value = false
    })

    const setDefault = async (key, val) => {
      await window.pywebview.api.set_instance_default(key, val)
      data.value = await window.pywebview.api.get_instance_sync_data()
    }

    const setOverride = async (name, key, val) => {
      await window.pywebview.api.set_instance_override(name, key, val)
      data.value = await window.pywebview.api.get_instance_sync_data()
    }

    const initials = (name) => name.split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('')

    return { data, loading, setDefault, setOverride, initials }
  },
  template: `
    <div class="page">
      <div class="page-heading">
        <span class="kicker">Instance Sync</span>
        <div class="page-heading-row">
          <h1 class="h1">Instance Sync</h1>
          <span v-if="data && data.is_configured" class="secondary">
            {{ data.instances.length }} instances
          </span>
        </div>
      </div>

      <div v-if="loading" class="loading">Loading…</div>

      <div v-else-if="!data.is_configured" class="card">
        <div class="card-body">
          <div class="h2">Not configured</div>
          <p class="secondary mt-sm">Run the setup wizard to configure instance sync.</p>
        </div>
      </div>

      <template v-else>
        <!-- Defaults card -->
        <div class="card">
          <div class="card-header">
            <span class="kicker">Defaults</span>
            <span class="h2">Global Defaults</span>
            <span class="secondary" style="margin-left:auto">Applied to new instances</span>
          </div>
          <div class="card-body flex gap-lg">
            <div>
              <div class="kicker">Exit Sync Default</div>
              <label class="toggle mt-sm">
                <input type="checkbox" :checked="data.defaults.exit_sync"
                  @change="setDefault('exit_sync', $event.target.checked)">
                <div class="toggle-track"></div>
                <div class="toggle-thumb"></div>
              </label>
            </div>
            <div>
              <div class="kicker">Startup Sync Default</div>
              <label class="toggle mt-sm">
                <input type="checkbox" :checked="data.defaults.startup_sync"
                  @change="setDefault('startup_sync', $event.target.checked)">
                <div class="toggle-track"></div>
                <div class="toggle-thumb"></div>
              </label>
            </div>
            <div class="fill">
              <div class="kicker">Sync Path</div>
              <div class="mono mt-sm">{{ data.sync_path || 'Not configured' }}</div>
            </div>
          </div>
        </div>

        <!-- Instance table -->
        <div class="card fill" style="overflow:hidden">
          <div class="card-header">
            <span class="kicker">Instances</span>
            <span class="h2">Instance Sync · {{ data.instances.length }}</span>
          </div>
          <div style="overflow-y:auto; flex:1">
            <table class="table" style="width:100%">
              <thead>
                <tr>
                  <th style="width:240px">Instance</th>
                  <th style="width:120px">Exit Sync</th>
                  <th style="width:120px">Startup Sync</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="inst in data.instances" :key="inst.name">
                  <td>
                    <div class="flex items-center gap-sm">
                      <div class="avatar">{{ initials(inst.name) }}</div>
                      <span class="text-0">{{ inst.name }}</span>
                    </div>
                  </td>
                  <td>
                    <label class="toggle">
                      <input type="checkbox" :checked="inst.exit_sync"
                        @change="setOverride(inst.name, 'exit_sync', $event.target.checked)">
                      <div class="toggle-track"></div>
                      <div class="toggle-thumb"></div>
                    </label>
                  </td>
                  <td>
                    <label class="toggle">
                      <input type="checkbox" :checked="inst.startup_sync"
                        @change="setOverride(inst.name, 'startup_sync', $event.target.checked)">
                      <div class="toggle-track"></div>
                      <div class="toggle-thumb"></div>
                    </label>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </div>
  `
}
```

- [ ] **Step 2: Launch and verify**

Run: `venv\Scripts\python main.py`, click Instance Sync.
Expected: Defaults card with toggle switches. Instance table with per-row toggles. Toggling saves immediately.

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/instance_sync.js
git commit -m "feat: implement Instance Sync page with defaults card and instance table"
```

---

### Task 8: Pack Registry page component

**Files:**
- Rewrite: `frontend/pages/pack_registry.js`

- [ ] **Step 1: Rewrite frontend/pages/pack_registry.js**

```js
import { ref, onMounted, computed } from '../vue.esm-browser.js'

const PUBLISH_STEPS = ['Build zip', 'Upload pack', 'Upload metadata']
const STEP_ICONS = { pending: '◌', running: '⟳', ok: '✓', error: '✗' }
const STEP_COLORS = { pending: 'var(--text-3)', running: 'var(--accent)', ok: 'var(--ok)', error: 'var(--err)' }

const CATEGORY_LABELS = {
  mods: 'Mods', config: 'Config', resourcepacks: 'Resource Packs',
  shaderpacks: 'Shader Packs', saves: 'Saves', screenshots: 'Screenshots',
}

export default {
  props: ['progress'],
  setup(props) {
    const activeTab = ref('repos')

    // ── Repos tab ──────────────────────────────────────────────────
    const repos = ref([])
    const selectedRepo = ref(null)
    const repoForm = ref({ id: null, name: '', url: '', pat_token: '', package_name: 'mc-packs' })
    const repoStatus = ref('')
    const savingRepo = ref(false)

    const loadRepos = async () => {
      repos.value = await window.pywebview.api.get_repos()
    }

    const selectRepo = (repo) => {
      selectedRepo.value = repo
      repoForm.value = { id: repo.id, name: repo.name, url: repo.base_url + '/' + repo.project_id, pat_token: repo.read_token || '', package_name: repo.package_name || 'mc-packs' }
      repoStatus.value = ''
    }

    const newRepo = () => {
      selectedRepo.value = null
      repoForm.value = { id: null, name: '', url: '', pat_token: '', package_name: 'mc-packs' }
      repoStatus.value = ''
    }

    const saveRepo = async () => {
      savingRepo.value = true
      repoStatus.value = 'Resolving project ID…'
      try {
        const saved = await window.pywebview.api.save_repo({ ...repoForm.value })
        repoStatus.value = `Saved. Project ID: ${saved.project_id}`
        await loadRepos()
      } catch (e) {
        repoStatus.value = `Error: ${e}`
      } finally {
        savingRepo.value = false
      }
    }

    const deleteRepo = async () => {
      if (!selectedRepo.value) return
      await window.pywebview.api.delete_repo(selectedRepo.value.id)
      newRepo()
      await loadRepos()
    }

    // ── Publish tab ────────────────────────────────────────────────
    const instances = ref([])
    const publishRepoId = ref('')
    const publishInst = ref('')
    const categories = ref(Object.fromEntries(Object.keys(CATEGORY_LABELS).map(k => [k, k === 'mods' || k === 'config'])))
    const meta = ref({ description: '', mc_version: '', loader: '' })
    const publishSteps = ref(PUBLISH_STEPS.map(l => ({ label: l, state: 'pending', detail: '' })))
    const publishSummary = ref(null)
    const publishing = ref(false)

    const loadPublishData = async () => {
      instances.value = await window.pywebview.api.get_all_instances()
      if (instances.value.length) {
        publishInst.value = instances.value[0]
        await loadInstanceMeta(publishInst.value)
      }
      if (repos.value.length) publishRepoId.value = repos.value[0].id
    }

    const loadInstanceMeta = async (name) => {
      const m = await window.pywebview.api.read_instance_meta(name)
      meta.value.mc_version = m.mc_version
      meta.value.loader = m.loader
    }

    const doPublish = async () => {
      publishing.value = true
      publishSteps.value = PUBLISH_STEPS.map(l => ({ label: l, state: 'pending', detail: '' }))
      publishSummary.value = null
      await window.pywebview.api.publish_pack({
        repo_id: publishRepoId.value,
        instance_name: publishInst.value,
        categories: categories.value,
        metadata: meta.value,
      })
    }

    // ── Browse tab ─────────────────────────────────────────────────
    const browseRepoId = ref('')
    const packs = ref([])
    const selectedPack = ref(null)
    const versions = ref([])
    const selectedVer = ref(null)
    const browseInst = ref('')
    const loadingPacks = ref(false)

    const loadPacks = async () => {
      if (!browseRepoId.value) return
      loadingPacks.value = true
      packs.value = await window.pywebview.api.get_packs(browseRepoId.value)
      loadingPacks.value = false
      selectedPack.value = null
      versions.value = []
      selectedVer.value = null
    }

    const selectPack = async (name) => {
      selectedPack.value = name
      versions.value = await window.pywebview.api.get_versions(browseRepoId.value, name)
      selectedVer.value = null
    }

    const doInstall = async () => {
      if (!selectedPack.value || !selectedVer.value || !browseInst.value) return
      await window.pywebview.api.install_pack({
        repo_id: browseRepoId.value,
        pack_name: selectedPack.value,
        version: selectedVer.value,
        instance_name: browseInst.value,
      })
    }

    // Progress event handler for publish
    const origHandler = window.__onProgress
    window.__onProgress = (event) => {
      if (origHandler) origHandler(event)
      if (activeTab.value !== 'publish') return
      if (event.type === 'reset') {
        publishSteps.value = PUBLISH_STEPS.map(l => ({ label: l, state: 'pending', detail: '' }))
        publishSummary.value = null
      } else if (event.type === 'step') {
        if (publishSteps.value[event.step]) {
          publishSteps.value[event.step].state = event.state
          publishSteps.value[event.step].detail = event.detail || ''
        }
      } else if (event.type === 'summary') {
        publishSummary.value = event
        publishing.value = false
      }
    }

    onMounted(async () => {
      await loadRepos()
      await loadPublishData()
      if (repos.value.length) browseRepoId.value = repos.value[0].id
      if (instances.value.length) browseInst.value = instances.value[0]
    })

    return {
      activeTab, repos, selectedRepo, repoForm, repoStatus, savingRepo,
      selectRepo, newRepo, saveRepo, deleteRepo,
      instances, publishRepoId, publishInst, categories, meta, CATEGORY_LABELS,
      publishSteps, publishSummary, publishing, doPublish, loadInstanceMeta,
      browseRepoId, packs, selectedPack, versions, selectedVer, browseInst,
      loadingPacks, loadPacks, selectPack, doInstall,
      STEP_ICONS, STEP_COLORS,
    }
  },
  template: `
    <div class="page">
      <div class="page-heading">
        <div class="page-heading-row">
          <div>
            <span class="kicker">Pack Registry</span>
            <h1 class="h1">Pack Registry</h1>
          </div>
          <div class="sub-tabs">
            <button class="sub-tab" :class="{ active: activeTab === 'repos' }" @click="activeTab = 'repos'">Repos</button>
            <button class="sub-tab" :class="{ active: activeTab === 'publish' }" @click="activeTab = 'publish'">Publish</button>
            <button class="sub-tab" :class="{ active: activeTab === 'browse' }" @click="activeTab = 'browse'">Browse & Install</button>
          </div>
        </div>
      </div>

      <!-- Repos tab -->
      <div v-if="activeTab === 'repos'" class="two-col fill">
        <div class="col-left card flex-col" style="width:240px">
          <div class="card-header"><span class="kicker">Repos</span></div>
          <div class="list-scroll">
            <div v-for="repo in repos" :key="repo.id"
              class="list-item" :class="{ active: selectedRepo && selectedRepo.id === repo.id }"
              @click="selectRepo(repo)">{{ repo.name }}</div>
          </div>
          <div class="card-body flex gap-sm">
            <button class="btn-ghost sm" @click="newRepo">+ New</button>
            <button class="btn-ghost sm" @click="deleteRepo">✕ Delete</button>
          </div>
        </div>

        <div class="col-right card">
          <div class="card-header"><span class="kicker">Repository</span></div>
          <div class="card-body flex-col gap-sm">
            <div v-for="(label, key) in { name: 'Name', url: 'GitLab Project URL', pat_token: 'PAT Token', package_name: 'Package Name' }" :key="key">
              <div class="kicker">{{ label }}</div>
              <input class="input mt-sm" :type="key === 'pat_token' ? 'password' : 'text'"
                v-model="repoForm[key]" :placeholder="key === 'url' ? 'https://gitlab.example.com/group/project' : ''">
            </div>
            <div class="secondary">Project ID resolves automatically from the URL</div>
            <div v-if="repoStatus" class="secondary" :style="{ color: repoStatus.startsWith('Error') ? 'var(--err)' : 'var(--text-3)' }">{{ repoStatus }}</div>
            <div class="flex gap-sm mt-sm">
              <button class="btn-ghost sm" @click="newRepo">Cancel</button>
              <button class="btn-primary sm" :disabled="savingRepo" @click="saveRepo">
                {{ savingRepo ? 'Saving…' : '✓ Save' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Publish tab -->
      <div v-if="activeTab === 'publish'" class="two-col fill">
        <div class="col-left card" style="min-width:320px;max-width:360px">
          <div class="card-header"><span class="kicker">Publish</span><span class="h2">Build & upload pack</span></div>
          <div class="card-body flex-col gap-sm">
            <div>
              <div class="kicker">Repository</div>
              <select class="input mt-sm" v-model="publishRepoId">
                <option v-for="r in repos" :key="r.id" :value="r.id">{{ r.name }}</option>
              </select>
            </div>
            <div>
              <div class="kicker">Instance</div>
              <select class="input mt-sm" v-model="publishInst" @change="loadInstanceMeta(publishInst)">
                <option v-for="i in instances" :key="i" :value="i">{{ i }}</option>
              </select>
            </div>
            <div>
              <div class="kicker">Include</div>
              <div class="flex-col gap-sm mt-sm">
                <label v-for="(label, key) in CATEGORY_LABELS" :key="key" class="flex items-center gap-sm" style="cursor:pointer">
                  <input type="checkbox" v-model="categories[key]">
                  <span>{{ label }}</span>
                </label>
              </div>
            </div>
            <div v-for="(label, key) in { description: 'Description', mc_version: 'MC Version', loader: 'Loader' }" :key="key">
              <div class="kicker">{{ label }}</div>
              <input class="input mt-sm" v-model="meta[key]">
            </div>
            <div class="secondary">MC Version and Loader auto-detected from instance</div>
            <button class="btn-primary sm" :disabled="publishing" @click="doPublish">
              {{ publishing ? '⟳ Publishing…' : '↑ Publish' }}
            </button>
          </div>
        </div>

        <div class="col-right card fill">
          <div class="card-header"><span class="kicker">Progress</span></div>
          <div class="progress-panel">
            <div v-for="(step, i) in publishSteps" :key="i" class="progress-row">
              <span class="progress-icon" :style="{ color: STEP_COLORS[step.state] }">{{ STEP_ICONS[step.state] }}</span>
              <span class="progress-label">{{ step.label }}</span>
              <span class="progress-detail">{{ step.detail }}</span>
            </div>
          </div>
          <div v-if="publishSummary" class="progress-summary"
            :style="{ color: publishSummary.tone === 'ok' ? 'var(--ok)' : 'var(--err)' }">
            {{ publishSummary.text }}
          </div>
        </div>
      </div>

      <!-- Browse & Install tab -->
      <div v-if="activeTab === 'browse'" class="flex-col fill gap-md">
        <div class="flex items-center gap-sm">
          <span class="kicker">Repository</span>
          <select class="input" style="width:240px" v-model="browseRepoId" @change="loadPacks">
            <option v-for="r in repos" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
          <button class="btn-ghost sm" @click="loadPacks">↻ Refresh</button>
        </div>

        <div class="two-col fill">
          <div class="col-left card flex-col" style="width:240px">
            <div class="card-header"><span class="kicker">Packs</span></div>
            <div class="list-scroll">
              <div v-if="loadingPacks" class="loading">Loading…</div>
              <div v-for="pack in packs" :key="pack"
                class="list-item" :class="{ active: selectedPack === pack }"
                @click="selectPack(pack)">{{ pack }}</div>
            </div>
          </div>

          <div class="col-right card flex-col fill">
            <div class="card-header"><span class="kicker">Versions</span></div>
            <div class="list-scroll">
              <div v-if="!selectedPack" class="empty">Select a pack</div>
              <div v-for="ver in versions" :key="ver"
                class="list-item" :class="{ active: selectedVer === ver }"
                @click="selectedVer = ver">{{ ver }}</div>
            </div>
            <div class="card-body flex items-center gap-sm" style="border-top:1px solid var(--line)">
              <select class="input fill" v-model="browseInst">
                <option v-for="i in instances" :key="i" :value="i">{{ i }}</option>
              </select>
              <button class="btn-primary sm" :disabled="!selectedPack || !selectedVer || !browseInst" @click="doInstall">
                ↓ Install
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
}
```

- [ ] **Step 2: Launch and verify**

Run: `venv\Scripts\python main.py`, click Pack Registry.
Expected: Repos/Publish/Browse tabs work. Repos tab shows form with URL field. Publish shows left form + right progress panel. Browse shows pack list + version list.

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/pack_registry.js
git commit -m "feat: implement Pack Registry page with Repos/Publish/Browse tabs"
```

---

### Task 9: Update build pipeline

**Files:**
- Modify: `MCAddonCompanion.spec`
- Modify: `.gitlab-ci.yml`
- Modify: `installer.iss`

- [ ] **Step 1: Update MCAddonCompanion.spec**

Replace the contents of `MCAddonCompanion.spec` with:

```python
from pathlib import Path

datas = [("frontend", "frontend")]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["webview", "webview.platforms.winforms"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["venv", "customtkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MCAddonCompanion",
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MCAddonCompanion",
)
```

- [ ] **Step 2: Update .gitlab-ci.yml build_linux**

Find the `build_linux` before_script section and replace with:

```yaml
build_linux:
  extends: .build_common
  image: python:3.11-slim-bullseye
  before_script:
    - apt-get update -qq
    - apt-get install -y -qq git binutils libwebkit2gtk-4.1-dev python3-gi gir1.2-webkit2-4.1 libgtk-3-dev
    - pip install --upgrade pip --quiet
    - pip install pyinstaller pywebview --quiet
    - echo "BUILD_SHA = '${CI_COMMIT_SHA}'" > core/_build_info.py
```

- [ ] **Step 3: Verify spec builds locally**

Run: `venv\Scripts\pyinstaller MCAddonCompanion.spec --clean --distpath dist_windows`
Expected: `dist_windows/MCAddonCompanion/` directory created with `MCAddonCompanion.exe` and `frontend/` inside.

- [ ] **Step 4: Verify built exe launches**

Run: `dist_windows\MCAddonCompanion\MCAddonCompanion.exe`
Expected: App opens with PyWebView window showing the SPA.

- [ ] **Step 5: Commit**

```bash
git add MCAddonCompanion.spec .gitlab-ci.yml
git commit -m "feat: update PyInstaller spec and CI for pywebview build"
```

---

### Task 10: Run full test suite and push

- [ ] **Step 1: Run all tests**

Run: `venv\Scripts\pytest tests/ -v`
Expected: All tests pass. (test_ui_tokens.py may fail — delete it, CTk is gone.)

- [ ] **Step 2: Delete obsolete test and source files**

```bash
git rm tests/test_ui_tokens.py
git rm -r modules/schematic_sync/page.py modules/instance_sync/page.py modules/pack_registry/page.py
git rm core/ui.py core/progress.py
git rm -r assets/
```

Note: Keep `core/sharing.py`, `modules/instance_sync/sync.py`, `modules/schematic_sync/page.py` (the `run_autosync` function is still used by `main.py`).

Actually — do NOT delete `modules/schematic_sync/page.py`. It contains `run_autosync()` which `main.py` imports. Only delete the `SchematicSyncModule` class and the CTk UI code from it; keep `run_autosync` and the data functions.

Safer: just delete `core/ui.py`, `core/progress.py`, `tests/test_ui_tokens.py`, and `assets/`. Leave module page.py files for now.

```bash
git rm core/ui.py core/progress.py tests/test_ui_tokens.py
git rm -r assets/
git add -A
git commit -m "chore: remove CTk design system and assets, keep module data functions"
```

- [ ] **Step 3: Run tests again**

Run: `venv\Scripts\pytest tests/ -v`
Expected: All remaining tests pass.

- [ ] **Step 4: Push to both remotes**

```bash
git push gitlab main
git push origin main
```

- [ ] **Step 5: Tag and release**

```bash
git tag v0.2.0-alpha
git push gitlab refs/tags/v0.2.0-alpha
git push origin refs/tags/v0.2.0-alpha
```

Expected: GitLab pipeline triggers, builds Linux binary, creates GitHub pre-release. GitHub Actions triggers, builds Windows installer.

---

## Self-Review

**Spec coverage check:**
- ✅ SPA shell (index.html + style.css + app.js) — Task 2
- ✅ Vue 3 ESM bundle — Task 1
- ✅ Python Api class with all methods — Task 4
- ✅ Progress streaming via `window.__onProgress` — Task 4 + Tasks 6/7/8
- ✅ Home page — Task 5
- ✅ Schematic Sync page — Task 6
- ✅ Instance Sync page — Task 7
- ✅ Pack Registry (Repos/Publish/Browse) — Task 8
- ✅ PyInstaller spec update — Task 9
- ✅ GitLab CI webkit2gtk deps — Task 9
- ✅ Headless CLI paths preserved — Task 4

**No placeholders found.**

**Type consistency:** All Api method names match between `main.py` (Task 4) and JS calls in page components (Tasks 5-8). `window.pywebview.api.get_home_data()`, `get_schematic_data()`, `get_instance_sync_data()`, `get_repos()`, etc. are consistent throughout.
