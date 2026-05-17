# Pack Registry v2 Design

## Goal

Redesign the Pack Registry so one repo can contain multiple named packs, each with proper versioning, changenotes, mod tagging, and tracked-instance auto-update on game launch.

## Architecture

Each named pack maps to one GitLab Generic Package (package name = slugified pack name). Versions are user-supplied strings. A `metadata.json` sidecar is uploaded alongside the ZIP for every version, carrying changenotes and a mod list with side tags. Tracked instances are stored in `state.json` and checked during the startup sync hook, which opens a small prompt window (matching the existing instance sync hook UI).

## Tech Stack

- Python backend: `core/gitlab.py`, `core/sharing.py`, `main.py` Api class
- Frontend: Vue 3 ESM, `frontend/pages/pack_registry.js`
- State: `state.json` (existing pattern)
- Hook integration: `--startup "Name"` CLI path in `main.py`

---

## Section 1: Data Model

### Repo config (`state.json`)

Remove `package_name` field. Pack names are discovered dynamically via `list_all_packages()`.

```json
{
  "id": "abc123",
  "name": "My Packs",
  "base_url": "https://gitlab.example.com",
  "project_url": "https://gitlab.example.com/user/mc-packs",
  "project_id": 3,
  "read_token": "glpat-...",
  "upload_token": "gldt-..."
}
```

### metadata.json schema

```json
{
  "pack_name": "Create Combined",
  "version": "1.0.0",
  "mc_version": "1.20.1",
  "loader": "fabric",
  "description": "My modpack description",
  "changenotes": "Added Create Trains, removed Waystones",
  "categories": ["mods", "config", "servers"],
  "mods": [
    { "name": "create", "file": "create-0.5.1.jar", "side": "required" },
    { "name": "iris", "file": "iris-1.6.4.jar", "side": "client" }
  ],
  "removed_mods": ["waystones-1.2.3.jar"]
}
```

`mods[].name` is derived from the JAR filename (strip version suffix). `mods[].side` is one of `required`, `client`, `server` — set manually by the user in the publish form, defaulting to `required`.

### GitLab package naming

- Pack name slugified: lowercase, spaces → hyphens, strip special chars
- GitLab package name = slug (e.g. `create-combined`)
- ZIP filename = `{slug}-{version}.zip` (e.g. `create-combined-1.0.0.zip`)
- `list_all_packages()` → pack name slugs → display as original pack name from latest metadata

### Tracked instances (`state.json`)

```json
{
  "tracked_packs": [
    {
      "instance_name": "Create Combined",
      "repo_id": "abc123",
      "pack_name": "Create Combined",
      "pack_slug": "create-combined",
      "installed_version": "1.0.0"
    }
  ]
}
```

---

## Section 2: Publish Flow

### Publish form fields

| Field | Type | Default |
|---|---|---|
| Pack name | text | Instance name (pre-filled, editable) |
| Version | text | empty |
| Description | text | Previous version's description if exists, else empty |
| Changenotes | textarea | empty |
| Categories | checkboxes | same as today |
| Mod tags | table (filename → side) | shown only if "mods" category checked; all default to `required` |

Mod tags table: lists all `.jar` files in `mods/` folder. Each row: filename, side selector (`required` / `client` / `server`).

### Publish progress steps

1. Build ZIP
2. Upload ZIP
3. Upload metadata.json

### Backend: `publish_pack` params

```python
{
  "repo_id": "abc123",
  "instance_name": "Create Combined",
  "pack_name": "Create Combined",        # user-supplied, editable
  "version": "1.0.0",                    # user-supplied
  "description": "...",
  "changenotes": "...",
  "categories": {"mods": True, "config": True, ...},
  "mod_tags": {"create-0.5.1.jar": "required", "iris-1.6.4.jar": "client"}
}
```

Backend slugifies `pack_name` to derive GitLab package name. Scans `mods/` folder, merges with `mod_tags` to build `mods` list in metadata. If a previous version exists in the registry, fetches its `mods[]` list and computes `removed_mods` = files present in previous version but absent in the new mod scan. The publish form shows the computed `removed_mods` list for review before publishing (read-only, informational).

---

## Section 3: Browse & Install Flow

### Browse tab layout

- Left column: list of packs (pack name + description from latest version metadata)
- Right panel (pack selected):
  - Pack name, description, mc_version, loader badges
  - Version dropdown — on version select:
    - Changenotes text
    - Mod diff vs previous version (two lists: added mods, removed mods)
    - Mod list with side badges (`required` / `client` / `server`)
  - Install section: two buttons — **Install to existing instance** and **Create new instance**
  - Checkbox: **Track this instance for updates** (shown after install, or as pre-install option)

### Install to existing instance

- Instance dropdown (existing Prism instances)
- Before extraction, delete any `.jar` files listed in the new version's `removed_mods[]` from `minecraft/mods/`. These are publisher-declared removals — user-added mods not in this list are left untouched.
- Conflict detection runs on the remaining files after mod removal (new `check_conflicts` API call)
  - If conflicts: show list of conflicting files + "Proceed anyway" / "Cancel"
  - If no conflicts: proceed directly
- Progress steps: Remove old mods → Detect conflicts → Download ZIP → Extract files → Done

### Create new instance

- Instance name input (pre-filled with pack name, editable)
- Same behavior as current `install_pack` (creates folder, writes `instance.cfg` + `mmc-pack.json`)
- Progress steps: Download ZIP → Extract files → Create instance

### Track for updates

After a successful install (either mode), if the user checked "Track this instance for updates", write a tracked_packs entry to `state.json`.

In the Browse tab, tracked instances show an **Update available** badge next to the pack if a newer version exists than `installed_version`. Clicking it pre-fills the install form with the new version.

### Backend API changes

**`get_versions(repo_id, pack_name)`** — returns list of `{version, metadata}` objects. Fetches metadata for each version to enable changenotes + mod diff display. Mod diff computed in JS by comparing `mods` arrays between consecutive versions.

**`check_conflicts(repo_id, pack_name, version, inst_name)`** — new method. Downloads the ZIP index (without extracting), compares member paths against existing files in the instance's `minecraft/` folder. Returns list of conflicting relative paths.

**`install_pack(params)`** — gains `mode` field: `"existing"` (conflict-checked merge) or `"new"` (current behavior). Also gains `track` boolean — if True, writes tracked_packs entry on success.

**`get_tracked_packs()`** — returns list of tracked pack entries with `has_update` bool (latest GitLab version > installed_version).

**`untrack_pack(instance_name)`** — removes entry from tracked_packs.

---

## Section 4: Startup Sync Hook — Update Prompt

### Trigger

When `--startup "Instance Name"` is called and the instance has a tracked pack entry, before running the normal startup sync, check for updates.

### Update check

Call `list_packages(pack_slug)` on the tracked repo. If latest version > `installed_version`, open the update prompt window instead of (or before) the normal startup sync progress window.

### Prompt window

Small PyWebView window (same style as existing instance sync progress window). Contents:
- Pack name + "Update available" heading
- Installed version → new version
- Changenotes for the new version
- Two buttons: **Update** and **Skip**
- 20-second countdown timer — on expiry, auto-skips

**Update chosen:** runs install_pack in `"existing"` mode (no conflict prompt in this path — silent overwrite). Deletes files listed in new version's `removed_mods[]` from `minecraft/mods/` before extracting. Updates `installed_version` in state.json, closes window, normal startup sync proceeds.

**Skip chosen or timeout:** closes window, normal startup sync proceeds unchanged.

### Frontend

New page: `frontend/pages/update_prompt.js`. The PyWebView window loads `index.html?mode=update_prompt&instance={name}` — `app.js` reads the query string and renders `update_prompt.js` instead of the normal nav shell. Receives pack info via `window.pywebview.api.get_update_prompt_data()`. Emits choice via `window.pywebview.api.submit_update_choice(choice)`.

---

## Out of Scope

- Auto-detection of mod side from JAR metadata (future)
- Conflict backup/restore (future — current design skips or proceeds on conflict)
- Multiple repos per tracked pack
