# Instance Sync Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the instance sync feature with delta exit sync, persistent error reporting via `last_result.json`, expandable Home table rows with read-only sync detail, gear modal danger zone with archive actions, module settings icon on the Instance Sync page, and update stream / GitLab PAT settings in the three-dot menu modals.

**Architecture:** Backend changes in `sync.py` (delta exit sync + `last_result.json` writer) and `main.py` (new API methods) are done first, then frontend changes to `home.js`, `instance_sync.js`, and `app.js` consume them. No shared state between frontend files — each page reads its own slice of data. The `last_result.json` sidecar pattern is the key new data source shared between Instance Sync page and Home expandable rows.

**Tech Stack:** Python 3.11, PyWebView, Vue 3 ESM (no build step), plain backtick template strings, existing CSS design tokens.

---

## File Map

| File | Changes |
|------|---------|
| `modules/instance_sync/sync.py` | Add `read_last_result`, `write_last_result` helpers; delta exit sync in `run_exit_sync`; write `last_result.json` after both sync functions |
| `main.py` | Add `get_instance_detail`, `get_update_stream`, `set_update_stream`, `get_gitlab_pat_api`, `set_gitlab_pat_api`; update `get_instance_sync_data` to include last_result per instance; add `archive_instance_move_only` |
| `frontend/pages/home.js` | Expandable rows with lazy-loaded detail panel; gear modal danger zone; greyed toggles with shortcuts; pack update shortcut |
| `frontend/pages/instance_sync.js` | Module settings icon + modal; populate last sync / size / error columns |
| `frontend/app.js` | Version & Updates modal: stream selector; Help & Debug modal: PAT field + stream-aware load |
| `frontend/style.css` | Expandable row styles; danger zone styles |

---

### Task 1: sync.py — last_result helpers + delta exit sync + last_result writes

**Files:**
- Modify: `modules/instance_sync/sync.py`

**Context:** `sync.py` currently has `run_exit_sync` (copies all non-blacklisted files unconditionally) and `run_startup_sync` (already does mtime+size comparison). Both live in `C:\Users\comsi\Nextcloud\Dev\MCAddonCompanion\modules\instance_sync\sync.py`. The sync folder per instance is at `<sync_path>/instance_sync/<instance_name>/`. `manifest.json` lives there already.

- [ ] **Step 1: Add `read_last_result` and `write_last_result` helpers**

After the `_file_stat` function, add:

```python
def read_last_result(sync_instance_dir: Path) -> dict:
    """Read last_result.json from sync folder. Returns {} if missing or corrupt."""
    p = sync_instance_dir / "last_result.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("last_result.json corrupt at %s: %s", p, e)
        return {}


def write_last_result(sync_instance_dir: Path, result: dict) -> None:
    """Write last_result.json alongside manifest.json. Best-effort — never raises."""
    try:
        sync_instance_dir.mkdir(parents=True, exist_ok=True)
        (sync_instance_dir / "last_result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
    except Exception as e:
        log.warning("Could not write last_result.json at %s: %s", sync_instance_dir, e)
```

- [ ] **Step 2: Make `run_exit_sync` delta — skip unchanged files**

Find the loop in `run_exit_sync` that iterates `to_copy`. Currently it copies every file. Change it to read the old manifest and skip files where mtime+size match:

Replace the existing `for src, rel in to_copy:` loop with:

```python
    old_manifest = read_manifest(sync_instance_dir)
    new_manifest = {}
    unchanged = 0

    for src, rel in to_copy:
        dest = sync_instance_dir / rel
        try:
            src_stat = src.stat()
            recorded = old_manifest.get(rel)
            if (recorded
                    and dest.exists()
                    and abs(src_stat.st_mtime - recorded["mtime"]) < 1.0
                    and src_stat.st_size == recorded["size"]):
                new_manifest[rel] = recorded
                unchanged += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))
            new_manifest[rel] = _file_stat(dest)
            copied += 1
        except Exception as e:
            errors.append(f"{rel}: {e}")
        if on_progress:
            on_progress(copied + unchanged, total)
```

Also update the return dict to include `unchanged`:

```python
    return {"copied": copied, "skipped": skipped, "pruned": pruned, "unchanged": unchanged, "errors": errors}
```

Note: remove the `old_manifest = read_manifest(sync_instance_dir)` line that was already at the top of the function (it's now inside the loop setup above — make sure it isn't duplicated).

- [ ] **Step 3: Write `last_result.json` at the end of `run_exit_sync`**

Just before the final `return` in `run_exit_sync`, add:

```python
    write_last_result(sync_instance_dir, {
        "mode": "exit",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "copied": copied,
        "skipped": skipped,
        "pruned": pruned,
        "unchanged": unchanged,
        "errors": errors,
    })
```

- [ ] **Step 4: Write `last_result.json` at the end of `run_startup_sync`**

Just before the final `return` in `run_startup_sync`, add:

```python
    write_last_result(sync_instance_dir, {
        "mode": "startup",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "restored": restored,
        "skipped": skipped,
        "backed_up": backed_up,
        "errors": errors,
    })
```

- [ ] **Step 5: Verify no import errors**

Run from the project root:
```
venv\Scripts\python.exe -c "from modules.instance_sync.sync import run_exit_sync, run_startup_sync, read_last_result, write_last_result; print('ok')"
```
Expected output: `ok`

- [ ] **Step 6: Commit**

```bash
git add modules/instance_sync/sync.py
git commit -m "feat: delta exit sync and last_result.json persistence in sync.py"
```

---

### Task 2: main.py — new API methods

**Files:**
- Modify: `main.py`

**Context:** `main.py` has an `Api` class. New methods go after the existing instance sync section (after `delete_archive_zip`). The following are already in `core/state.py` and importable: `get_update_stream`, `set_update_stream`, `get_gitlab_pat`, `set_gitlab_pat`. The `get_instance_sync_config` and `is_instance_sync_configured` are imported at module top. `INSTANCES_DIR` and `get_minecraft_dir` are in scope.

- [ ] **Step 1: Add `get_instance_detail` API method**

After `delete_archive_zip`, add:

```python
def get_instance_detail(self, instance_name: str) -> dict:
    """Return sync detail and pack info for one instance. All reads are local — no network."""
    from modules.instance_sync.sync import read_last_result, read_manifest
    from core.state import get_installed_instances, get_tracked_packs

    cfg = get_instance_sync_config()
    sync_path = cfg.get("sync_path") or ""
    result = {
        "last_exit_sync": None,
        "last_startup_sync": None,
        "synced_file_count": 0,
        "synced_size_mb": 0.0,
        "last_exit_errors": [],
        "last_startup_errors": [],
        "instance_folder_size_mb": None,
        "pack": None,
    }

    # Sync data from last_result.json and manifest.json
    if sync_path and is_instance_sync_configured():
        sync_dir = Path(sync_path) / "instance_sync" / instance_name
        last = read_last_result(sync_dir)
        if last.get("mode") == "exit":
            result["last_exit_sync"] = last.get("timestamp")
            result["last_exit_errors"] = last.get("errors", [])
        elif last.get("mode") == "startup":
            result["last_startup_sync"] = last.get("timestamp")
            result["last_startup_errors"] = last.get("errors", [])

        manifest = read_manifest(sync_dir)
        result["synced_file_count"] = len(manifest)
        result["synced_size_mb"] = round(
            sum(v.get("size", 0) for v in manifest.values()) / 1_048_576, 1
        )

    # Instance folder size
    inst_dir = INSTANCES_DIR / instance_name
    if inst_dir.exists():
        try:
            total = sum(f.stat().st_size for f in inst_dir.rglob("*") if f.is_file())
            result["instance_folder_size_mb"] = round(total / 1_048_576, 1)
        except Exception:
            pass

    # Pack info from state
    installed_map = {i["instance_name"]: i for i in get_installed_instances()}
    tracked_map = {t["instance_name"]: t for t in get_tracked_packs()}
    inst_record = installed_map.get(instance_name)
    if inst_record:
        tracked = tracked_map.get(instance_name)
        result["pack"] = {
            "name": inst_record.get("pack_name"),
            "installed_version": inst_record.get("installed_version"),
            "tracked": tracked is not None,
            "has_update": False,
            "latest_version": None,
        }

    return result
```

- [ ] **Step 2: Add `archive_instance_move_only` API method**

After `get_instance_detail`, add:

```python
def archive_instance_move_only(self, instance_name: str) -> dict:
    """Sync instance to sync folder then delete instance folder. No zip backup created."""
    import shutil
    from modules.instance_sync.sync import is_blacklisted, read_manifest, write_manifest, _file_stat

    cfg = get_instance_sync_config()
    instances_path = Path(cfg.get("instances_path") or str(INSTANCES_DIR))
    sync_path = Path(cfg.get("sync_path") or "")
    if not sync_path:
        return {"ok": False, "error": "Sync path not configured."}

    inst_dir = instances_path / instance_name
    if not inst_dir.exists():
        return {"ok": False, "error": f"Instance folder not found: {inst_dir}"}

    mc_dir = get_minecraft_dir(instances_path, instance_name)

    # Sync to sync folder
    sync_dir = sync_path / "instance_sync" / instance_name
    if mc_dir:
        all_files = [(src, src.relative_to(mc_dir).as_posix())
                     for src in mc_dir.rglob("*") if src.is_file()]
        to_copy = [(src, rel) for src, rel in all_files if not is_blacklisted(rel)]
        sync_dir.mkdir(parents=True, exist_ok=True)
        new_manifest = {}
        for src, rel in to_copy:
            dest = sync_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))
            new_manifest[rel] = _file_stat(dest)
        write_manifest(sync_dir, new_manifest)

    # Remove instance folder (no zip)
    try:
        shutil.rmtree(str(inst_dir))
    except Exception as e:
        return {"ok": False, "error": f"Could not remove instance folder: {e}"}

    log.info("Move-only archived instance %r (no zip)", instance_name)
    return {"ok": True}
```

- [ ] **Step 3: Add update stream and GitLab PAT API methods**

After `archive_instance_move_only`, add:

```python
def get_update_stream_api(self) -> str:
    from core.state import get_update_stream
    return get_update_stream()

def set_update_stream_api(self, stream: str) -> dict:
    from core.state import set_update_stream, VALID_STREAMS
    if stream not in VALID_STREAMS:
        return {"ok": False, "error": f"Invalid stream: {stream}"}
    try:
        set_update_stream(stream)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_gitlab_pat_api(self) -> str:
    from core.state import get_gitlab_pat
    return get_gitlab_pat() or ""

def set_gitlab_pat_api(self, pat: str) -> None:
    from core.state import set_gitlab_pat
    set_gitlab_pat(pat.strip())
```

- [ ] **Step 4: Update `get_instance_sync_data` to include last_result per instance**

Find `get_instance_sync_data` in `main.py`. In the loop that builds `rows`, after appending the existing fields, add last_result data. The loop currently builds:

```python
rows.append({
    "name": name,
    "exit_sync": ...,
    "startup_sync": ...,
    "enabled": ...,
})
```

Replace with:

```python
        from modules.instance_sync.sync import read_last_result, read_manifest
        sync_dir = Path(sync_path) / "instance_sync" / name if sync_path else None
        last = read_last_result(sync_dir) if sync_dir else {}
        manifest = read_manifest(sync_dir) if sync_dir else {}
        synced_size = round(
            sum(v.get("size", 0) for v in manifest.values()) / 1_048_576, 1
        ) if manifest else 0.0
        rows.append({
            "name": name,
            "exit_sync": inst_cfg.get("exit_sync") if inst_cfg.get("exit_sync") is not None else defaults["exit_sync"],
            "startup_sync": inst_cfg.get("startup_sync") if inst_cfg.get("startup_sync") is not None else defaults.get("startup_sync", False),
            "enabled": inst_cfg.get("enabled", True),
            "last_exit_sync": last.get("timestamp") if last.get("mode") == "exit" else None,
            "last_startup_sync": last.get("timestamp") if last.get("mode") == "startup" else None,
            "last_errors": last.get("errors", []),
            "synced_size_mb": synced_size,
        })
```

Move the `from modules.instance_sync.sync import ...` line to the top of `get_instance_sync_data` (before the loop) to avoid re-importing on every iteration.

- [ ] **Step 5: Verify no import errors**

```
venv\Scripts\python.exe -c "import main; print('ok')"
```
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: get_instance_detail, archive_instance_move_only, update stream/PAT API methods, last_result in get_instance_sync_data"
```

---

### Task 3: style.css — expandable row and danger zone styles

**Files:**
- Modify: `frontend/style.css`

**Context:** The existing table styles use `.data-table`. Toggle styles use `.toggle-track` / `.toggle-thumb`. New styles needed: expandable row detail panel, danger zone section. Add after the existing `.data-table` block.

- [ ] **Step 1: Find the end of the `.data-table` CSS block**

Search for `.data-table` in `style.css`. The block ends somewhere around the table/row/cell rules. Add the following after it:

```css
/* expandable row detail panel */
.row-detail {
  background: var(--bg-0); border-top: 1px solid var(--line);
  padding: 14px 16px; display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px 24px;
}
.row-detail-field { display: flex; flex-direction: column; gap: 3px; }
.row-detail-label { font-size: 11px; font-weight: 500; color: var(--text-3); text-transform: uppercase; letter-spacing: .06em; }
.row-detail-value { font-size: 13px; color: var(--text-0); }
.row-detail-error { font-size: 12px; color: var(--err); margin-top: 4px; }

/* danger zone */
.danger-zone {
  border-top: 1px solid var(--err-soft); margin-top: 16px; padding-top: 14px;
}
.danger-zone-label {
  font-size: 11px; font-weight: 600; color: var(--err); text-transform: uppercase;
  letter-spacing: .08em; margin-bottom: 10px;
}
.btn-danger {
  background: transparent; border: 1px solid var(--err); color: var(--err);
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 10px; border-radius: var(--r-btn);
  font-family: inherit; font-weight: 500; font-size: 12px;
  cursor: pointer; transition: all .12s;
}
.btn-danger:hover { background: var(--err-soft); }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

/* toggle disabled state */
.toggle-track.disabled-hint { opacity: 0.4; cursor: not-allowed; }
.toggle-hint { font-size: 11px; color: var(--text-3); margin-top: 3px; }
.toggle-hint a { color: var(--accent-hi); cursor: pointer; text-decoration: none; }
.toggle-hint a:hover { text-decoration: underline; }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/style.css
git commit -m "feat: expandable row detail, danger zone, and disabled toggle hint styles"
```

---

### Task 4: home.js — expandable rows + gear modal improvements

**Files:**
- Modify: `frontend/pages/home.js`

**Context:** `home.js` is a Vue 3 ESM component. `setup()` currently returns `{ data, loading, error, query, filtered, syncedCount, load, icon, abbr, openInstancesFolder, settingsModal, openSettings, closeSettings, saveSettings }`. The template is a backtick string. The instance table rows are `<tr v-for="inst in filtered">`. The gear modal `<teleport>` block is at the end of the template before `</main>`.

The component has `emits: ['navigate']` so `$emit('navigate', 'pack_registry')` works in the template.

Instance Sync is not always configured — check `data.value` for a flag. `get_instance_sync_data` returns `is_configured` but `get_home_data` does not. Use `get_instance_sync_config` indirectly: add a new API call `is_instance_sync_configured_api` — actually simpler: check if `inst.exit_sync` or `inst.startup_sync` appear in `get_home_data` results. They already do (`exit_sync`, `startup_sync` on each instance row). If `exit_sync` and `startup_sync` are both `false` and there's no hook, Instance Sync may not be configured — but that's ambiguous. Better approach: add `instance_sync_configured` boolean to `get_home_data` response.

**Note to implementer:** In `main.py`, find `get_home_data` and add `"instance_sync_configured": is_instance_sync_configured()` to the returned dict. This is a one-liner addition to an existing method.

- [ ] **Step 1: Add `instance_sync_configured` to `get_home_data` in main.py**

Find `get_home_data` in `main.py`. Its return statement is:
```python
return {"instances": rows, "repos": repos}
```

Change to:
```python
return {"instances": rows, "repos": repos, "instance_sync_configured": is_instance_sync_configured()}
```

- [ ] **Step 2: Add expandable row state to setup() in home.js**

After `const openInstancesFolder = async () => { ... }`, add:

```js
// Expandable row detail
const expandedRow = ref(null)          // instance name currently expanded, or null
const rowDetail = ref({})              // { [instName]: { loading, data } }

const toggleRow = (instName) => {
  if (expandedRow.value === instName) {
    expandedRow.value = null
    return
  }
  expandedRow.value = instName
  if (rowDetail.value[instName]) return  // already loaded
  rowDetail.value = { ...rowDetail.value, [instName]: { loading: true, data: null } }
  window.__apiReady.then(() =>
    window.pywebview.api.get_instance_detail(instName)
      .then(d => { rowDetail.value = { ...rowDetail.value, [instName]: { loading: false, data: d } } })
      .catch(() => { rowDetail.value = { ...rowDetail.value, [instName]: { loading: false, data: null } } })
  )
}

const refreshRowDetail = (instName) => {
  rowDetail.value = { ...rowDetail.value, [instName]: { loading: true, data: null } }
  window.__apiReady.then(() =>
    window.pywebview.api.get_instance_detail(instName)
      .then(d => { rowDetail.value = { ...rowDetail.value, [instName]: { loading: false, data: d } } })
      .catch(() => { rowDetail.value = { ...rowDetail.value, [instName]: { loading: false, data: null } } })
  )
}

const fmtDate = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}
```

- [ ] **Step 3: Add archive state to setup() in home.js**

After the expandable row state, add:

```js
// Archive actions (danger zone in gear modal)
const archiveConfirm = ref(null)      // null | 'archive' | 'move_only'
const archiving = ref(false)
const archiveError = ref(null)

const doArchive = async (instName, moveOnly) => {
  archiving.value = true
  archiveError.value = null
  try {
    await window.__apiReady
    const method = moveOnly ? 'archive_instance_move_only' : 'archive_instance'
    const r = await window.pywebview.api[method](instName)
    if (r.ok) {
      closeSettings()
      await load()
    } else {
      archiveError.value = r.error || 'Archive failed'
    }
  } catch(e) {
    archiveError.value = String(e)
  }
  archiving.value = false
  archiveConfirm.value = null
}
```

- [ ] **Step 4: Update the return {} in setup() to include new refs**

Add to the return object:
```js
expandedRow, rowDetail, toggleRow, refreshRowDetail, fmtDate,
archiveConfirm, archiving, archiveError, doArchive,
```

- [ ] **Step 5: Update the instance table rows in the template**

Find the `<tr v-for="inst in filtered"` row in the template. Add `@click="toggleRow(inst.name)"` and `style="cursor:pointer"` to the `<tr>`:

```html
<tr v-for="inst in filtered" :key="inst.name" @click.self="toggleRow(inst.name)" style="cursor:pointer">
```

Note: use `@click.self` won't work on tr directly — instead wrap the row action. Simplest approach: add `@click="toggleRow(inst.name)"` to the `<tr>` and add `@click.stop` to the gear button so it doesn't propagate:

```html
<tr v-for="inst in filtered" :key="inst.name" @click="toggleRow(inst.name)" style="cursor:pointer">
```

And on the gear button cell:
```html
<td style="text-align:right" @click.stop>
  <div class="flex items-center gap-4" style="justify-content:flex-end">
    <button class="icon-btn" title="Settings" @click="openSettings(inst.name)"><span v-html="icon('settings',14)"></span></button>
  </div>
</td>
```

- [ ] **Step 6: Add the expandable detail row after each instance row**

After the closing `</tr>` of the instance row (but inside `<tbody>`), add:

```html
<tr v-if="expandedRow === inst.name" :key="inst.name + '-detail'">
  <td colspan="6" style="padding:0;border-top:none">
    <div class="row-detail">
      <template v-if="rowDetail[inst.name]?.loading">
        <div class="row-detail-field" style="grid-column:1/-1">
          <span class="fs-13 text-3">Loading…</span>
        </div>
      </template>
      <template v-else-if="rowDetail[inst.name]?.data">
        <div class="row-detail-field">
          <span class="row-detail-label">Last Exit Sync</span>
          <span class="row-detail-value mono fs-12" :title="rowDetail[inst.name].data.last_exit_sync">
            {{ fmtDate(rowDetail[inst.name].data.last_exit_sync) }}
          </span>
        </div>
        <div class="row-detail-field">
          <span class="row-detail-label">Last Startup Sync</span>
          <span class="row-detail-value mono fs-12" :title="rowDetail[inst.name].data.last_startup_sync">
            {{ fmtDate(rowDetail[inst.name].data.last_startup_sync) }}
          </span>
        </div>
        <div class="row-detail-field">
          <span class="row-detail-label">Synced</span>
          <span class="row-detail-value fs-12">
            {{ rowDetail[inst.name].data.synced_file_count }} files · {{ rowDetail[inst.name].data.synced_size_mb }} MB
          </span>
        </div>
        <div class="row-detail-field">
          <span class="row-detail-label">Instance Size</span>
          <span class="row-detail-value fs-12">
            {{ rowDetail[inst.name].data.instance_folder_size_mb != null ? rowDetail[inst.name].data.instance_folder_size_mb + ' MB' : '—' }}
          </span>
        </div>
        <template v-if="rowDetail[inst.name].data.pack">
          <div class="row-detail-field">
            <span class="row-detail-label">Installed Pack</span>
            <span class="row-detail-value fs-12">{{ rowDetail[inst.name].data.pack.name }} v{{ rowDetail[inst.name].data.pack.installed_version }}</span>
          </div>
          <div class="row-detail-field">
            <span class="row-detail-label">Tracking</span>
            <span class="row-detail-value fs-12">{{ rowDetail[inst.name].data.pack.tracked ? 'Tracked' : 'Not tracked' }}</span>
          </div>
          <div v-if="rowDetail[inst.name].data.pack.has_update" class="row-detail-field">
            <span class="row-detail-label">Update</span>
            <span class="row-detail-value fs-12">
              v{{ rowDetail[inst.name].data.pack.latest_version }} available —
              <a class="ghost-link" style="font-size:12px" @click.stop="$emit('navigate','pack_registry')">Go to Registry</a>
            </span>
          </div>
        </template>
        <div v-if="rowDetail[inst.name].data.last_exit_errors?.length || rowDetail[inst.name].data.last_startup_errors?.length"
          class="row-detail-field" style="grid-column:1/-1">
          <span class="row-detail-label">Last Errors</span>
          <div v-for="e in [...(rowDetail[inst.name].data.last_exit_errors||[]), ...(rowDetail[inst.name].data.last_startup_errors||[])]"
            :key="e" class="row-detail-error">{{ e }}</div>
        </div>
        <div class="row-detail-field" style="grid-column:1/-1;display:flex;justify-content:flex-end">
          <button class="btn btn-ghost btn-sm" style="font-size:11px" @click.stop="refreshRowDetail(inst.name)">
            <span v-html="icon('refresh',11)"></span> Refresh
          </button>
        </div>
      </template>
      <template v-else>
        <div class="row-detail-field" style="grid-column:1/-1">
          <span class="fs-13 text-3">No sync data available.</span>
        </div>
      </template>
    </div>
  </td>
</tr>
```

- [ ] **Step 7: Update the gear modal to add greyed toggles, pack update shortcut, and danger zone**

Find the gear modal `<teleport>` block. Inside `<template v-else-if="settingsModal.form">`, the current toggle section ends before the `<div style="padding:16px 24px;border-top...` footer.

**Replace the toggle section** (the part with Schematic Sync, Pre/Post Launch Hook, Instance Sync, and Track for Updates) with the following — which adds `disabled-hint` class and tooltip links when Instance Sync is not configured:

```html
<!-- Schematic Sync — always active -->
<div style="display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--line)">
  <div>
    <div class="fs-13 fw-500 text-0">Schematic Sync</div>
    <div class="fs-12 text-3" style="margin-top:2px">Auto-sync schematics on instance exit</div>
  </div>
  <div class="toggle-track" :class="settingsModal.form.schematic_sync ? 'on' : 'off'"
    @click="settingsModal.form.schematic_sync = !settingsModal.form.schematic_sync" style="flex:none">
    <div class="toggle-thumb"></div>
  </div>
</div>

<!-- Pre/Post Launch Hook -->
<div style="display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--line)">
  <div>
    <div class="fs-13 fw-500 text-0">Pre/Post Launch Hook</div>
    <div class="fs-12 text-3" style="margin-top:2px">Run sync commands before launch and after exit</div>
    <div v-if="!data.instance_sync_configured" class="toggle-hint">
      Instance Sync not set up —
      <a @click="closeSettings(); $emit('navigate','instance_sync')">Configure →</a>
    </div>
  </div>
  <div class="toggle-track"
    :class="[settingsModal.form.hook_enabled ? 'on' : 'off', !data.instance_sync_configured ? 'disabled-hint' : '']"
    @click="if(data.instance_sync_configured) settingsModal.form.hook_enabled = !settingsModal.form.hook_enabled"
    style="flex:none">
    <div class="toggle-thumb"></div>
  </div>
</div>

<!-- Instance Sync group -->
<div style="padding:12px 0;border-bottom:1px solid var(--line)">
  <div style="display:flex;align-items:center;justify-content:space-between">
    <div>
      <div class="fs-13 fw-500 text-0">Instance Sync</div>
      <div class="fs-12 text-3" style="margin-top:2px">Sync instance files on launch and exit</div>
      <div v-if="!data.instance_sync_configured" class="toggle-hint">
        Instance Sync not set up —
        <a @click="closeSettings(); $emit('navigate','instance_sync')">Configure →</a>
      </div>
    </div>
    <div class="toggle-track"
      :class="[(settingsModal.form.exit_sync || settingsModal.form.startup_sync) ? 'on' : 'off', !data.instance_sync_configured ? 'disabled-hint' : '']"
      style="flex:none;opacity:.5;cursor:not-allowed" title="Configure via sub-toggles below">
      <div class="toggle-thumb"></div>
    </div>
  </div>
  <div style="margin-top:8px;padding-left:16px;display:flex;flex-direction:column;gap:6px;border-left:2px solid var(--line)">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0">
      <div>
        <div class="fs-12 fw-500 text-1">Exit Sync</div>
        <div class="fs-11 text-3">Sync files when Prism closes</div>
      </div>
      <div class="toggle-track"
        :class="[settingsModal.form.exit_sync ? 'on' : 'off', !data.instance_sync_configured ? 'disabled-hint' : '']"
        @click="if(data.instance_sync_configured) settingsModal.form.exit_sync = !settingsModal.form.exit_sync"
        style="flex:none;transform:scale(0.85);transform-origin:right center">
        <div class="toggle-thumb"></div>
      </div>
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0">
      <div>
        <div class="fs-12 fw-500 text-1">Startup Sync</div>
        <div class="fs-11 text-3">Restore files when Prism launches</div>
      </div>
      <div class="toggle-track"
        :class="[settingsModal.form.startup_sync ? 'on' : 'off', !data.instance_sync_configured ? 'disabled-hint' : '']"
        @click="if(data.instance_sync_configured) settingsModal.form.startup_sync = !settingsModal.form.startup_sync"
        style="flex:none;transform:scale(0.85);transform-origin:right center">
        <div class="toggle-thumb"></div>
      </div>
    </div>
  </div>
</div>

<!-- Track for Updates (only if pack installed) -->
<div v-if="settingsModal.form.installed"
  style="display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--line)">
  <div>
    <div class="fs-13 fw-500 text-0">Track for Updates</div>
    <div class="fs-12 text-3" style="margin-top:2px">{{ settingsModal.form.pack_name || 'Pack' }} — auto-check for new versions</div>
  </div>
  <div class="toggle-track" :class="settingsModal.form.tracked ? 'on' : 'off'"
    @click="settingsModal.form.tracked = !settingsModal.form.tracked" style="flex:none">
    <div class="toggle-thumb"></div>
  </div>
</div>
```

- [ ] **Step 8: Add pack update shortcut and danger zone to gear modal**

After the Track for Updates toggle (still inside `<template v-else-if="settingsModal.form">`), before the `<div style="padding:16px 24px;border-top...` footer, add:

```html
<!-- Pack update shortcut (shown if update available) -->
<div v-if="settingsModal.form.installed && rowDetail[settingsModal.instance]?.data?.pack?.has_update"
  style="padding:10px 0;border-bottom:1px solid var(--line)">
  <div class="fs-12 text-2">
    Update available — v{{ rowDetail[settingsModal.instance].data.pack.latest_version }}
  </div>
  <button class="ghost-link" style="margin-top:4px" @click="closeSettings(); $emit('navigate','pack_registry')">
    <span v-html="icon('download',11)"></span> Go to Pack Registry to update
  </button>
</div>

<!-- Danger Zone -->
<div class="danger-zone">
  <div class="danger-zone-label">Danger Zone</div>

  <!-- Archive error -->
  <div v-if="archiveError" class="fs-12" style="color:var(--err);margin-bottom:8px">{{ archiveError }}</div>

  <!-- Archive (with zip backup) -->
  <div style="margin-bottom:8px">
    <template v-if="archiveConfirm === 'archive'">
      <div class="fs-12 text-1" style="margin-bottom:6px">This will sync, zip, and remove the instance from Prism. Continue?</div>
      <div class="flex items-center gap-6">
        <button class="btn-danger" :disabled="archiving" @click="doArchive(settingsModal.instance, false)">
          {{ archiving ? 'Archiving…' : 'Confirm Archive' }}
        </button>
        <button class="btn btn-ghost btn-sm" @click="archiveConfirm = null">Cancel</button>
      </div>
    </template>
    <button v-else class="btn-danger" @click="archiveConfirm = 'archive'; archiveError = null">
      <span v-html="icon('archive',12)"></span> Archive
    </button>
    <div class="fs-11 text-3" style="margin-top:4px">Sync + create zip backup + remove from Prism</div>
  </div>

  <!-- Archive Move Only (no zip) -->
  <div>
    <template v-if="archiveConfirm === 'move_only'">
      <div class="fs-12" style="color:var(--err);margin-bottom:6px">
        ⚠ Warning: Without a zip backup, this instance cannot be recovered if the sync folder is lost or corrupted.
      </div>
      <div class="flex items-center gap-6">
        <button class="btn-danger" :disabled="archiving" @click="doArchive(settingsModal.instance, true)">
          {{ archiving ? 'Moving…' : 'Yes, move only' }}
        </button>
        <button class="btn btn-ghost btn-sm" @click="archiveConfirm = null">Cancel</button>
      </div>
    </template>
    <button v-else class="btn-danger" @click="archiveConfirm = 'move_only'; archiveError = null">
      <span v-html="icon('archive',12)"></span> Archive (Move only)
    </button>
    <div class="fs-11 text-3" style="margin-top:4px">Sync + remove from Prism — no zip backup created</div>
  </div>
</div>
```

- [ ] **Step 9: Reset archiveConfirm when modal closes**

In `closeSettings`, the current implementation is:
```js
const closeSettings = () => {
  settingsModal.value = { show: false, loading: false, saving: false, instance: null, form: null }
}
```

Replace with:
```js
const closeSettings = () => {
  settingsModal.value = { show: false, loading: false, saving: false, instance: null, form: null }
  archiveConfirm.value = null
  archiveError.value = null
}
```

- [ ] **Step 10: Launch from source and test**

```
python main.py
```

- Click any instance row → detail panel expands and loads
- Click row again → collapses
- Click gear on an instance → quick settings modal opens
- If Instance Sync not configured: Exit Sync and Startup Sync sub-toggles are greyed, "Configure →" link visible
- Danger Zone visible at bottom with Archive and Archive (Move only)
- Archive → shows confirmation → cancel works

- [ ] **Step 11: Commit**

```bash
git add frontend/pages/home.js main.py
git commit -m "feat: expandable instance rows, gear modal danger zone and disabled sync hints"
```

---

### Task 5: instance_sync.js — module settings icon + populated columns + error indicator

**Files:**
- Modify: `frontend/pages/instance_sync.js`

**Context:** `instance_sync.js` is a Vue 3 ESM component. The page header currently has `<h1>Instance Sync</h1>` on the left and Archived/Refresh buttons on the right. `get_instance_sync_data` now returns `last_exit_sync`, `last_startup_sync`, `last_errors`, `synced_size_mb` per instance row. The instance table has `Last Exit Sync`, `Last Startup Sync`, `Size` columns currently showing `—`.

- [ ] **Step 1: Add module settings modal state to setup()**

After `const load = async () => { ... }`, add:

```js
const showModuleSettings = ref(false)
const moduleSettingsForm = ref({ instances_path: '', sync_path: '' })
const moduleSettingsSaving = ref(false)
const moduleSettingsError = ref(null)

const openModuleSettings = () => {
  moduleSettingsForm.value = {
    instances_path: data.value?.instances_path || '',
    sync_path: data.value?.sync_path || '',
  }
  moduleSettingsError.value = null
  showModuleSettings.value = true
}

const saveModuleSettings = async () => {
  if (!moduleSettingsForm.value.instances_path || !moduleSettingsForm.value.sync_path) {
    moduleSettingsError.value = 'Both paths are required.'
    return
  }
  moduleSettingsSaving.value = true
  moduleSettingsError.value = null
  try {
    await window.__apiReady
    await window.pywebview.api.setup_instance_sync(
      moduleSettingsForm.value.instances_path,
      moduleSettingsForm.value.sync_path,
    )
    showModuleSettings.value = false
    await load()
  } catch(e) {
    moduleSettingsError.value = String(e)
  }
  moduleSettingsSaving.value = false
}

const resetModuleSync = async () => {
  try {
    await window.__apiReady
    await window.pywebview.api.reset_module('instance_sync')
    showModuleSettings.value = false
    await load()
  } catch(e) {}
}
```

- [ ] **Step 2: Add `fmtDate` helper and `expandedError` ref to setup()**

```js
const fmtDate = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

const expandedError = ref(null)  // instance name whose error panel is open
```

- [ ] **Step 3: Update return {} to include new refs**

Add to the return object:
```js
showModuleSettings, moduleSettingsForm, moduleSettingsSaving, moduleSettingsError,
openModuleSettings, saveModuleSettings, resetModuleSync,
fmtDate, expandedError,
```

- [ ] **Step 4: Update the existing `openSetup` and `saveSetup` to use the module settings modal**

The existing `openSetup` / `saveSetup` / `showSetup` are used on the unconfigured state screen. Change the unconfigured screen button to call `openModuleSettings()` instead of `openSetup()`. Keep `openSetup` / `saveSetup` / `showSetup` in the return for now — they can be removed in a later cleanup. Just wire the button:

Find in the template:
```html
<button class="btn btn-primary btn-sm" @click="openSetup">Setup Instance Sync</button>
```

Replace with:
```html
<button class="btn btn-primary btn-sm" @click="openModuleSettings">Setup Instance Sync</button>
```

- [ ] **Step 5: Add the settings gear icon to the page header**

Find in the template:
```html
<h1>Instance Sync</h1>
```

Replace with:
```html
<h1>Instance Sync</h1>
```
But wrap the `<div>` containing kicker + h1 to add the gear button alongside:

Find the full header left block:
```html
        <div>
          <div class="kicker">Sync</div>
          <h1>Instance Sync</h1>
        </div>
```

Replace with:
```html
        <div style="display:flex;align-items:center;gap:10px">
          <div>
            <div class="kicker">Sync</div>
            <h1>Instance Sync</h1>
          </div>
          <button class="icon-btn" title="Instance Sync Settings" @click="openModuleSettings" style="margin-top:4px">
            <span v-html="icon('settings',15)"></span>
          </button>
        </div>
```

- [ ] **Step 6: Populate last sync and size columns in the instance table**

Find the table columns currently showing `—`:

```html
                  <td><span class="mono fs-12 text-2">—</span></td>
                  <td><span class="mono fs-12 text-2">—</span></td>
                  <td style="text-align:right"><span class="mono fs-12 text-2">—</span></td>
```

Replace with:

```html
                  <td>
                    <span class="mono fs-12 text-2" :title="inst.last_exit_sync">{{ fmtDate(inst.last_exit_sync) }}</span>
                    <span v-if="inst.last_errors?.length" style="margin-left:6px;cursor:pointer;color:var(--warn)"
                      :title="inst.last_errors.join('\n')"
                      @click="expandedError = expandedError === inst.name ? null : inst.name">⚠</span>
                  </td>
                  <td>
                    <span class="mono fs-12 text-2" :title="inst.last_startup_sync">{{ fmtDate(inst.last_startup_sync) }}</span>
                  </td>
                  <td style="text-align:right">
                    <span class="mono fs-12 text-2">{{ inst.synced_size_mb ? inst.synced_size_mb + ' MB' : '—' }}</span>
                  </td>
```

- [ ] **Step 7: Add error expansion row after each instance row**

After the closing `</tr>` of the instance row (inside `<tbody>`), add:

```html
<tr v-if="expandedError === inst.name && inst.last_errors?.length" :key="inst.name + '-err'">
  <td colspan="7" style="padding:8px 16px;background:var(--err-soft)">
    <div v-for="e in inst.last_errors" :key="e" class="fs-12" style="color:var(--err)">{{ e }}</div>
  </td>
</tr>
```

- [ ] **Step 8: Add the module settings modal teleport**

After the existing `<!-- Setup wizard modal -->` teleport block, add:

```html
<!-- Module settings modal -->
<teleport to="body">
  <div v-if="showModuleSettings"
    style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px"
    @mousedown.self="showModuleSettings = false">
    <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:520px;overflow:hidden">
      <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between">
        <div class="fw-600 text-0" style="font-size:15px">Instance Sync Settings</div>
        <button class="icon-btn" @click="showModuleSettings = false"><span v-html="icon('x',13)"></span></button>
      </div>
      <div style="padding:20px 24px;display:flex;flex-direction:column;gap:14px">
        <div>
          <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Prism Instances Path</div>
          <input v-model="moduleSettingsForm.instances_path" class="input input-mono" placeholder="C:\Users\…\PrismLauncher\instances">
          <div class="fs-12 text-3 mt-4">Folder containing all Prism instance subfolders.</div>
        </div>
        <div>
          <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Sync Folder Path</div>
          <input v-model="moduleSettingsForm.sync_path" class="input input-mono" placeholder="C:\Users\…\Nextcloud\Minecraft">
          <div class="fs-12 text-3 mt-4">Folder where instance files will be synced (e.g. Nextcloud).</div>
        </div>
        <div v-if="moduleSettingsError" style="padding:8px 12px;border-radius:6px;background:var(--err-soft);color:var(--err);font-size:12px">{{ moduleSettingsError }}</div>
      </div>
      <div style="padding:16px 24px;border-top:1px solid var(--line);display:flex;align-items:center;justify-content:space-between">
        <button class="ghost-link" style="color:var(--err);font-size:12px" @click="resetModuleSync">Reset sync config</button>
        <div class="flex items-center gap-8">
          <button class="btn btn-ghost btn-sm" @click="showModuleSettings = false">Cancel</button>
          <button class="btn btn-primary btn-sm" :disabled="moduleSettingsSaving" @click="saveModuleSettings">
            {{ moduleSettingsSaving ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</teleport>
```

- [ ] **Step 9: Launch and test**

```
python main.py
```

- Navigate to Instance Sync page
- Gear icon visible next to "Instance Sync" title — click opens module settings modal
- Last sync columns show relative timestamps (or `—` if no sync run yet)
- ⚠ icon appears in rows with errors, clicking expands error row
- Unconfigured state: "Setup Instance Sync" button opens module settings modal

- [ ] **Step 10: Commit**

```bash
git add frontend/pages/instance_sync.js
git commit -m "feat: module settings icon, populated last sync columns, error expansion on Instance Sync page"
```

---

### Task 6: app.js — stream selector in Version & Updates modal + PAT field in Help & Debug modal

**Files:**
- Modify: `frontend/app.js`

**Context:** `app.js` `setup()` currently has `showVersionModal`, `checkingUpdate`, `manualUpdateResult`, `openVersionModal`, `checkUpdateManual`, `showDebugModal`, `hostInfo`, `resetConfirm`, `resetResult`, `openDebugModal`, `confirmReset`. The Version & Updates modal is a `<teleport>` block. The Help & Debug modal is another `<teleport>` block after it. `VALID_STREAMS` in Python is `("dev", "alpha", "beta", "prerelease", "release")` — for UI show: `release`, `beta`, `alpha`, `dev` (skip `prerelease` in UI, it's a legacy alias).

- [ ] **Step 1: Add stream and PAT state to setup() in app.js**

After the `confirmReset` function, add:

```js
const updateStream = ref('alpha')   // loaded on modal open
const streamSaving = ref(false)

const setStream = async (stream) => {
  streamSaving.value = true
  try {
    await window.__apiReady
    await window.pywebview.api.set_update_stream_api(stream)
    updateStream.value = stream
    manualUpdateResult.value = null  // force re-check on next "Check for updates"
  } catch(e) {}
  streamSaving.value = false
}

const gitlabPat = ref('')
const savePat = async () => {
  try {
    await window.__apiReady
    await window.pywebview.api.set_gitlab_pat_api(gitlabPat.value)
  } catch(e) {}
}
```

- [ ] **Step 2: Load stream on modal open**

Find `openVersionModal`:
```js
const openVersionModal = () => {
  showMenu.value = false
  manualUpdateResult.value = null
  showVersionModal.value = true
}
```

Replace with:
```js
const openVersionModal = async () => {
  showMenu.value = false
  manualUpdateResult.value = null
  showVersionModal.value = true
  try {
    await window.__apiReady
    updateStream.value = await window.pywebview.api.get_update_stream_api()
  } catch(e) {}
}
```

- [ ] **Step 3: Load stream and PAT when debug modal opens**

Find `openDebugModal`:
```js
const openDebugModal = async () => {
  resetConfirm.value = null
  resetResult.value = {}
  showDebugModal.value = true
  try {
    await window.__apiReady
    hostInfo.value = await window.pywebview.api.get_host_info()
  } catch(e) { hostInfo.value = null }
}
```

Replace with:
```js
const openDebugModal = async () => {
  resetConfirm.value = null
  resetResult.value = {}
  showDebugModal.value = true
  try {
    await window.__apiReady
    const [info, stream, pat] = await Promise.all([
      window.pywebview.api.get_host_info(),
      window.pywebview.api.get_update_stream_api(),
      window.pywebview.api.get_gitlab_pat_api(),
    ])
    hostInfo.value = info
    updateStream.value = stream
    gitlabPat.value = pat
  } catch(e) { hostInfo.value = null }
}
```

- [ ] **Step 4: Add new refs to return {} in setup()**

Add:
```js
updateStream, streamSaving, setStream, gitlabPat, savePat,
```

- [ ] **Step 5: Add stream selector to Version & Updates modal template**

In the Version & Updates modal, after the Status row (`<div style="display:flex;justify-content:space-between;align-items:center">` containing `Status` label), add:

```html
<div style="display:flex;justify-content:space-between;align-items:center">
  <span class="text-2 fs-13">Update stream</span>
  <div class="sub-tabs" style="font-size:11px">
    <button v-for="s in ['release','beta','alpha','dev']" :key="s"
      class="sub-tab" :class="{ active: updateStream === s }"
      :disabled="streamSaving"
      @click="setStream(s)"
      style="padding:3px 10px;font-size:11px;text-transform:capitalize">
      {{ s }}
    </button>
  </div>
</div>
```

- [ ] **Step 6: Add GitLab PAT field to Help & Debug modal**

In the Help & Debug modal, after the Diagnostics section (the Upload Debug Data block), add:

```html
<!-- Dev stream PAT (only shown when stream is 'dev') -->
<div v-if="updateStream === 'dev'">
  <div class="kicker" style="margin-bottom:10px">Dev Stream Access</div>
  <div style="padding:8px 12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--line)">
    <div class="fs-13 fw-500 text-0" style="margin-bottom:6px">GitLab Dev Token</div>
    <input
      v-model="gitlabPat"
      type="password"
      class="input input-mono"
      placeholder="glpat-…"
      style="font-size:12px"
      @blur="savePat">
    <div class="fs-12 text-3" style="margin-top:6px">Required to download builds from private GitLab CI. Only relevant on Dev stream.</div>
  </div>
</div>
```

- [ ] **Step 7: Launch and test**

```
python main.py
```

- Three-dot menu → Version & Updates → stream selector shows current stream, clicking changes it
- Three-dot menu → Help & Debug → if stream is `dev`, GitLab PAT field appears; if `alpha`/`beta`/`release`, field hidden
- Change stream to `dev` in Version & Updates, reopen Help & Debug → PAT field visible

- [ ] **Step 8: Commit**

```bash
git add frontend/app.js
git commit -m "feat: update stream selector in Version & Updates modal, GitLab PAT field in Help & Debug modal"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ Delta exit sync — Task 1 Step 2
- ✅ `last_result.json` written after both sync functions — Task 1 Steps 3+4
- ✅ `read_last_result` / `write_last_result` helpers — Task 1 Step 1
- ✅ `get_instance_detail` API — Task 2 Step 1
- ✅ `archive_instance_move_only` API — Task 2 Step 2
- ✅ Update stream API methods — Task 2 Step 3
- ✅ `get_instance_sync_data` includes last_result per row — Task 2 Step 4
- ✅ `instance_sync_configured` in `get_home_data` — Task 4 Step 1
- ✅ Expandable rows with lazy-load — Task 4 Steps 2+5+6
- ✅ Row detail: last sync, file count, size, instance folder size, pack info, errors — Task 4 Step 6
- ✅ Gear modal danger zone with Archive + Archive (Move only) + confirmations — Task 4 Steps 7+8
- ✅ Greyed toggles with "Configure →" shortcut — Task 4 Step 7
- ✅ Pack update shortcut in gear modal — Task 4 Step 8
- ✅ CSS: expandable row, danger zone, disabled-hint — Task 3
- ✅ Module settings icon + modal on Instance Sync page — Task 5 Steps 4+5+8
- ✅ Last sync timestamps + size columns populated — Task 5 Step 6
- ✅ Error indicator with expand — Task 5 Steps 6+7
- ✅ Unconfigured screen uses module settings modal — Task 5 Step 4
- ✅ Stream selector in Version & Updates modal — Task 6 Steps 5
- ✅ GitLab PAT in Help & Debug, dev-stream-only — Task 6 Step 6

**2. Placeholder scan:** None found. All code blocks are complete.

**3. Type consistency:**
- `get_instance_detail` returns `last_exit_errors` and `last_startup_errors` (arrays). Task 4 Step 6 uses `rowDetail[inst.name].data.last_exit_errors` — consistent.
- `archive_instance_move_only` returns `{ok, error?}` — same shape as `archive_instance`. `doArchive` checks `r.ok` — consistent.
- `get_update_stream_api` returns a string. `setStream` receives a string. `updateStream` ref holds a string — consistent.
- `fmtDate` defined in both Task 4 (home.js) and Task 5 (instance_sync.js) independently — each file owns its own copy, no shared module. Correct for this codebase pattern.
- `get_instance_sync_data` now returns `last_exit_sync`, `last_startup_sync`, `last_errors`, `synced_size_mb` per instance. Task 5 Step 6 reads `inst.last_exit_sync`, `inst.last_errors`, `inst.synced_size_mb` — consistent.
