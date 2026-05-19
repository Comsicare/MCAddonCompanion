# Logging & Debug Dump Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extensive Python + JS logging to a central `logs/` folder, with a one-click debug dump zip for sharing with support.

**Architecture:** Log folder moves to `%LOCALAPPDATA%\MCAddonCompanion\logs\`. Python logging audit from the prior spec is folded in. JS errors and API call traces are captured automatically and written to a separate `js_errors.log` via a `log_js_error()` Python API method. A `create_debug_dump()` API method builds a timestamped zip (logs + redacted state + system info) and opens the user's Downloads folder.

**Tech Stack:** Python `logging` + `logging.handlers.RotatingFileHandler`, JS `Proxy` for API tracing, `zipfile` for dump, `os.startfile()` for delivery.

---

## Scope

This spec folds in and supersedes the Python-side logging audit from `2026-05-11-logging-audit-design.md`. That spec is now fully incorporated here. Do not implement the old spec separately.

Out of scope: live log viewer in UI, log level toggle, upload to GitLab/external service.

---

## Section 1: Log Folder

**Location:** `%LOCALAPPDATA%\MCAddonCompanion\logs\`

Created on startup if it doesn't exist. In dev (unfrozen), same path — keeps dev and installed app logs in the same place.

**Files in `logs/`:**

| File | Writer | Rotation |
|---|---|---|
| `mcaddoncompanion.log` | Python root logger | 10 MB × 3 backups |
| `js_errors.log` | `logging.getLogger("js")` via `log_js_error()` | 2 MB × 2 backups |
| `update_install.log` | Updater batch script (already written here) | None (small) |

**Migration:** The existing log path (`%APPDATA%\MCAddonCompanion\mcaddoncompanion.log`) is replaced. No migration of old log content — old file is left in place and ignored.

---

## Section 2: Python Logging Configuration

Replaces the existing `_configure_logging()` in `main.py`:

```python
def _configure_logging():
    log_dir = Path(os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA", "."))) / "MCAddonCompanion" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Main log
    main_handler = logging.handlers.RotatingFileHandler(
        log_dir / "mcaddoncompanion.log",
        maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    main_handler.setFormatter(fmt)

    # JS errors log (separate logger, separate file)
    js_handler = logging.handlers.RotatingFileHandler(
        log_dir / "js_errors.log",
        maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    js_handler.setFormatter(fmt)
    js_log = logging.getLogger("js")
    js_log.addHandler(js_handler)
    js_log.propagate = False  # don't also write JS noise to main log

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(main_handler)

    if not getattr(sys, "frozen", False):
        root.addHandler(logging.StreamHandler())
```

`_configure_logging()` is called at the top of `main.py` before any other imports.

### Log levels

| Level | Used for |
|---|---|
| `DEBUG` | File scans, sync decisions, HTTP request URLs, API call traces from JS |
| `INFO` | User-triggered actions starting/completing (publish, install, sync, dump created) |
| `WARNING` | Non-critical failures where a safe default is returned |
| `ERROR` | Operation failures the user will notice; unhandled JS exceptions |

### One logger per module

Every Python module gets at the top:
```python
import logging
log = logging.getLogger(__name__)
```

---

## Section 3: Python Silent Exception Handler Fixes

Folds in all fixes from the prior logging audit spec.

### Log + return (non-critical)

| Location | Current | Fix |
|---|---|---|
| `core/updater.py` — `check_for_update` | `except Exception: return None` | `log.warning("Update check failed: %s", e); return None` |
| `core/updater.py` — `download_update` | `except Exception: return None` | `log.error("Download failed: %s", e); return None` |
| `core/gitlab.py` — `get_metadata` | `except Exception: return {}` | `log.debug("metadata fetch failed (may be absent): %s", e); return {}` |
| `core/prism.py` — `is_prism_running` | `except Exception: return False` | `log.warning("is_prism_running check failed: %s", e); return False` |
| `modules/instance_sync/sync.py` — `read_manifest` | `except Exception: return {}` | `log.warning("read_manifest failed: %s", e); return {}` |
| `modules/instance_sync/sync.py` — changelog read | `except Exception: existing = []` | `log.warning("changelog read failed: %s", e); existing = []` |
| `modules/instance_sharing/share.py` — `instance.cfg` parse | `except Exception: pass` | `log.debug("instance.cfg parse skipped: %s", e); pass` |
| `modules/schematic_sync/page.py` — state import | `except Exception: imported = None` | `log.warning("state import failed: %s", e); imported = None` |

### Log + keep safe default (state corruption)

| Location | Current | Fix |
|---|---|---|
| `core/state.py` — `load_state` JSON parse | `except Exception: return {}` | `log.error("state.json corrupted, returning empty state: %s", e); return {}` |

Keep safe default (don't raise) — crashing on startup due to bad state is worse than losing state.

### Improve response validation

`core/gitlab.py` — `_get()`: after `json.loads`, check `isinstance(result, (list, dict))`. If not, log first 200 chars of raw body at DEBUG and raise `GitLabError("Unexpected response format from GitLab API")`.

### Headless arg validation (`main.py`)

```python
if not instance_name:
    log.error("--autosync called with no instance name")
    sys.exit(1)
if not (INSTANCES_DIR / instance_name).is_dir():
    log.error("--autosync: instance '%s' not found in %s", instance_name, INSTANCES_DIR)
    sys.exit(1)
```

Same pattern for `--startup`.

### Consolidate `get_minecraft_dir`

Currently duplicated in `main.py`, `modules/instance_sharing/page.py`, `modules/pack_registry/page.py`. Move to `core/prism.py`:

```python
def get_minecraft_dir(instances_dir: Path, instance_name: str) -> Path | None:
    for sub in (".minecraft", "minecraft"):
        p = instances_dir / instance_name / sub
        if p.exists():
            return p
    return None
```

All three callers import from `core.prism`.

### Dead code removal

`modules/instance_sharing/share.py`:
- Remove `build_filtered_zip` (never called)
- Remove `launch_prism_import` (scrapped feature)

---

## Section 4: JS Logging

### `log_js_error(level, message)` — Python API method

Added to the `Api` class in `main.py`:

```python
def log_js_error(self, level: str, message: str) -> None:
    js_log = logging.getLogger("js")
    lvl = {"debug": logging.DEBUG, "info": logging.INFO,
           "warning": logging.WARNING, "error": logging.ERROR}.get(level, logging.ERROR)
    js_log.log(lvl, message)
```

### JS error capture — `frontend/app.js`

Added after `window.__apiReady` setup, before `createApp`:

```js
// Global unhandled error capture
window.onerror = (msg, src, line, col, err) => {
  const text = `${msg} (${src}:${line}:${col})${err ? ' ' + err.stack : ''}`
  window.__apiReady.then(() => window.pywebview.api.log_js_error('error', '[onerror] ' + text).catch(() => {}))
}
window.addEventListener('unhandledrejection', e => {
  const text = String(e.reason?.stack || e.reason || e)
  window.__apiReady.then(() => window.pywebview.api.log_js_error('error', '[unhandledrejection] ' + text).catch(() => {}))
})
```

Vue error handler added after `createApp(App)`:

```js
const app = createApp(App)
app.config.errorHandler = (err, instance, info) => {
  const text = `${info}: ${err?.stack || err}`
  window.__apiReady.then(() => window.pywebview.api.log_js_error('error', '[vue] ' + text).catch(() => {}))
  console.error('[vue errorHandler]', err)
}
app.component('update-prompt-page', UpdatePromptPage).mount('#app')
```

### API call proxy — `frontend/app.js`

Wraps `window.pywebview.api` after `pywebviewready` fires:

```js
window.addEventListener('pywebviewready', () => {
  __apiReadyResolve()
  // Wrap API with logging proxy
  window.pywebview.api = new Proxy(window.pywebview.api, {
    get(target, method) {
      const fn = target[method]
      if (typeof fn !== 'function') return fn
      return (...args) => {
        const argStr = JSON.stringify(args).slice(0, 200)
        window.pywebview.api.__raw_log('debug', `api.call method=${method} args=${argStr}`).catch(() => {})
        return fn.apply(target, args).then(result => {
          window.pywebview.api.__raw_log('debug', `api.result method=${method}`).catch(() => {})
          return result
        }).catch(err => {
          window.pywebview.api.__raw_log('error', `api.error method=${method} error=${err}`).catch(() => {})
          throw err
        })
      }
    }
  })
})
```

`__raw_log` is an alias for `log_js_error` added to avoid the proxy wrapping itself:

```python
def __raw_log(self, level: str, message: str) -> None:
    """Direct log bypass — called by the JS API proxy, must not go through the proxy itself."""
    self.log_js_error(level, message)
```

The proxy is applied after `__apiReadyResolve()` so it doesn't interfere with the ready signal itself.

---

## Section 5: Debug Dump

### `create_debug_dump()` — Python API method

```python
def create_debug_dump(self) -> dict:
    """Build a debug zip in Downloads and open the folder. Returns {ok, filename} or {ok:False, error}."""
```

**Steps:**
1. Collect `logs/` folder (all files matching `*.log*`)
2. Load and redact `state.json` — walk all keys recursively, replace value with `"***"` if key name contains `pat`, `token`, `secret`, or `password` (case-insensitive)
3. Build `system_info.json` from `get_host_info()` output + `{"dump_timestamp": "<ISO>"}`
4. Write zip to `~/Downloads/mcaddoncompanion-debug-YYYY-MM-DD-HHMMSS.zip`
5. Call `os.startfile(downloads_dir)` to open the folder
6. Log `INFO` with the zip filename
7. Return `{"ok": True, "filename": "mcaddoncompanion-debug-....zip"}` or `{"ok": False, "error": "..."}`

Downloads folder resolved via:
```python
downloads = Path.home() / "Downloads"
```

### UI — Help & Debug modal (`frontend/app.js`)

Replace the current "Upload Debug Data" placeholder with a working button:

```
[ Save Debug Dump ]   ← calls create_debug_dump()
```

States:
- Default: "Save Debug Dump" button
- While running: button disabled, label "Creating dump…"
- Success: green inline message "Saved: mcaddoncompanion-debug-....zip — folder opened"
- Error: red inline message with error text

---

## Files Changed

| File | Change |
|---|---|
| `main.py` | Replace `_configure_logging()`, add `log_js_error`, `__raw_log`, `create_debug_dump`, `get_minecraft_dir` import; fix headless arg validation; add `log =` at module level |
| `core/prism.py` | Add `get_minecraft_dir(instances_dir, name)`; add `log =` |
| `core/state.py` | Add `log =`; fix `load_state` handler |
| `core/gitlab.py` | Add `log =`; fix `_get()` response validation; fix `get_metadata` handler |
| `core/updater.py` | Add `log =`; fix both handlers |
| `modules/instance_sync/sync.py` | Add `log =`; fix manifest + changelog handlers |
| `modules/instance_sharing/share.py` | Add `log =`; fix `instance.cfg` handler; remove `build_filtered_zip`, `launch_prism_import` |
| `modules/schematic_sync/page.py` | Add `log =`; fix state import handler |
| `modules/instance_sharing/page.py` | Update `get_minecraft_dir` import |
| `modules/pack_registry/page.py` | Update `get_minecraft_dir` import |
| `frontend/app.js` | Add `window.onerror`, `unhandledrejection`, Vue `errorHandler`, API proxy; wire debug dump button |

---

## What This Does NOT Change

- Module return value shapes
- Progress callback signatures
- UI error display patterns
- Any feature behavior
- The `update_install.log` written by the updater batch script (already in the right place)
