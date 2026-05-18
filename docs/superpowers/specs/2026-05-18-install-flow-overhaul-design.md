# Install Flow Overhaul — Design Spec

## Goal

Extend the Pack Registry install flow to support server pack downloads and give users control over which client-side mods are included in a client install.

## Architecture

Two new modals added to `pack_registry.js`, following the existing conflict modal pattern (teleport to body, full-screen backdrop). One new Python method (`download_server_pack`) and one small addition to `install_pack` (`excluded_mods` param). No changes to publish flow, metadata schema, or GitLab storage.

**Tech stack:** Vue 3 ESM, PyWebView API, existing progress event system.

---

## Install Card Changes

The Browse tab Install card gains one new button alongside the existing client install controls:

```
[ Create new instance ]  [ Install to existing ]      [ Download server pack ]
```

"Download server pack" is visually separate (ghost or secondary style) to signal it's a different path. It is always visible when a pack version is selected, regardless of whether the pack has server-tagged mods.

---

## Client Path — Mod Review Modal

### Trigger

When the user clicks Install (either mode) and the selected version has at least one mod with `side === 'client'`, the Client Mod Review modal opens instead of immediately calling `install_pack`.

If no client-tagged mods exist, install proceeds immediately as today.

### Layout

- **Header:** "Client-only mods" + subtitle: "These mods are client-side only. Deselect any you don't want installed."
- **Body:** Scrollable list of client mods only
  - Column header with toggle-all checkbox
  - Each row: checkbox (default: checked) + mod name (`.jar` extension stripped)
- **Footer:** "X of Y selected" count label | Cancel button | Install button

### State

```js
showClientModModal: ref(false)
clientModList: ref([])  // [{ file: string, name: string, include: bool }]
```

Populated from `selectedVersionObj.metadata.mods` filtered to `side === 'client'` when modal opens. All `include` default to `true`.

### Behaviour

- **Confirm:** calls `install_pack` with `excluded_mods` = `clientModList.filter(m => !m.include).map(m => m.file)`
- **Cancel:** modal closes, install does not proceed

### Backend change — `install_pack`

Accepts new optional param `excluded_mods: list[str]` (default `[]`). During mod extraction, any file in `mods/` whose filename is in `excluded_mods` is skipped. Applied in addition to existing `skip_files` logic.

---

## Server Path — Server Download Modal

### Trigger

User clicks "Download server pack" in the Install card.

### Modal steps

#### Step 1 — Destination

- Folder path text input, pre-filled with user's Downloads folder (`~/Downloads`)
- "Browse…" button → calls `pick_folder()` API → updates input
- Toggle: **Save as zip** (default) / **Extract to folder**
- Next → button

#### Step 2 — Content

- Static label: "Required + server-side mods — always included"
- Checkbox: **Include config files** (default: ON)
- Info note: "Saves, resource packs, and shader packs are excluded from server packs."
- ← Back / **Confirm & Download** button

#### Step 3 — Progress

- Progress steps: Download pack → Build server pack → Save to folder
- On success: green summary + full destination path
- On error: red summary with error message
- Close button (always shown after completion)

### State

```js
showServerModal: ref(false)
serverModalStep: ref(1)          // 1 | 2 | 3
serverDest: ref('')              // pre-filled with Downloads path
serverAsZip: ref(true)
serverIncludeConfig: ref(true)
serverProgress: ref([...])       // 3 steps
serverSummary: ref(null)         // { tone, text }
```

### Backend — `download_server_pack(params)`

New method on the `Api` class. Runs in a daemon thread, emits progress events via `_emit`.

**Params:**
```python
{
  "repo_id": str,
  "pack_name": str,
  "version": str,
  "dest_folder": str,       # absolute path chosen by user
  "as_zip": bool,           # True = write .zip, False = extract to folder
  "include_config": bool,
}
```

**Filter logic:**
- Include `mods/` entries where `side` is `"required"` or `"server"` (from metadata.json)
- Include `config/` tree only if `include_config=True`
- Always exclude: `saves/`, `shaderpacks/`, `resourcepacks/`
- Always exclude: `instance.cfg`, `mmc-pack.json` (Prism instance files)

**Output (zip):** `{dest_folder}/{slug}-{version}-server.zip`

**Output (raw):** folder `{dest_folder}/{slug}-{version}-server/` containing filtered files

**Progress steps:**
- Step 0: "Download pack" — download zip from GitLab
- Step 1: "Build server pack" — filter content in-memory
- Step 2: "Save to folder" — write zip or extract files to dest

### Backend — `pick_folder()`

New method on `Api`:
```python
def pick_folder(self) -> str | None:
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result:
        return result[0]
    return None
```

---

## Progress Event Routing

The existing `__onProgress` handler in `pack_registry.js` routes events to the active tab's progress display. Server download progress uses a dedicated `serverProgress`/`serverSummary` state inside the server modal (step 3). A new `type: 'server_pack'` event type is used to distinguish from install/publish events.

Client mod review does not add any new progress routing — it feeds into the existing install progress flow.

---

## Backlog (out of scope for this implementation)

- **Publisher-controlled client mod defaults:** allow publisher to mark individual client-side mods as recommended (checked by default) vs optional (unchecked by default) in the mod tags table. Affects default `include` state in the Client Mod Review modal.

---

## Files Changed

| File | Change |
|---|---|
| `frontend/pages/pack_registry.js` | Add `showClientModModal`, `clientModList`, server modal state + all modal templates; modify `checkAndInstall` to gate on client mods; add `download_server_pack` call |
| `main.py` | Add `excluded_mods` param to `install_pack`; add `download_server_pack()` method; add `pick_folder()` method |
