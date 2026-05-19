# Instance Sync Rework — Design Spec

**Date:** 2026-05-18
**Status:** Approved

---

## Goal

Consolidate instance sync information and controls into two surfaces: the Home page instance table (overview + quick settings) and the Instance Sync page (operational detail + module config). Improve sync reliability with delta exit sync and persistent error reporting. Surface update stream and dev PAT settings in the existing three-dot menu modals.

---

## Scope

### In scope
- Home page: expandable instance rows (read-only detail panel), gear modal danger zone (archive actions), gear modal quick settings improvements (greyed-out states with shortcuts, pack update button)
- Instance Sync page: module settings icon/modal (replaces setup wizard location), last sync timestamps + size from manifest, last error display, delta exit sync, `last_result.json` for headless run errors
- Version & Updates modal: update stream selector pill
- Help & Debug modal: GitLab PAT field (dev stream only)

### Out of scope
- Schematic Sync page improvements (separate future spec)
- Settings page / nav changes (deferred)
- Linux compatibility pass (tracked separately)
- Startup sync logic changes (only exit sync gets delta)

---

## Architecture

### New data flow: `last_result.json`

After every headless `--startup` or `--autosync` run, `sync.py` writes a sidecar file alongside `manifest.json`:

```
<sync_path>/instance_sync/<instance_name>/last_result.json
```

Shape:
```json
{
  "mode": "exit" | "startup",
  "timestamp": "2026-05-18T14:32:00",
  "copied": 12,
  "skipped": 304,
  "pruned": 2,
  "errors": ["mods/somemod.jar: permission denied"]
}
```

The Instance Sync page reads this on load. The Home expandable row reads it on first expand.

### New API method: `get_instance_detail(instance_name)`

Returns everything needed for the Home expandable row in one call:

```python
{
  "last_exit_sync": "2026-05-18T14:32:00" | None,
  "last_startup_sync": "2026-05-18T09:15:00" | None,
  "synced_file_count": 316,
  "synced_size_mb": 142.3,
  "last_exit_error": ["mods/somemod.jar: permission denied"] | [],
  "instance_folder_size_mb": 890.4,
  "pack": {
    "name": "Comsicraft",
    "installed_version": "1.3.0",
    "tracked": True,
    "has_update": False,
    "latest_version": "1.3.0"
  } | None
}
```

Reads from: `last_result.json` (timestamps + errors), `manifest.json` (file count + synced size), instance folder on disk (folder size), installed_instances + tracked_packs state (pack info). All reads are local — no network calls.

### Delta exit sync

`run_exit_sync` in `sync.py` currently copies all non-blacklisted files unconditionally. Change: read the existing manifest before copying, skip files where mtime and size match the recorded values. Only copy new, modified, or previously-untracked files. Prune logic unchanged.

---

## Feature Details

### 1. Home — Expandable instance rows

**Row click behaviour:** Clicking anywhere on a row (except the gear button) toggles an inline detail panel. The gear button stops click propagation so it doesn't also toggle the row.

**Detail panel — load on first expand:**
- Shows a spinner while `get_instance_detail` is in flight
- Caches result — subsequent expands of the same row use cached data until Home is refreshed
- Refresh button in panel header re-fetches

**Detail panel — content (read-only):**

| Field | Source |
|-------|--------|
| Last Exit Sync | `last_result.json` (mode=exit) timestamp |
| Last Startup Sync | `last_result.json` (mode=startup) timestamp |
| Synced files / size | `manifest.json` file count + sum of sizes |
| Instance folder size | `du` of Prism instance folder on disk |
| Last sync error | `last_result.json` errors array, shown in red if non-empty |
| Installed pack | state: pack name + version |
| Pack tracking | state: tracked yes/no |
| Update available | state: latest_version vs installed_version |

If Instance Sync is not configured, the sync fields show "Not configured" with a link to Instance Sync page.

**Pack update shortcut:** If `has_update` is true, an "Update available — vX.Y.Z" line appears with an "Update" ghost-link that opens Pack Registry → Instances tab (navigates via `$emit('navigate', 'pack_registry')`). Full update flow lives in Pack Registry, not here.

### 2. Home — Gear modal improvements

**Greyed-out toggles with shortcuts:**

- **Exit Sync / Startup Sync sub-toggles:** Disabled + dimmed if Instance Sync is not configured. Tooltip: "Instance Sync not set up". A small "Configure →" link navigates to Instance Sync page and closes the modal.
- **Pre/Post Launch Hook:** Disabled + dimmed if Instance Sync is not configured (hook requires sync to be meaningful). Same "Configure →" shortcut.
- **Track for Updates:** Only shown if a pack is installed to that instance (existing behaviour, no change).

**Pack update button in quick settings:**
If the instance has an installed pack with an update available, show a button in the modal body (above the Danger Zone): "Update available — vX.Y.Z → Update Pack". Clicking navigates to Pack Registry and closes the modal. This is a navigation shortcut, not an inline update trigger.

**Danger Zone section** (bottom of modal, visually separated):

A red-tinted section header "Danger Zone" separates it from the toggles above.

Two buttons, both red-bordered:

1. **Archive** — existing behaviour: exit sync → create zip backup in instances dir → delete instance folder. Single click triggers an inline confirmation row ("This will remove the instance from Prism. A zip backup will be created. Continue?" + Confirm / Cancel).

2. **Archive (Move only)** — exit sync → delete instance folder, no zip. Single click triggers a stronger confirmation: "Warning: Without a zip backup, this instance cannot be recovered if the sync folder is lost or corrupted. Are you sure?" + "Yes, move only" (red) / Cancel. No second chances.

Both archive actions close the modal on success and reload the Home data.

### 3. Instance Sync page — Module settings icon

A settings gear icon button appears next to the "Instance Sync" page title in the header, right-aligned. Clicking opens the **Instance Sync Settings modal**.

**Instance Sync Settings modal** contains:
- Prism instances path (editable input + current value)
- Sync folder path (editable input + current value)
- Save button (calls existing `setup_instance_sync` API)
- A "Reset instance sync config" danger link at the bottom (calls `reset_module('instance_sync')` — same as Help & Debug reset)

The "Setup Instance Sync" button on the unconfigured state screen opens this same modal. The modal works whether sync is configured or not.

### 4. Instance Sync page — Operational improvements

**Last sync columns (currently `—`):**

Read `last_result.json` per instance during `get_instance_sync_data`. Add to each instance row:
```python
{
  "last_exit_sync": "2026-05-18T14:32:00" | None,
  "last_startup_sync": "2026-05-18T09:15:00" | None,
  "last_error": ["..."] | [],
  "synced_size_mb": 142.3,
}
```

Display timestamps as relative ("2h ago") with absolute on hover. Size shown as "142 MB".

**Last error indicator:**

If `last_error` is non-empty, show a warning icon (⚠) in the row. Clicking the icon expands an inline error panel below the row showing the full error list.

**Size column:** Total synced size from manifest, shown as human-readable MB/GB.

**Delta exit sync (`run_exit_sync` in `sync.py`):**

Before copying, read existing manifest. For each file in `to_copy`:
- If `rel` is in manifest AND `src.stat().st_mtime == manifest[rel]["mtime"]` AND `src.stat().st_size == manifest[rel]["size"]`: skip (no copy needed)
- Otherwise: copy and update manifest entry

Add a `unchanged` counter to the return dict. Log skipped-as-unchanged count.

**`last_result.json` writes:**

Both `run_exit_sync` and `run_startup_sync` write `last_result.json` to `sync_instance_dir` after completing. Written even on partial error — always reflects the most recent run.

The headless entry points in `main.py` (`_execute_instance_plan`) call these functions already — no changes needed to the hook wiring, just to the sync functions themselves.

### 5. Version & Updates modal — Stream selector

Add a segmented pill selector below the current version display:

```
Release  |  Beta  |  Alpha  |  Dev
```

Current stream loaded via new `get_update_stream()` API call on modal open. Saved immediately on change via `set_update_stream(stream)`. Both functions already exist in `core/state.py` — just need `Api` methods.

When stream changes, `manualUpdateResult` resets to null (forces re-check).

### 6. Help & Debug modal — GitLab PAT field

A new "Dev Stream Access" section appears at the bottom of the Help & Debug modal, **only visible when the active update stream is `dev`**. This requires the modal to know the current stream — load it alongside `hostInfo` when the modal opens.

The section contains:
- Label: "GitLab Dev Token"
- A mono password input (type=password, toggleable to text)
- Current value loaded via new `get_gitlab_pat()` API method (returns masked value or empty)
- Saved on blur via new `set_gitlab_pat(pat)` API method
- A note: "Required to download builds from private GitLab CI. Only relevant on Dev stream."

`get_gitlab_pat` and `set_gitlab_pat` already exist in `core/state.py` — just need `Api` wrapper methods.

---

## File Map

| File | Changes |
|------|---------|
| `modules/instance_sync/sync.py` | Delta exit sync logic; write `last_result.json` after every run |
| `main.py` | New API: `get_instance_detail`, `get_update_stream`, `set_update_stream`, `get_gitlab_pat`, `set_gitlab_pat`; update `get_instance_sync_data` to include last_result data |
| `frontend/pages/home.js` | Expandable rows + detail panel; gear modal danger zone + greyed toggles with shortcuts + pack update shortcut |
| `frontend/pages/instance_sync.js` | Module settings icon + modal; populate last sync / size / error columns; error indicator |
| `frontend/app.js` | Version & Updates modal: stream selector; Help & Debug modal: PAT field + stream-aware visibility |
| `frontend/style.css` | Expandable row styles; danger zone styles |

---

## Error Handling

- `get_instance_detail`: if sync not configured, sync fields return null (not an error). If manifest missing, synced_file_count=0, synced_size_mb=0. If instance folder missing from disk, instance_folder_size_mb=null.
- `last_result.json` write failures are logged but do not cause the sync to fail — they are best-effort.
- Archive (Move only): if exit sync fails before deletion, abort — do not delete the instance. Return error to modal.
- Archive: if zip creation fails, abort — do not delete the instance. Return error to modal.
- Stream selector: invalid stream values rejected by existing `set_update_stream` validation in `core/state.py`.

---

## What Does NOT Change

- Startup sync logic (already delta, no change)
- Archive/restore Python logic (only the UI trigger point changes)
- Pack Registry install/update flow (Home links to it, doesn't duplicate it)
- Schematic Sync page (untouched)
- Prism hook wiring (`--startup`/`--autosync` CLI args, `patch_exit_commands`)
- Blacklist logic
