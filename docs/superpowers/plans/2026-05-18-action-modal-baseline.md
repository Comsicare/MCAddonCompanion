# Action Modal Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all inline progress displays in Pack Registry with a reusable ActionModal component that shows a summary before each action, then transitions to a live progress + log view.

**Architecture:** A new `frontend/components/action-modal.js` Vue 3 ESM component handles all rendering via props/emits. Each flow in `pack_registry.js` manages its own state object (`installModal`, `publishModal`, `updateModal`). Python emits gain a `flow` field so JS routes events by flow instead of by active tab. Existing inline progress markup and state refs are removed.

**Tech Stack:** Vue 3 ESM (no build step), PyWebView `_emit` progress events, CSS opacity transitions.

---

## File Map

| File | What changes |
|---|---|
| `frontend/components/action-modal.js` | **New** — ActionModal component |
| `frontend/style.css` | Add `.log-panel`, `.modal-fade` CSS |
| `main.py` | Add `"flow": "install"` / `"flow": "publish"` to every `_emit` in `install_pack` and `publish_pack` |
| `frontend/pages/pack_registry.js` | Replace inline progress state + markup with modal state objects + ActionModal; rewrite `__onProgress` routing; update all flow trigger functions |

---

### Task 1: CSS — add log-panel and modal-fade

**Files:**
- Modify: `frontend/style.css`

- [ ] **Step 1: Add the two new CSS rules**

Open `frontend/style.css`. Find the end of the file and append:

```css
/* action modal */
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

- [ ] **Step 2: Commit**

```bash
git add frontend/style.css
git commit -m "feat: add log-panel and modal-fade CSS for action modal"
```

---

### Task 2: Create ActionModal component

**Files:**
- Create: `frontend/components/action-modal.js`

**Context:** This is the only place modal rendering lives. It receives all data as props and emits three events: `confirm`, `cancel`, `retry`. It has two internal refs (`showDeletions`, `showLogs`) that reset whenever `phase` changes. The teleport pattern matches the existing conflict/server modals in `pack_registry.js`.

The `progress-step` CSS class and `progress-step-icon` classes are already defined in `style.css` — use them exactly as the existing modals do. The `icon()` helper is NOT available inside this component (it lives on the pack_registry setup scope). Use inline SVG characters for the step icons instead: `✓` for done, `✕` for error, and a CSS spin class for running.

- [ ] **Step 1: Create `frontend/components/` directory and the file**

```bash
mkdir -p "C:/Users/comsi/Nextcloud/Dev/MCAddonCompanion/frontend/components"
```

Then create `frontend/components/action-modal.js` with this full content:

```js
import { ref, watch } from '../vue.esm-browser.js'

export default {
  props: {
    show:      { type: Boolean, default: false },
    title:     { type: String,  default: '' },
    summary:   { type: String,  default: '' },
    deletions: { type: Array,   default: () => [] },
    steps:     { type: Array,   default: () => [] },
    logs:      { type: Array,   default: () => [] },
    phase:     { type: String,  default: 'summary' }, // 'summary' | 'progress'
    done:      { type: Boolean, default: false },
    error:     { type: Boolean, default: false },
  },
  emits: ['confirm', 'cancel', 'retry'],
  setup(props) {
    const showDeletions = ref(false)
    const showLogs = ref(false)

    watch(() => props.phase, () => {
      showDeletions.value = false
      showLogs.value = false
    })

    return { showDeletions, showLogs }
  },
  template: `
    <teleport to="body">
      <div v-if="show"
        style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px">
        <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:560px;max-height:80vh;display:flex;flex-direction:column;overflow:hidden">

          <!-- Header -->
          <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line);flex:none">
            <div class="fw-600 text-0" style="font-size:15px">{{ title }}</div>
          </div>

          <!-- Body: summary phase -->
          <div v-if="phase === 'summary'" class="modal-fade" style="overflow-y:auto;flex:1;padding:20px 24px;display:flex;flex-direction:column;gap:12px">
            <div class="fs-14 text-1" style="line-height:1.5">{{ summary }}</div>
            <div v-if="deletions.length">
              <div style="display:flex;align-items:center;gap:8px;cursor:pointer" @click="showDeletions = !showDeletions">
                <span class="fs-13 text-2">{{ deletions.length }} file{{ deletions.length !== 1 ? 's' : '' }} will be deleted/overwritten</span>
                <span class="fs-11 text-3">{{ showDeletions ? '▲' : '▼' }}</span>
              </div>
              <div v-if="showDeletions" style="margin-top:8px;padding:8px 10px;background:var(--bg-0);border:1px solid var(--line);border-radius:6px;max-height:160px;overflow-y:auto;display:flex;flex-direction:column;gap:2px">
                <div v-for="f in deletions" :key="f" class="mono fs-12 text-2">{{ f }}</div>
              </div>
            </div>
          </div>

          <!-- Body: progress phase -->
          <div v-if="phase === 'progress'" class="modal-fade" style="overflow-y:auto;flex:1;padding:16px 24px;display:flex;flex-direction:column;gap:4px">
            <div v-for="(s, i) in steps" :key="i" class="progress-step">
              <span class="progress-step-icon" :class="s.state">
                <span v-if="s.state === 'done'" style="font-size:10px">✓</span>
                <span v-else-if="s.state === 'run'" class="spin" style="font-size:10px">↻</span>
                <span v-else-if="s.state === 'err'" style="font-size:10px">✕</span>
              </span>
              <span class="fs-13 text-0">{{ s.label }}</span>
              <span v-if="s.detail" class="mono fs-11 text-3" style="margin-left:auto">{{ s.detail }}</span>
            </div>
            <button
              class="btn btn-ghost btn-sm"
              style="align-self:flex-start;margin-top:8px;font-size:11px"
              @click="showLogs = !showLogs">
              {{ showLogs ? 'Show less' : 'Show more' }}
            </button>
            <div v-if="showLogs" class="log-panel">
              <div v-for="(line, i) in logs" :key="i" class="mono fs-11 text-2">{{ line }}</div>
            </div>
          </div>

          <!-- Footer -->
          <div style="padding:16px 24px;border-top:1px solid var(--line);display:flex;justify-content:flex-end;align-items:center;gap:8px;flex:none">
            <template v-if="phase === 'summary'">
              <button class="btn btn-ghost btn-sm" @click="$emit('cancel')">Cancel</button>
              <button class="btn btn-primary btn-sm" @click="$emit('confirm')">Confirm</button>
            </template>
            <template v-if="phase === 'progress' && done">
              <button v-if="error" class="btn btn-ghost btn-sm" @click="$emit('retry')">Retry</button>
              <button class="btn btn-ghost btn-sm" @click="$emit('cancel')">Close</button>
            </template>
          </div>

        </div>
      </div>
    </teleport>
  `
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/action-modal.js
git commit -m "feat: add ActionModal reusable component"
```

---

### Task 3: Python — add flow field to install_pack and publish_pack emits

**Files:**
- Modify: `main.py`

**Context:** Every `self._emit(...)` call inside `install_pack` and `publish_pack` needs a `"flow"` key added. This lets the JS router send events to the right modal without relying on which tab is active. `install_pack` gets `"flow": "install"`, `publish_pack` gets `"flow": "publish"`. The `download_server_pack` method already uses its own event types (`server_pack`, `server_pack_summary`) and does not need a flow field.

- [ ] **Step 1: Add flow field to install_pack emits**

In `main.py`, find `install_pack` (line ~729). There are 7 `self._emit` calls inside `_run`. Add `"flow": "install"` to each one:

```python
                self._emit({"type": "reset", "flow": "install"})
```
```python
                self._emit({"type": "step", "flow": "install", "step": 0, "state": "running", "detail": ""})
```
```python
                self._emit({"type": "step", "flow": "install", "step": 0, "state": "ok", "detail": f"{size_mb:.1f} MB"})
```
```python
                self._emit({"type": "step", "flow": "install", "step": 1, "state": "running", "detail": ""})
```
```python
                self._emit({"type": "step", "flow": "install", "step": 1, "state": "ok", "detail": f"{count} files"})
```
```python
                self._emit({"type": "step", "flow": "install", "step": 2, "state": "running", "detail": ""})
```
```python
                self._emit({"type": "step", "flow": "install", "step": 2, "state": "ok", "detail": ""})
```
```python
                self._emit({"type": "summary", "flow": "install", "text": f"Installed {pack_name} v{version}.", "tone": "ok"})
```
```python
                self._emit({"type": "summary", "flow": "install", "text": f"Error: {e}", "tone": "error"})
```

- [ ] **Step 2: Add flow field to publish_pack emits**

Find `publish_pack` (line ~623). Add `"flow": "publish"` to each `self._emit` call inside `_run`. The early-exit emits (before the thread) also get `"flow": "publish"`:

```python
            self._emit({"type": "summary", "flow": "publish", "text": "Pack name is required.", "tone": "error"})
```
```python
            self._emit({"type": "summary", "flow": "publish", "text": "Version is required.", "tone": "error"})
```
```python
            self._emit({"type": "summary", "flow": "publish", "text": "Repo not found.", "tone": "error"})
```
```python
            self._emit({"type": "summary", "flow": "publish", "text": "Instance not found.", "tone": "error"})
```

Inside `_run`:
```python
                self._emit({"type": "reset", "flow": "publish"})
```
```python
                self._emit({"type": "step", "flow": "publish", "step": 0, "state": "running", "detail": ""})
```
```python
                self._emit({"type": "step", "flow": "publish", "step": 0, "state": "ok", "detail": f"{size_mb:.1f} MB"})
```
```python
                self._emit({"type": "step", "flow": "publish", "step": 1, "state": "running", "detail": ""})
```
```python
                self._emit({"type": "step", "flow": "publish", "step": 1, "state": "ok", "detail": ""})
```
```python
                self._emit({"type": "step", "flow": "publish", "step": 2, "state": "running", "detail": ""})
```
```python
                self._emit({"type": "step", "flow": "publish", "step": 2, "state": "ok", "detail": ""})
```
```python
                self._emit({"type": "summary", "flow": "publish", "text": f"Published {pack_name} v{version}.", "tone": "ok"})
```
```python
                self._emit({"type": "summary", "flow": "publish", "text": f"Error: {e}", "tone": "error"})
```

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add flow field to install_pack and publish_pack emits"
```

---

### Task 4: pack_registry.js — modal state objects + routeToModal

**Files:**
- Modify: `frontend/pages/pack_registry.js`

**Context:** Add three modal state objects and the `routeToModal` helper. These replace the existing `installSteps`/`installSummary`/`publishSteps`/`publishSummary`/`publishTone`/`instanceProgress` refs. Do NOT remove the old refs yet — that happens in Task 5 and 6. This task only adds.

- [ ] **Step 1: Import ActionModal at the top of pack_registry.js**

At the very top of `pack_registry.js`, find the existing import line:
```js
import { ref, onMounted, computed, watch } from '../vue.esm-browser.js'
```

Add below it:
```js
import ActionModal from '../components/action-modal.js'
```

- [ ] **Step 2: Add modal state objects after the existing INSTALL_STEPS constant**

Find `const INSTALL_STEPS = ['Download zip', 'Extract files', 'Create instance']` (around line 358). Add after it:

```js
    const _makeModal = () => ({
      show: false, phase: 'summary', done: false, error: false,
      title: '', summary: '', deletions: [],
      steps: [], logs: [],
    })
    const installModal = ref(_makeModal())
    const publishModal = ref(_makeModal())
    const updateModal  = ref(_makeModal())
```

- [ ] **Step 3: Add routeToModal helper**

After the modal state objects, add:

```js
    const routeToModal = (modal, event) => {
      if (event.type === 'reset') {
        modal.value.steps = modal.value.steps.map(s => ({ ...s, state: 'idle', detail: '' }))
        modal.value.logs = []
      } else if (event.type === 'step') {
        const s = modal.value.steps[event.step]
        if (s) {
          s.state = event.state === 'ok' ? 'done' : event.state === 'error' ? 'err' : 'run'
          s.detail = event.detail || ''
          const label = s.label
          const logLine = `[${label}] ${event.detail || s.state}`
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

- [ ] **Step 4: Replace __onProgress routing**

Find the `window.__onProgress = (event) => {` block (around line 607). Replace the entire block with:

```js
    const _baseHandler = window.__onProgress
    window.__onProgress = (event) => {
      if (_baseHandler) _baseHandler(event)

      if (event.type === 'server_pack') {
        if (event.step !== undefined && serverProgress.value[event.step]) {
          serverProgress.value[event.step].state = event.state === 'ok' ? 'done' : event.state === 'error' ? 'err' : 'run'
          serverProgress.value[event.step].detail = event.detail || ''
        }
        return
      }
      if (event.type === 'server_pack_summary') {
        serverSummary.value = { tone: event.tone, text: event.text }
        return
      }

      const flow = event.flow
      if (flow === 'install') {
        routeToModal(installModal, event)
        if (event.type === 'summary' && event.tone === 'ok') loadInstalledInstances()
        return
      }
      if (flow === 'publish') {
        routeToModal(publishModal, event)
        return
      }
    }
```

- [ ] **Step 5: Add new items to return block**

Find the `return {` block (around line 674). Add:
```js
      installModal, publishModal, updateModal, routeToModal,
      ActionModal,
```

- [ ] **Step 6: Commit**

```bash
git add frontend/pages/pack_registry.js
git commit -m "feat: add modal state objects and flow-based onProgress routing"
```

---

### Task 5: pack_registry.js — wire install and browse flows to ActionModal

**Files:**
- Modify: `frontend/pages/pack_registry.js`

**Context:** Replace the install flow's inline progress card with ActionModal. The `checkAndInstall` / `openClientModReview` / `confirmClientModInstall` functions need to open `installModal` in summary phase instead of calling `doInstall` directly. `doInstall` is renamed to `_runInstall` to make clear it's internal. The conflict modal and client mod review modal are removed — their job (gathering skip_files and excluded_mods) moves into the summary modal's `deletions` list.

**Important**: The conflict resolution UI (file-by-file keep/overwrite) is a distinct feature from just showing a count. For now, keep the conflict modal as-is and just add the file list to `installModal.deletions` after conflict resolution. The client mod review modal is also kept as-is — excluded mods are added to `installModal.deletions` after review. Both modals still do their job; the action modal just confirms before the actual install runs.

- [ ] **Step 1: Add openInstallModal function**

After `confirmClientModInstall` (around line 522), add:

```js
    const openInstallModal = (params, skipFiles, excludedMods) => {
      const mode = params.mode === 'new' ? 'new instance' : 'existing instance'
      installModal.value = {
        show: true, phase: 'summary', done: false, error: false,
        title: 'Install Pack',
        summary: `${params.pack_name} v${params.version} → ${params.instance_name} (${mode})`,
        deletions: [...(skipFiles || []), ...(excludedMods || [])],
        steps: INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })),
        logs: [],
        _params: params,
      }
    }

    const confirmInstall = async () => {
      const params = installModal.value._params
      installModal.value.phase = 'progress'
      try {
        await window.__apiReady
        await window.pywebview.api.install_pack(params)
      } catch(e) {
        installModal.value.done = true
        installModal.value.error = true
        installModal.value.logs.push(`Error: ${e}`)
      }
    }

    const retryInstall = async () => {
      installModal.value.steps = INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' }))
      installModal.value.logs = []
      installModal.value.done = false
      installModal.value.error = false
      await confirmInstall()
    }

    const closeInstallModal = () => {
      const wasOk = installModal.value.done && !installModal.value.error
      installModal.value = _makeModal()
      if (wasOk) loadInstalledInstances()
    }
```

- [ ] **Step 2: Update confirmClientModInstall to open install modal**

Find `confirmClientModInstall` (around line 518). Replace it:

```js
    const confirmClientModInstall = async () => {
      showClientModModal.value = false
      const excluded = clientModList.value.filter(m => !m.include).map(m => m.file)
      const params = { ...clientInstallParams.value, excluded_mods: excluded }
      openInstallModal(params, clientInstallParams.value.skip_files || [], excluded)
    }
```

- [ ] **Step 3: Update confirmConflictInstall to route through client mod review then install modal**

`confirmConflictInstall` currently calls `openClientModReview`. That still works — client mod review calls `confirmClientModInstall` which now calls `openInstallModal`. No change needed to `confirmConflictInstall` itself.

Verify by reading the current `confirmConflictInstall`:
```js
    const confirmConflictInstall = async () => {
      showConflictModal.value = false
      const skip = conflictGroups.value.flatMap(g => g.files.filter(f => f.keep).map(f => f.path))
      openClientModReview({ ...conflictInstallParams.value, skip_files: skip })
    }
```
This is already correct — no change needed.

- [ ] **Step 4: Update openClientModReview no-client-mods path to open install modal**

Find `openClientModReview` (around line 492). Currently when no client mods exist it calls `doInstall(params)`. Change to call `openInstallModal` instead:

```js
    const openClientModReview = (params) => {
      const mods = selectedVersionObj.value?.metadata?.mods || []
      const clientMods = mods.filter(m => m.side === 'client')
      if (!clientMods.length) {
        openInstallModal(params, params.skip_files || [], [])
        return
      }
      clientModList.value = clientMods.map(m => ({
        file: m.file,
        name: m.file.replace(/\.jar$/i, ''),
        include: true,
      }))
      clientInstallParams.value = params
      showClientModModal.value = true
    }
```

- [ ] **Step 5: Remove inline install progress markup from Browse tab**

In the template, find the inline progress card in the Browse tab — it looks like:
```html
              <!-- Progress panel -->
              <div v-if="installing || installSummary" class="card">
```

Delete this entire card block (from `<!-- Progress panel -->` through its closing `</div>`).

- [ ] **Step 6: Add ActionModal to template for install flow**

Find the `<!-- ─── CONFLICT MODAL` teleport block. Add BEFORE it:

```html
      <!-- ─── INSTALL ACTION MODAL ──────────────────────────────────────────────── -->
      <action-modal
        :show="installModal.show"
        :title="installModal.title"
        :summary="installModal.summary"
        :deletions="installModal.deletions"
        :steps="installModal.steps"
        :logs="installModal.logs"
        :phase="installModal.phase"
        :done="installModal.done"
        :error="installModal.error"
        @confirm="confirmInstall"
        @cancel="closeInstallModal"
        @retry="retryInstall"
      />
```

- [ ] **Step 7: Add openInstallModal, confirmInstall, retryInstall, closeInstallModal to return block**

```js
      openInstallModal, confirmInstall, retryInstall, closeInstallModal,
```

- [ ] **Step 8: Register ActionModal as a component**

The Vue 3 ESM `defineComponent` pattern used here doesn't have an explicit `components:` option since it's a flat setup() + template string. Instead, register it globally via the app instance. Find where `app.js` creates the Vue app — but since pack_registry.js is a page component loaded via a dynamic import, the simplest approach is to use the component directly in the template using kebab-case tag after adding it to the `components` option.

Change the export default at the top of `pack_registry.js` from:
```js
export default {
  props: ['progress'],
  emits: ['navigate'],
  setup(props) {
```
To:
```js
export default {
  props: ['progress'],
  emits: ['navigate'],
  components: { ActionModal },
  setup(props) {
```

- [ ] **Step 9: Commit**

```bash
git add frontend/pages/pack_registry.js
git commit -m "feat: install flow uses ActionModal summary+progress"
```

---

### Task 6: pack_registry.js — wire publish flow to ActionModal

**Files:**
- Modify: `frontend/pages/pack_registry.js`

**Context:** The publish flow currently uses `publishSteps` (a computed based on `props.progress`), `publishSummary`, `publishTone`, and a `publishing` boolean to drive the inline progress card in the right column of the Publish tab. Replace all of this with `publishModal`.

The tricky part: `removed_mods` is computed on the Python side during `publish_pack`. We need it on the JS side to populate `deletions` in the summary before the publish runs. It's already available: `loadModFiles` fetches `prevMeta` from the previous version and we compute `removed_mods` there. We need to surface that computed list.

- [ ] **Step 1: Add removedMods computed ref**

Find `loadModFiles` (around line 263). After `modFiles.value = tagged`, add a `removedMods` ref declared alongside `modFiles`:

Find:
```js
    const modFiles = ref([])  // [{file: string, side: string}]
```

Change to:
```js
    const modFiles = ref([])  // [{file: string, side: string}]
    const publishRemovedMods = ref([])  // mods that will be in removed_mods on publish
```

Then inside `loadModFiles`, after `(prevMeta.removed_mods || []).forEach(f => excludedSet.add(f))`, add:
```js
              publishRemovedMods.value = prevMeta.removed_mods || []
```

Also reset it when there's no prevMeta — after `modFiles.value = tagged` (the initial assignment), add:
```js
        publishRemovedMods.value = []
```

- [ ] **Step 2: Add openPublishModal, confirmPublish, retryPublish, closePublishModal**

After `closeInstallModal`, add:

```js
    const openPublishModal = () => {
      const f = publishForm.value
      const excluded = modFiles.value.filter(m => m.excluded).map(m => m.file)
      // removed_mods = mods in previous version not in current publish
      const currentFiles = new Set(modFiles.value.filter(m => !m.excluded).map(m => m.file))
      const deletions = publishRemovedMods.value.filter(f => !currentFiles.has(f))
      publishModal.value = {
        show: true, phase: 'summary', done: false, error: false,
        title: 'Publish Pack',
        summary: `${f.pack_name} v${f.version} from ${f.instance_name}`,
        deletions,
        steps: PUBLISH_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })),
        logs: [],
      }
    }

    const confirmPublish = async () => {
      publishModal.value.phase = 'progress'
      const f = publishForm.value
      const mod_tags = {}
      modFiles.value.forEach(m => { if (!m.excluded) mod_tags[m.file] = m.side })
      try {
        await window.__apiReady
        await window.pywebview.api.publish_pack({
          repo_id: f.repo_id,
          instance_name: f.instance_name,
          pack_name: f.pack_name,
          version: f.version,
          description: f.description,
          changenotes: f.changenotes,
          mc_version: f.mc_version,
          loader: f.loader,
          loader_version: f.loader_version,
          categories: f.categories,
          mod_tags,
        })
      } catch(e) {
        publishModal.value.done = true
        publishModal.value.error = true
        publishModal.value.logs.push(`Error: ${e}`)
      }
    }

    const retryPublish = async () => {
      publishModal.value.steps = PUBLISH_STEPS.map(l => ({ label: l, state: 'idle', detail: '' }))
      publishModal.value.logs = []
      publishModal.value.done = false
      publishModal.value.error = false
      await confirmPublish()
    }

    const closePublishModal = () => {
      publishModal.value = _makeModal()
    }
```

- [ ] **Step 3: Replace publish button click handler**

Find the Publish button in the template:
```html
                <button class="btn btn-primary btn-sm flex items-center gap-6"
                  :disabled="publishing || !publishForm.repo_id || !publishForm.instance_name || !publishForm.pack_name || !publishForm.version"
                  @click="publish">
```

Replace with:
```html
                <button class="btn btn-primary btn-sm flex items-center gap-6"
                  :disabled="!publishForm.repo_id || !publishForm.instance_name || !publishForm.pack_name || !publishForm.version"
                  @click="openPublishModal">
```

- [ ] **Step 4: Remove inline progress card from Publish tab**

In the template, find the right-column progress card in the Publish tab:
```html
          <!-- Progress panel -->
          <div style="display:flex;flex-direction:column;gap:12px">
            <div class="card">
              <div class="card-header">
                <div class="card-title" style="margin-top:0">Progress</div>
              </div>
```

Delete this entire right-column div (from the `<!-- Progress panel -->` comment through its closing `</div></div>` that ends the two-column grid). The Publish tab becomes a single-column layout.

Also update the outer grid div for Publish tab from:
```html
        <div style="display:grid;grid-template-columns:1fr 340px;gap:16px;align-items:start">
```
To:
```html
        <div style="display:grid;grid-template-columns:1fr;gap:16px;align-items:start">
```

- [ ] **Step 5: Add ActionModal for publish flow**

After the install action modal tag, add:

```html
      <!-- ─── PUBLISH ACTION MODAL ──────────────────────────────────────────────── -->
      <action-modal
        :show="publishModal.show"
        :title="publishModal.title"
        :summary="publishModal.summary"
        :deletions="publishModal.deletions"
        :steps="publishModal.steps"
        :logs="publishModal.logs"
        :phase="publishModal.phase"
        :done="publishModal.done"
        :error="publishModal.error"
        @confirm="confirmPublish"
        @cancel="closePublishModal"
        @retry="retryPublish"
      />
```

- [ ] **Step 6: Update return block**

Add to return:
```js
      publishRemovedMods, openPublishModal, confirmPublish, retryPublish, closePublishModal,
```

Remove from return: `publishSteps`, `publishSummary`, `publishTone`, `publishing`, `publish`, `clearPublish`

- [ ] **Step 7: Commit**

```bash
git add frontend/pages/pack_registry.js
git commit -m "feat: publish flow uses ActionModal summary+progress"
```

---

### Task 7: pack_registry.js — wire update/reinstall flows to ActionModal

**Files:**
- Modify: `frontend/pages/pack_registry.js`

**Context:** The Instances tab currently uses `instanceProgress` (a dict keyed by instance name) with per-row `<tr>` progress panels. Replace with `updateModal`. Both `installUpdate` and `reinstallInstance` open the modal in summary phase. The update flow needs `removed_mods` from the latest version's metadata — this is already fetched in `check_conflicts` (the metadata is downloaded as part of conflict detection). For reinstall, `deletions` is empty.

- [ ] **Step 1: Add openUpdateModal, confirmUpdate, retryUpdate, closeUpdateModal**

After `closePublishModal`, add:

```js
    const openUpdateModal = (params, removedMods, isReinstall) => {
      const title = isReinstall ? 'Reinstall Pack' : 'Update Pack'
      const summary = isReinstall
        ? `${params.pack_name} v${params.version} → ${params.instance_name}`
        : `${params.pack_name} → v${params.version} on ${params.instance_name}`
      updateModal.value = {
        show: true, phase: 'summary', done: false, error: false,
        title,
        summary,
        deletions: removedMods || [],
        steps: INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })),
        logs: [],
        _params: params,
      }
    }

    const confirmUpdate = async () => {
      const params = updateModal.value._params
      updateModal.value.phase = 'progress'
      try {
        await window.__apiReady
        await window.pywebview.api.install_pack(params)
      } catch(e) {
        updateModal.value.done = true
        updateModal.value.error = true
        updateModal.value.logs.push(`Error: ${e}`)
      }
    }

    const retryUpdate = async () => {
      updateModal.value.steps = INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' }))
      updateModal.value.logs = []
      updateModal.value.done = false
      updateModal.value.error = false
      await confirmUpdate()
    }

    const closeUpdateModal = () => {
      const wasOk = updateModal.value.done && !updateModal.value.error
      updateModal.value = _makeModal()
      if (wasOk) loadInstalledInstances()
    }
```

- [ ] **Step 2: Rewrite installUpdate to open update modal**

Find `installUpdate` (around line 90). Replace it:

```js
    const installUpdate = async (inst) => {
      try {
        await window.__apiReady
        const conflicts = await window.pywebview.api.check_conflicts(
          inst.repo_id,
          inst.pack_name,
          inst.latest_version,
          inst.instance_name
        )
        // Fetch removed_mods from latest version metadata for the summary
        let removedMods = []
        try {
          const versions = await window.pywebview.api.get_versions(inst.repo_id, inst.pack_name)
          const latestVer = versions.find(v => v.version === inst.latest_version)
          removedMods = latestVer?.metadata?.removed_mods || []
        } catch(e) {}

        const params = {
          repo_id: inst.repo_id,
          pack_name: inst.pack_name,
          version: inst.latest_version,
          instance_name: inst.instance_name,
          mode: 'existing',
          track: inst.tracked,
          skip_files: conflicts,
          excluded_mods: [],
        }
        openUpdateModal(params, removedMods, false)
      } catch(e) {}
    }
```

- [ ] **Step 3: Rewrite reinstallInstance to open update modal**

Find `reinstallInstance` (around line 71). Replace it:

```js
    const reinstallInstance = async (inst) => {
      const params = {
        repo_id: inst.repo_id,
        pack_name: inst.pack_name,
        version: inst.installed_version,
        instance_name: inst.instance_name,
        mode: 'new',
        track: inst.tracked,
        skip_files: [],
        excluded_mods: [],
      }
      openUpdateModal(params, [], true)
    }
```

- [ ] **Step 4: Remove per-row progress tr blocks from Instances tab template**

In the template, find the `<template v-for="inst in installedInstances"` block. It currently has a data row `<tr>` followed by a progress `<tr v-if="instanceProgress[inst.instance_name]">`. Delete the entire progress `<tr>` block (keep the data row).

Also delete the `_initInstProgress` function (around line 17) since it's no longer needed.

- [ ] **Step 5: Add ActionModal for update flow**

After the publish action modal tag, add:

```html
      <!-- ─── UPDATE ACTION MODAL ───────────────────────────────────────────────── -->
      <action-modal
        :show="updateModal.show"
        :title="updateModal.title"
        :summary="updateModal.summary"
        :deletions="updateModal.deletions"
        :steps="updateModal.steps"
        :logs="updateModal.logs"
        :phase="updateModal.phase"
        :done="updateModal.done"
        :error="updateModal.error"
        @confirm="confirmUpdate"
        @cancel="closeUpdateModal"
        @retry="retryUpdate"
      />
```

- [ ] **Step 6: Update return block**

Add:
```js
      openUpdateModal, confirmUpdate, retryUpdate, closeUpdateModal,
```

Remove: `instanceProgress`, `_initInstProgress` (already gone from code, just remove from return)

- [ ] **Step 7: Commit**

```bash
git add frontend/pages/pack_registry.js
git commit -m "feat: update and reinstall flows use ActionModal"
```

---

### Task 8: Clean up removed refs from return block and template

**Files:**
- Modify: `frontend/pages/pack_registry.js`

**Context:** After Tasks 5-7, several refs and functions are unused. Remove them cleanly.

- [ ] **Step 1: Remove unused state refs**

Delete these declarations from setup():
- `const installSteps = ref(...)` 
- `const installSummary = ref(null)`
- `const installing = ref(false)`
- `const publishSteps = computed(...)`
- `const publishSummary = computed(...)`
- `const publishTone = computed(...)`
- `const publishing = ref(false)`
- `const instanceProgress = ref({})`
- `const _initInstProgress = ...`
- `const publish = async () => {...}` (replaced by openPublishModal/confirmPublish)
- `const clearPublish = () => {...}`
- `const installPack = async () => {...}` (replaced by openInstallModal flow)
- `const doInstall = async () => {...}` (no longer called)

- [ ] **Step 2: Remove unused items from return block**

Remove from `return {}`:
```
installSteps, installSummary, INSTALL_STEPS,
installing, installPack,
publishSteps, publishSummary, publishTone, publishing,
publish, clearPublish,
instanceProgress,
stepIconState,
```

Keep: `INSTALL_STEPS` constant (still used by modal state init), `PUBLISH_STEPS` (same), `stepIconState` only if still referenced in template — check first.

- [ ] **Step 3: Verify template has no dangling references**

Search the template for any remaining references to removed identifiers:
- `installing` — should be gone (was on the Install button disabled prop)
- `publishSummary`, `publishTone`, `publishSteps` — should be gone (was in progress card)
- `instanceProgress` — should be gone (was in per-row tr)
- `installSummary` — should be gone (was in inline progress card)

Fix any found references.

- [ ] **Step 4: Commit**

```bash
git add frontend/pages/pack_registry.js
git commit -m "chore: remove inline progress state refs replaced by ActionModal"
```

---

### Task 9: Manual integration test + hotpatch

**Files:** No code changes — run and verify.

- [ ] **Step 1: Launch from source**

```bash
cd C:\Users\comsi\Nextcloud\Dev\MCAddonCompanion
start "" "venv/Scripts/pythonw.exe" main.py
```

- [ ] **Step 2: Test install flow**

1. Browse tab → select pack + version → Install → Create new instance
2. Expected: "Install Pack" modal opens in summary phase showing pack name, version, instance name
3. Click Confirm — modal transitions to progress, steps animate, Show more shows log lines
4. On success: Close button appears, clicking it dismisses modal and refreshes Instances tab

- [ ] **Step 3: Test install with client mods**

1. Select pack with client-tagged mods → Install
2. Expected: client mod review modal first, then on confirm → Install Pack summary modal
3. Deselected mods appear in deletions list in summary

- [ ] **Step 4: Test publish flow**

1. Publish tab → fill all fields → click Publish Pack
2. Expected: "Publish Pack" modal opens, summary shows pack + version + instance
3. If updating existing pack: deletions shows removed mods
4. Confirm → progress steps animate → success + Close

- [ ] **Step 5: Test update flow (Instances tab)**

1. Instances tab → find instance with update available → click version button
2. Expected: "Update Pack" modal opens with summary showing version transition
3. Confirm → progress → success

- [ ] **Step 6: Test reinstall flow**

1. Instances tab → find missing instance → click Reinstall
2. Expected: "Reinstall Pack" modal, no deletions shown, Confirm → progress

- [ ] **Step 7: Hotpatch frontend to installed app**

```bash
cp "C:/Users/comsi/Nextcloud/Dev/MCAddonCompanion/frontend/pages/pack_registry.js" "C:/Users/comsi/AppData/Local/MCAddonCompanion/_internal/frontend/pages/pack_registry.js"
cp "C:/Users/comsi/Nextcloud/Dev/MCAddonCompanion/frontend/style.css" "C:/Users/comsi/AppData/Local/MCAddonCompanion/_internal/frontend/style.css"
```

Note: `frontend/components/action-modal.js` is a new file — it must also be copied:
```bash
mkdir -p "C:/Users/comsi/AppData/Local/MCAddonCompanion/_internal/frontend/components"
cp "C:/Users/comsi/Nextcloud/Dev/MCAddonCompanion/frontend/components/action-modal.js" "C:/Users/comsi/AppData/Local/MCAddonCompanion/_internal/frontend/components/action-modal.js"
```
