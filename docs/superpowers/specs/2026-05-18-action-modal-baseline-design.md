# Action Modal Baseline — Design Spec

## Goal

Replace all inline progress displays in the app with a consistent modal overlay pattern. Every action (install, publish, update, server download, archive, sync) follows the same three-phase modal lifecycle: Summary → Transition → Progress.

## Architecture

A reusable `ActionModal` Vue 3 ESM component (`frontend/components/action-modal.js`) handles all rendering. Each flow in its parent page manages its own state object and passes props. Progress event routing moves from tab-based heuristics to a `flow` field on each emitted event.

**Tech stack:** Vue 3 ESM, existing `_emit` progress event system, CSS transitions.

---

## Modal Lifecycle

### Phase 1 — Summary

Shown before the action starts. User reads what will happen and confirms.

**Layout:**
- Header: action title (e.g. "Install Pack")
- Body:
  - Summary line: key params in plain English (e.g. "Create Combined v1.2 → new instance my-pack")
  - If `deletions` is non-empty: collapsed row "X files will be deleted/overwritten" with a chevron → expands to exact file list (same scrollable pattern as conflict modal file list)
  - If `deletions` is empty: no Show more row
- Footer: Cancel button + Confirm button

### Phase 2 — Transition

Triggered when user clicks Confirm. Summary content fades out (~200ms CSS opacity transition), progress content fades in. No intermediate loading state.

### Phase 3 — Progress

**Simple view (default):**
- Step indicators: same `progress-step` pattern as today (idle/run/done/err icons + label + detail)
- "Show more" button below steps — expands log panel

**Expanded view (Show more):**
- Scrollable log panel below steps
- Log lines appended as progress events arrive
- Format: `[Step name] detail text` — one line per state change per step
- When a step transitions (e.g. running → done), the existing line for that step is updated in-place, not duplicated

**Footer:**
- While running: no buttons (intentional — action is in flight)
- On success: Close button
- On error: Close + Retry buttons (Retry re-emits `retry` event to parent, parent re-triggers the action)

---

## ActionModal Component

**File:** `frontend/components/action-modal.js`

### Props

```js
{
  show:      Boolean,   // controls teleport visibility
  title:     String,    // e.g. "Install Pack"
  summary:   String,    // e.g. "Create Combined v1.2 → my-pack (new instance)"
  deletions: Array,     // string[] — filenames/paths; empty = no Show more on summary
  steps:     Array,     // [{label, state, detail}] — state: 'idle'|'run'|'done'|'err'
  logs:      Array,     // string[] — appended log lines
  phase:     String,    // 'summary' | 'progress'
  done:      Boolean,   // shows Close button
  error:     Boolean,   // shows Retry button alongside Close
}
```

### Emits

```js
'confirm'  // user clicked Confirm — parent transitions to progress + starts action
'cancel'   // user clicked Cancel or Close — parent resets modal state
'retry'    // user clicked Retry — parent resets steps/logs and re-triggers the action directly (skips summary phase)
```

### Template structure

```
<teleport to="body">
  <div v-if="show" class="modal-backdrop">
    <div class="modal-card">
      <!-- Header -->
      <div class="modal-header">{{ title }}</div>

      <!-- Body: summary phase -->
      <div v-if="phase === 'summary'" class="modal-body modal-fade">
        <div class="summary-line">{{ summary }}</div>
        <div v-if="deletions.length" class="deletions-row">
          <span>{{ deletions.length }} file(s) will be deleted/overwritten</span>
          <button @click="showDeletions = !showDeletions">{{ showDeletions ? '▲' : '▼' }}</button>
          <div v-if="showDeletions" class="deletions-list">
            <div v-for="f in deletions" class="mono fs-12">{{ f }}</div>
          </div>
        </div>
      </div>

      <!-- Body: progress phase -->
      <div v-if="phase === 'progress'" class="modal-body modal-fade">
        <div v-for="s in steps" class="progress-step">...</div>
        <button @click="showLogs = !showLogs">{{ showLogs ? 'Show less' : 'Show more' }}</button>
        <div v-if="showLogs" class="log-panel">
          <div v-for="line in logs" class="mono fs-11">{{ line }}</div>
        </div>
      </div>

      <!-- Footer -->
      <div class="modal-footer">
        <template v-if="phase === 'summary'">
          <button @click="$emit('cancel')">Cancel</button>
          <button @click="$emit('confirm')">Confirm</button>
        </template>
        <template v-if="phase === 'progress' && done">
          <button v-if="error" @click="$emit('retry')">Retry</button>
          <button @click="$emit('cancel')">Close</button>
        </template>
      </div>
    </div>
  </div>
</teleport>
```

Component has two internal refs: `showDeletions: ref(false)`, `showLogs: ref(false)`. Both reset to false when `phase` changes.

---

## Progress Event Routing

### Python side — add `flow` field to all emits

Every `_emit` call in `publish_pack`, `install_pack`, `download_server_pack` gets a `flow` field:

```python
self._emit({"type": "step", "flow": "install", "step": 0, "state": "running", "detail": ""})
self._emit({"type": "summary", "flow": "install", "text": "Installed ...", "tone": "ok"})
```

Valid flow values: `"install"`, `"publish"`, `"server_pack"` (already has its own type), `"archive"`, `"schematic"`

### JS side — route by flow field

```js
window.__onProgress = (event) => {
  if (_baseHandler) _baseHandler(event)
  const flow = event.flow
  if (flow === 'install') routeToModal(installModal, event)
  else if (flow === 'publish') routeToModal(publishModal, event)
  // server_pack already handled separately
}

const routeToModal = (modal, event) => {
  if (event.type === 'reset') {
    modal.value.steps = modal.value.steps.map(s => ({ ...s, state: 'idle', detail: '' }))
    modal.value.logs = []
  } else if (event.type === 'step') {
    const s = modal.value.steps[event.step]
    if (s) {
      const state = event.state === 'ok' ? 'done' : event.state === 'error' ? 'err' : 'run'
      s.state = state
      s.detail = event.detail || ''
      // Update or append log line
      const label = s.label
      const logLine = `[${label}] ${event.detail || state}`
      const existingIdx = modal.value.logs.findLastIndex(l => l.startsWith(`[${label}]`))
      if (existingIdx >= 0) modal.value.logs[existingIdx] = logLine
      else modal.value.logs.push(logLine)
    }
  } else if (event.type === 'summary') {
    modal.value.done = true
    modal.value.error = event.tone !== 'ok'
    modal.value.logs.push(event.text)
  }
}
```

---

## Pack Registry — Per-Flow State & Summary Lines

### Install flow (`installModal`)

```js
installModal.value = {
  show: true, phase: 'summary', done: false, error: false,
  title: 'Install Pack',
  summary: `${packName} v${version} → ${instName} (${mode === 'new' ? 'new instance' : 'existing'})`,
  deletions: [...conflictSkipFiles, ...excludedClientMods],
  steps: INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })),
  logs: [],
}
```

`deletions` populated from: conflict skip list (files marked "keep" = will be overwritten) + client mods deselected in review modal.

### Publish flow (`publishModal`)

```js
publishModal.value = {
  show: true, phase: 'summary', done: false, error: false,
  title: 'Publish Pack',
  summary: `${packName} v${version} from ${instanceName}`,
  deletions: removedMods,   // computed before publish, same as today
  steps: PUBLISH_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })),
  logs: [],
}
```

`removedMods` is already computed client-side by diffing previous metadata — use that value directly.

### Update flow (`updateModal`)

```js
updateModal.value = {
  show: true, phase: 'summary', done: false, error: false,
  title: 'Update Pack',
  summary: `${packName} ${installedVersion} → ${latestVersion} on ${instanceName}`,
  deletions: removedMods,   // from latest version metadata (already fetched in check_conflicts)
  steps: INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })),
  logs: [],
}
```

### Reinstall flow (reuses `updateModal`)

```js
updateModal.value = {
  show: true, phase: 'summary', done: false, error: false,
  title: 'Reinstall Pack',
  summary: `${packName} v${installedVersion} → ${instanceName}`,
  deletions: [],
  steps: INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })),
  logs: [],
}
```

---

## What Gets Removed from pack_registry.js

| Removed | Replaced by |
|---|---|
| `installSteps`, `installSummary` refs | `installModal` object |
| `publishSteps` computed, `publishSummary` computed, `publishTone` computed | `publishModal` object |
| Per-row `instanceProgress` dict + `_initInstProgress()` | `updateModal` object |
| Inline progress card in Browse tab | `ActionModal` component |
| Inline progress card + right column in Publish tab | `ActionModal` component |
| Per-row `<tr>` progress in Instances tab | `ActionModal` component |
| Tab-based routing in `__onProgress` (`tab.value === 'browse'`) | `event.flow` routing |

---

## CSS additions (style.css)

```css
.modal-fade {
  transition: opacity .2s ease;
}
.log-panel {
  max-height: 200px;
  overflow-y: auto;
  background: var(--bg-0);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 10px;
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
```

---

## Scope

This spec covers:
1. `ActionModal` component (new file)
2. Pack Registry flows: install, publish, update, reinstall
3. Python `_emit` changes to add `flow` field
4. CSS additions

**Out of scope for this pass (future):**
- Instance Sync archive/restore flow
- Schematic Sync flow
- Server pack download (already uses modal, wire to ActionModal in a follow-up)

---

## Files Changed

| File | Change |
|---|---|
| `frontend/components/action-modal.js` | New file — ActionModal component |
| `frontend/pages/pack_registry.js` | Replace inline progress with ActionModal; new modal state objects; updated __onProgress routing; updated confirm/install/publish/update functions |
| `frontend/style.css` | Add `.log-panel` and `.modal-fade` |
| `main.py` | Add `flow` field to all `_emit` calls in `install_pack`, `publish_pack` |
