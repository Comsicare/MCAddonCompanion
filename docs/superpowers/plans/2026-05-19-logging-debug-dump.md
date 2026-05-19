# Logging & Debug Dump Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Python logging to `%LOCALAPPDATA%\MCAddonCompanion\logs\`, add a JS-side error capture + API call proxy that forwards to Python, add the missing v0.3.0 API methods (`get_host_info`, `open_instances_folder`, `reset_module`, `get_instance_settings`, `save_instance_settings`), and wire a working "Save Debug Dump" button in the Help & Debug modal.

**Architecture:** `_configure_logging()` in `main.py` is replaced to write to `logs/` under `%LOCALAPPDATA%`. A new `logging.getLogger("js")` writes JS errors to a separate `js_errors.log`. The JS side wraps `window.pywebview.api` in a `Proxy` after `pywebviewready` to trace every call automatically. A `create_debug_dump()` Python method zips logs + redacted state + system info into Downloads. Missing v0.3.0 API methods are added to `main.py` so the gear modal and Help & Debug modal fully work.

**Tech Stack:** Python `logging.handlers.RotatingFileHandler`, JS `Proxy`, `zipfile`, `os.startfile()`, Vue 3 ESM (no build step).

---

## Repo & Key Paths

- Repo: `C:\Users\comsi\Nextcloud\Dev\MCAddonCompanion\`
- Entry: `main.py` — `_configure_logging()` at line 11, called at line 35
- Frontend: `frontend/app.js` — `pywebviewready` listener at line 43, `createApp` at line 384
- State file (dev): `state.json` in repo root
- State file (frozen): `%APPDATA%\MCAddonCompanion\state.json`
- Current log (to be moved): `%APPDATA%\MCAddonCompanion\mcaddoncompanion.log`
- New log folder: `%LOCALAPPDATA%\MCAddonCompanion\logs\`

## Branch

All work goes on the current branch: `release/0.2.2-alpha`.

## No Tests

This project has no test suite. Skip all test steps. Verify by running `python main.py` from the repo root and checking behaviour manually.

---

## File Map

| File | What changes |
|---|---|
| `main.py` | Replace `_configure_logging()`; add `log_js_error`, `__raw_log`, `create_debug_dump`, `get_host_info`, `open_instances_folder`, `reset_module`, `get_instance_settings`, `save_instance_settings` to `Api` class |
| `frontend/app.js` | Replace `pywebviewready` listener with proxy-wrapping version; add `window.onerror`, `unhandledrejection`, Vue `errorHandler`; wire debug dump button in Help & Debug modal; add `dumpState`/`dumpError` refs |

No other files need changes. `core/prism.py` already has `get_minecraft_dir`. `core/state.py`, `core/gitlab.py`, `core/updater.py`, `modules/instance_sync/sync.py` already have loggers and fixed handlers based on the explore results.

---

## Task 1: Replace `_configure_logging()` in `main.py`

**Files:**
- Modify: `main.py` lines 11–32

Replace the existing `_configure_logging()` function (lines 11–32). The new version writes to `%LOCALAPPDATA%\MCAddonCompanion\logs\` and sets up a separate `js` logger for `js_errors.log`.

- [ ] **Step 1: Replace `_configure_logging` in `main.py`**

Replace lines 11–32 (the entire `_configure_logging` function body) with:

```python
def _configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    if sys.platform == "win32":
        log_dir = pathlib.Path(os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA", "."))) / "MCAddonCompanion" / "logs"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", str(pathlib.Path.home() / ".local/share"))
        log_dir = pathlib.Path(xdg) / "MCAddonCompanion" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.handlers.RotatingFileHandler(
        log_dir / "mcaddoncompanion.log",
        maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)

    # JS errors go to a separate file so they don't pollute the main log
    js_fh = logging.handlers.RotatingFileHandler(
        log_dir / "js_errors.log",
        maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    js_fh.setFormatter(fmt)
    js_log = logging.getLogger("js")
    js_log.addHandler(js_fh)
    js_log.propagate = False  # don't echo JS noise into main log

    if not getattr(sys, "frozen", False):
        root.addHandler(logging.StreamHandler())
```

- [ ] **Step 2: Add module-level logger after `_configure_logging()` call**

After line 35 (`_configure_logging()`), add:

```python
log = logging.getLogger(__name__)
```

- [ ] **Step 3: Verify log folder is created on launch**

Run: `python main.py` — close immediately. Then check that `%LOCALAPPDATA%\MCAddonCompanion\logs\mcaddoncompanion.log` and `js_errors.log` both exist.

Expected: both files present in `C:\Users\comsi\AppData\Local\MCAddonCompanion\logs\`

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: move logging to %LOCALAPPDATA%/MCAddonCompanion/logs with separate js_errors.log"
```

---

## Task 2: Add missing v0.3.0 API methods to `main.py`

**Files:**
- Modify: `main.py` — `Api` class (add after `set_gitlab_pat_api` which is around line 598)

These five methods are called by the frontend (gear modal, Help & Debug modal, open folder button) but are missing from `main.py`. Without them the UI silently fails. Add them all in one block.

- [ ] **Step 1: Find the right insertion point**

Open `main.py`. Search for `def set_gitlab_pat_api`. The new methods go immediately after it.

- [ ] **Step 2: Add `get_host_info`**

```python
def get_host_info(self) -> dict:
    import platform
    from core.config import VERSION, INSTANCES_DIR, STATEFILE
    return {
        "version": VERSION,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "platform_version": platform.version(),
        "instances_dir": str(INSTANCES_DIR),
        "state_file": str(STATEFILE),
        "frozen": getattr(sys, "frozen", False),
    }
```

- [ ] **Step 3: Add `open_instances_folder`**

```python
def open_instances_folder(self) -> None:
    from core.config import INSTANCES_DIR
    import subprocess
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(INSTANCES_DIR)])
    else:
        subprocess.Popen(["xdg-open", str(INSTANCES_DIR)])
```

- [ ] **Step 4: Add `reset_module`**

```python
def reset_module(self, module: str) -> dict:
    from core.state import load_state, save_state
    valid = {"schematic_sync", "instance_sync", "pack_registry"}
    if module not in valid:
        return {"ok": False, "error": f"Unknown module: {module}"}
    try:
        state = load_state()
        state.pop(module, None)
        save_state(state)
        log.info("reset_module: cleared state for %s", module)
        return {"ok": True}
    except Exception as e:
        log.error("reset_module failed for %s: %s", module, e)
        return {"ok": False, "error": str(e)}
```

- [ ] **Step 5: Add `get_instance_settings`**

```python
def get_instance_settings(self, instance_name: str) -> dict:
    from core.state import load_state
    from core.config import INSTANCES_DIR
    state = load_state()
    is_cfg = state.get("instance_sync", {})
    instances = is_cfg.get("instances", {})
    inst = instances.get(instance_name, {})
    sc_cfg = state.get("schematic_sync", {})
    sc_instances = sc_cfg.get("instances", {})
    sc_inst = sc_instances.get(instance_name, {})
    tracked = state.get("tracked_packs", {})
    installed = state.get("installed_instances", {})
    inst_installed = installed.get(instance_name)
    pack_name = inst_installed.get("pack_name") if inst_installed else None
    return {
        "schematic_sync": bool(sc_inst.get("enabled", False)),
        "exit_sync": bool(inst.get("exit_sync", False)),
        "startup_sync": bool(inst.get("startup_sync", False)),
        "hook_enabled": bool(inst.get("hook_enabled", False)),
        "tracked": instance_name in tracked,
        "installed": inst_installed is not None,
        "pack_name": pack_name,
    }
```

- [ ] **Step 6: Add `save_instance_settings`**

```python
def save_instance_settings(self, instance_name: str, settings: dict) -> dict:
    from core.state import load_state, save_state
    from core.config import INSTANCES_DIR
    from core.prism import patch_exit_commands, clear_exit_commands
    try:
        state = load_state()

        # Schematic sync
        sc_cfg = state.setdefault("schematic_sync", {})
        sc_instances = sc_cfg.setdefault("instances", {})
        sc_inst = sc_instances.setdefault(instance_name, {})
        sc_inst["enabled"] = bool(settings.get("schematic_sync", False))

        # Instance sync toggles
        is_cfg = state.setdefault("instance_sync", {})
        instances = is_cfg.setdefault("instances", {})
        inst = instances.setdefault(instance_name, {})
        inst["exit_sync"] = bool(settings.get("exit_sync", False))
        inst["startup_sync"] = bool(settings.get("startup_sync", False))

        # Hook
        hook_enabled = bool(settings.get("hook_enabled", False))
        inst["hook_enabled"] = hook_enabled
        main_script = Path(__file__).resolve()
        if hook_enabled:
            patch_exit_commands([instance_name], main_script, INSTANCES_DIR)
        else:
            clear_exit_commands([instance_name], INSTANCES_DIR)

        # Track for updates
        tracked = state.setdefault("tracked_packs", {})
        if settings.get("tracked"):
            installed = state.get("installed_instances", {})
            inst_info = installed.get(instance_name, {})
            if inst_info:
                tracked[instance_name] = inst_info
        else:
            tracked.pop(instance_name, None)

        save_state(state)
        log.info("save_instance_settings: saved settings for %s", instance_name)
        return self.get_instance_settings(instance_name)
    except Exception as e:
        log.error("save_instance_settings failed for %s: %s", instance_name, e)
        return {"error": str(e)}
```

- [ ] **Step 7: Verify app starts without errors**

Run: `python main.py` — open the app, click the gear icon on any instance. The quick settings modal should open and show toggles.

- [ ] **Step 8: Commit**

```bash
git add main.py
git commit -m "feat: add missing v0.3.0 API methods (get_host_info, open_instances_folder, reset_module, get/save_instance_settings)"
```

---

## Task 3: Add `log_js_error`, `__raw_log`, `create_debug_dump` to `main.py`

**Files:**
- Modify: `main.py` — `Api` class (add after `save_instance_settings`)

- [ ] **Step 1: Add `log_js_error` and `__raw_log`**

```python
def log_js_error(self, level: str, message: str) -> None:
    js_log = logging.getLogger("js")
    lvl = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }.get(str(level).lower(), logging.ERROR)
    js_log.log(lvl, message)

def __raw_log(self, level: str, message: str) -> None:
    """Direct log bypass used by the JS API proxy — must not be wrapped by the proxy itself."""
    self.log_js_error(level, message)
```

- [ ] **Step 2: Add `create_debug_dump`**

```python
def create_debug_dump(self) -> dict:
    import zipfile
    import json as _json
    from datetime import datetime

    try:
        # Resolve paths
        if sys.platform == "win32":
            log_dir = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "MCAddonCompanion" / "logs"
            state_path = pathlib.Path(os.environ.get("APPDATA", ".")) / "MCAddonCompanion" / "state.json"
        else:
            xdg = os.environ.get("XDG_DATA_HOME", str(pathlib.Path.home() / ".local/share"))
            log_dir = pathlib.Path(xdg) / "MCAddonCompanion" / "logs"
            state_path = log_dir.parent / "state.json"

        # Also check local state.json (dev mode)
        local_state = pathlib.Path(__file__).parent / "state.json"
        if local_state.exists():
            state_path = local_state

        downloads = pathlib.Path.home() / "Downloads"
        downloads.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        zip_name = f"mcaddoncompanion-debug-{ts}.zip"
        zip_path = downloads / zip_name

        def _redact(obj):
            """Recursively redact sensitive keys."""
            if isinstance(obj, dict):
                return {
                    k: "***" if any(s in k.lower() for s in ("pat", "token", "secret", "password"))
                    else _redact(v)
                    for k, v in obj.items()
                }
            if isinstance(obj, list):
                return [_redact(i) for i in obj]
            return obj

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Logs
            if log_dir.exists():
                for f in log_dir.iterdir():
                    if f.is_file():
                        zf.write(f, f"logs/{f.name}")

            # Redacted state
            if state_path.exists():
                try:
                    raw = _json.loads(state_path.read_text(encoding="utf-8"))
                    redacted = _redact(raw)
                    zf.writestr("state_redacted.json", _json.dumps(redacted, indent=2))
                except Exception as e:
                    zf.writestr("state_redacted.json", f"{{\"error\": \"{e}\"}}")

            # System info
            info = self.get_host_info()
            info["dump_timestamp"] = datetime.now().isoformat()
            zf.writestr("system_info.json", _json.dumps(info, indent=2))

        log.info("Debug dump created: %s", zip_path)

        # Open Downloads folder
        if sys.platform == "win32":
            import subprocess
            subprocess.Popen(["explorer", str(downloads)])

        return {"ok": True, "filename": zip_name}

    except Exception as e:
        log.error("create_debug_dump failed: %s", e)
        return {"ok": False, "error": str(e)}
```

- [ ] **Step 3: Verify app starts without errors**

Run: `python main.py` — open Help & Debug. The "Upload Debug Data" placeholder should still show (we wire the button in Task 4). Check that no import errors appear in the terminal.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add log_js_error, __raw_log, create_debug_dump API methods"
```

---

## Task 4: JS error capture + API proxy + debug dump button in `frontend/app.js`

**Files:**
- Modify: `frontend/app.js`

Four changes to `app.js`:

1. Replace the `pywebviewready` listener (line 43) with a version that also installs the API proxy
2. Add `window.onerror` and `unhandledrejection` handlers before `createApp`
3. Add Vue `errorHandler` after `createApp`
4. Replace the "Upload Debug Data" placeholder in the Help & Debug modal with a working button

- [ ] **Step 1: Replace the `pywebviewready` listener**

Find this in `app.js` (line 43):
```js
window.addEventListener('pywebviewready', () => __apiReadyResolve())
```

Replace with:
```js
window.addEventListener('pywebviewready', () => {
  __apiReadyResolve()
  // Wrap API with a logging proxy — traces every call to js_errors.log
  const _raw = window.pywebview.api
  window.pywebview.api = new Proxy(_raw, {
    get(target, method) {
      const fn = target[method]
      if (typeof fn !== 'function') return fn
      // Don't proxy the raw log bypass itself (infinite loop guard)
      if (method === '__raw_log' || method === 'log_js_error') return fn.bind(target)
      return (...args) => {
        const argStr = JSON.stringify(args).slice(0, 300)
        _raw.__raw_log('debug', `api.call method=${method} args=${argStr}`).catch(() => {})
        return fn.apply(target, args).then(result => {
          _raw.__raw_log('debug', `api.result method=${method}`).catch(() => {})
          return result
        }).catch(err => {
          _raw.__raw_log('error', `api.error method=${method} error=${err}`).catch(() => {})
          throw err
        })
      }
    }
  })
})
```

- [ ] **Step 2: Add global error capture**

Find the line in `app.js`:
```js
const PAGES = {
```

Insert immediately before it:
```js
// Global unhandled error capture — forwards to js_errors.log via Python
window.onerror = (msg, src, line, col, err) => {
  const text = `${msg} (${src}:${line}:${col})${err ? ' ' + err.stack : ''}`
  window.__apiReady.then(() => window.pywebview.api.log_js_error('error', '[onerror] ' + text).catch(() => {}))
}
window.addEventListener('unhandledrejection', e => {
  const text = String(e.reason?.stack || e.reason || e)
  window.__apiReady.then(() => window.pywebview.api.log_js_error('error', '[unhandledrejection] ' + text).catch(() => {}))
})

```

- [ ] **Step 3: Add Vue `errorHandler` and `dumpState` refs to `App` setup and template**

**In the `setup()` function of the `App` component**, add these refs after `gitlabPat`:
```js
const dumpState = ref(null) // null | {running:true} | {ok:true,filename:str} | {ok:false,error:str}
const createDump = async () => {
  dumpState.value = { running: true }
  try {
    await window.__apiReady
    const r = await window.pywebview.api.create_debug_dump()
    dumpState.value = r
  } catch(e) {
    dumpState.value = { ok: false, error: String(e) }
  }
}
```

Add `dumpState, createDump` to the `return` statement of `setup()`.

- [ ] **Step 4: Replace the debug dump placeholder in the template**

Find in the template:
```js
              <div style="margin-top:10px;padding:8px 12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--line)">
                <div class="fs-13 fw-500 text-0" style="margin-bottom:6px">Upload Debug Data</div>
                <div class="fs-12 text-3">Collect and share logs with support.</div>
              </div>
```

Replace with:
```js
              <div style="margin-top:10px;padding:8px 12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--line)">
                <div class="fs-13 fw-500 text-0" style="margin-bottom:6px">Debug Dump</div>
                <div class="fs-12 text-3" style="margin-bottom:8px">Saves a zip with logs, redacted config, and system info to your Downloads folder.</div>
                <button class="btn btn-ghost btn-sm" :disabled="dumpState && dumpState.running" @click="createDump">
                  <span v-html="icon('download', 12)"></span>
                  {{ dumpState && dumpState.running ? 'Creating…' : 'Save Debug Dump' }}
                </button>
                <div v-if="dumpState && !dumpState.running" style="margin-top:6px" :style="dumpState.ok ? 'color:var(--ok)' : 'color:var(--err)'" class="fs-12">
                  <template v-if="dumpState.ok">Saved: {{ dumpState.filename }} — Downloads folder opened</template>
                  <template v-else>Error: {{ dumpState.error }}</template>
                </div>
              </div>
```

- [ ] **Step 5: Add Vue `errorHandler` after `createApp`**

Find:
```js
createApp(App)
  .component('update-prompt-page', UpdatePromptPage)
  .mount('#app')
```

Replace with:
```js
const app = createApp(App)
app.config.errorHandler = (err, _instance, info) => {
  const text = `${info}: ${err?.stack || err}`
  window.__apiReady.then(() => window.pywebview.api.log_js_error('error', '[vue] ' + text).catch(() => {}))
  console.error('[vue errorHandler]', err)
}
app.component('update-prompt-page', UpdatePromptPage).mount('#app')
```

- [ ] **Step 6: Verify**

Run: `python main.py`. Open Help & Debug. Confirm:
- Host info table loads
- "Save Debug Dump" button appears
- Click it — Downloads folder should open with a zip file
- Open the zip — should contain `logs/`, `state_redacted.json`, `system_info.json`
- Check `C:\Users\comsi\AppData\Local\MCAddonCompanion\logs\js_errors.log` — should have `api.call` entries

Also test:
- Gear icon on an instance → quick settings modal opens
- Three-dot menu → Version & Updates → stream selector works
- Three-dot menu → Help & Debug → reset buttons work

- [ ] **Step 7: Commit**

```bash
git add frontend/app.js
git commit -m "feat: JS error capture, API call proxy, working debug dump button"
```

---

## Task 5: Copy frontend to installed app and do a full manual test

The installed app has a separate copy of the frontend. After JS changes, copy the updated files so the installed app is also up to date.

- [ ] **Step 1: Copy frontend files**

Run from the repo root (PowerShell or cmd):
```
copy frontend\app.js "%LOCALAPPDATA%\MCAddonCompanion\_internal\frontend\app.js"
```

No Python changes need copying — Python-side is only tested from source (`python main.py`) during development.

- [ ] **Step 2: Full test checklist**

Run `python main.py` from source and confirm all of these:

**Home page:**
- [ ] Gear icon on an instance → quick settings modal opens with correct toggles
- [ ] Toggling Schematic Sync, Hook, Exit Sync, Startup Sync and clicking Save → no error
- [ ] "Open" link in Launcher card → opens PrismLauncher instances folder in Explorer
- [ ] Clicking an instance row → expands detail panel (lazy loads)
- [ ] Detail panel Refresh button works

**Three-dot menu:**
- [ ] Menu opens on click, closes on outside click
- [ ] Version & Updates → shows version, stream selector pill (release/beta/alpha/dev)
- [ ] Help & Debug → host info table populated, reset buttons work, debug dump button works

**Logging:**
- [ ] `%LOCALAPPDATA%\MCAddonCompanion\logs\mcaddoncompanion.log` exists and has entries
- [ ] `%LOCALAPPDATA%\MCAddonCompanion\logs\js_errors.log` exists and has `api.call` entries

- [ ] **Step 3: Commit if any last-minute fixes were needed**

```bash
git add -A
git commit -m "fix: <describe any fixes found during manual test>"
```

Skip this step if no fixes were needed.
