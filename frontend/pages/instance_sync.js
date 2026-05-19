import { ref, onMounted, computed } from '../vue.esm-browser.js'
import ActionModal from '../components/action-modal.js'

export default {
  props: ['progress'],
  emits: ['navigate'],
  components: { ActionModal },
  setup() {
    const data = ref(null)
    const loading = ref(true)
    const error = ref(null)
    const query = ref('')

    // Setup wizard state
    const showSetup = ref(false)
    const setupForm = ref({ instances_path: '', sync_path: '' })
    const setupSaving = ref(false)
    const setupError = ref(null)

    const icon = (name, size = 16) => window.__icon(name, size)
    const abbr = name => name.slice(0, 2).toUpperCase()

    const load = async () => {
      loading.value = true
      error.value = null
      try {
        await window.__apiReady
        data.value = await window.pywebview.api.get_instance_sync_data()
      } catch(e) {
        error.value = String(e)
      }
      loading.value = false
    }

    const openSetup = () => {
      setupForm.value = {
        instances_path: data.value?.instances_path || 'C:\\Users\\comsi\\AppData\\Roaming\\PrismLauncher\\instances',
        sync_path: data.value?.sync_path || '',
      }
      setupError.value = null
      showSetup.value = true
    }

    const saveSetup = async () => {
      if (!setupForm.value.instances_path || !setupForm.value.sync_path) {
        setupError.value = 'Both paths are required.'
        return
      }
      setupSaving.value = true
      setupError.value = null
      try {
        await window.__apiReady
        await window.pywebview.api.setup_instance_sync(
          setupForm.value.instances_path,
          setupForm.value.sync_path,
        )
        showSetup.value = false
        await load()
      } catch(e) {
        setupError.value = String(e)
      }
      setupSaving.value = false
    }

    // Module settings modal (replaces setup wizard entry points)
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

    // Date formatter and error expansion
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

    const expandedError = ref(null)

    onMounted(load)

    const filtered = computed(() => {
      if (!data.value?.instances) return []
      const q = query.value.toLowerCase()
      return data.value.instances.filter(i => i.name.toLowerCase().includes(q))
    })

    const toggleDefault = async (key) => {
      if (!data.value) return
      const next = !data.value.defaults[key]
      try {
        await window.pywebview.api.set_instance_default(key, next)
        data.value.defaults[key] = next
      } catch(e) {}
    }

    const toggleOverride = async (inst, key) => {
      const next = !inst[key]
      try {
        await window.pywebview.api.set_instance_override(inst.name, key, next)
        inst[key] = next
      } catch(e) {}
    }

    // ── Instance gear modal ──────────────────────────────────────────────────
    const _makeArchiveModal = () => ({
      show: false, instance: null, moveOnly: false,
      phase: 'summary', done: false, error: false,
      steps: [], logs: [],
    })
    const archiveModal = ref(_makeArchiveModal())
    const archiveConfirm = ref(null) // 'archive' | 'move_only' | null

    const openArchiveModal = (instName, moveOnly) => {
      archiveConfirm.value = null
      archiveModal.value = {
        show: true, instance: instName, moveOnly,
        phase: 'summary', done: false, error: false,
        steps: [], logs: [],
      }
    }

    const closeArchiveModal = () => { archiveModal.value = _makeArchiveModal() }

    const _archiveStepLabels = (moveOnly) => moveOnly
      ? ['Reading files…', 'Moving files…', 'Removing instance folder…']
      : ['Reading files…', 'Copying files…', 'Creating zip archive…', 'Removing instance folder…']

    const _stepFor = (steps, label) => steps.find(s => s.label === label)

    const confirmArchive = async () => {
      const { instance, moveOnly } = archiveModal.value
      const stepLabels = _archiveStepLabels(moveOnly)
      archiveModal.value.steps = stepLabels.map((label, i) => ({ label, state: i === 0 ? 'run' : 'wait', pct: i === 0 ? 0 : null, detail: '' }))
      archiveModal.value.phase = 'progress'

      const prevHandler = window.__onProgress
      window.__onProgress = async (event) => {
        window.pywebview.api.log_js_error('debug', '[archive] received event: ' + JSON.stringify(event))
        if (event.type === 'archive_progress') {
          const running = archiveModal.value.steps.find(s => s.state === 'run')
          if (running) running.pct = event.pct
          window.pywebview.api.log_js_error('debug', '[archive] progress pct=' + event.pct)
        } else if (event.type === 'archive_log') {
          if (event.line != null) archiveModal.value.logs = [...archiveModal.value.logs, event.line]
          window.pywebview.api.log_js_error('debug', '[archive] log line appended: ' + event.line)
        } else if (event.type === 'archive_step') {
          const steps = archiveModal.value.steps
          const runIdx = steps.findIndex(s => s.state === 'run')
          if (runIdx >= 0) { steps[runIdx].state = 'done'; steps[runIdx].pct = null }
          const next = steps.find(s => s.state === 'wait')
          if (next) { next.state = 'run'; next.pct = event.pct ?? 0 }
          window.pywebview.api.log_js_error('debug', '[archive] step transition -> "' + event.step + '"')
        } else if (event.type === 'archive_done') {
          window.__onProgress = prevHandler
          const steps = archiveModal.value.steps
          if (event.ok) {
            steps.forEach(s => { if (s.state !== 'done') s.state = 'done' })
            archiveModal.value.error = false
            if (event.logs) archiveModal.value.logs = [...archiveModal.value.logs, ...event.logs]
            archiveModal.value.done = true
            load()
          } else {
            const running = steps.find(s => s.state === 'run')
            if (running) running.state = 'err'
            archiveModal.value.logs = [event.error || 'Archive failed']
            archiveModal.value.done = true
            archiveModal.value.error = true
          }
          window.pywebview.api.log_js_error('debug', '[archive] done ok=' + event.ok + ', logs=' + (event.logs ? event.logs.length : 0))
        } else if (prevHandler) {
          prevHandler(event)
        }
      }

      // Start first step running
      if (archiveModal.value.steps.length) archiveModal.value.steps[0].state = 'run'

      try {
        await window.__apiReady
        const method = moveOnly ? 'archive_instance_move_only' : 'archive_instance'
        const r = await window.pywebview.api[method](instance)
        if (!r.ok && !r.started) {
          window.__onProgress = prevHandler
          archiveModal.value.logs = [r.error || 'Archive failed']
          archiveModal.value.done = true
          archiveModal.value.error = true
        }
      } catch(e) {
        window.__onProgress = prevHandler
        archiveModal.value.logs = [String(e)]
        archiveModal.value.done = true
        archiveModal.value.error = true
      }
    }

    const showRestoreModal = ref(false)
    const archivedList = ref([])
    const selectedArchive = ref('')
    const restoring = ref(false)
    const restoreResult = ref(null)   // {ok, instance_name, has_zip}

    const openRestoreModal = async () => {
      restoreResult.value = null
      selectedArchive.value = ''
      try {
        await window.__apiReady
        archivedList.value = await window.pywebview.api.get_archived_instances()
      } catch(e) { archivedList.value = [] }
      showRestoreModal.value = true
    }

    const doRestore = async () => {
      if (!selectedArchive.value) return
      restoring.value = true
      try {
        await window.__apiReady
        const result = await window.pywebview.api.restore_instance(selectedArchive.value)
        restoreResult.value = { ...result, instance_name: selectedArchive.value }
        if (result.ok) await load()
      } catch(e) { restoreResult.value = { ok: false, error: String(e) } }
      restoring.value = false
    }

    const deleteZip = async () => {
      if (!restoreResult.value) return
      try {
        await window.__apiReady
        await window.pywebview.api.delete_archive_zip(restoreResult.value.instance_name)
      } catch(e) {}
      restoreResult.value = { ...restoreResult.value, has_zip: false }
    }

    const closeRestoreModal = () => {
      showRestoreModal.value = false
      restoreResult.value = null
    }

    const pickFolderInto = async (target, field) => {
      try {
        await window.__apiReady
        const result = await window.pywebview.api.pick_folder()
        if (result) target[field] = result
      } catch(e) {}
    }

    return {
      data, loading, error, query, filtered, icon, abbr, load, toggleDefault, toggleOverride,
      showSetup, setupForm, setupSaving, setupError, openSetup, saveSetup,
      archiveModal, archiveConfirm, openArchiveModal, closeArchiveModal, confirmArchive,
      showRestoreModal, archivedList, selectedArchive, restoring, restoreResult,
      openRestoreModal, doRestore, deleteZip, closeRestoreModal,
      showModuleSettings, moduleSettingsForm, moduleSettingsSaving, moduleSettingsError,
      openModuleSettings, saveModuleSettings, resetModuleSync,
      fmtDate, expandedError, pickFolderInto,
    }
  },
  template: `
    <main class="page-wrap">
      <div class="page-header">
        <div style="display:flex;align-items:center;gap:10px">
          <div>
            <div class="kicker">Sync</div>
            <h1>Instance Sync</h1>
          </div>
          <button class="icon-btn" title="Instance Sync Settings" @click="openModuleSettings" style="margin-top:4px">
            <span v-html="icon('settings',15)"></span>
          </button>
        </div>
        <div class="flex items-center gap-10">
          <button class="btn btn-ghost btn-sm flex items-center gap-6" @click="openRestoreModal">
            <span v-html="icon('archive', 12)"></span> Archived
          </button>
          <button class="btn btn-ghost btn-sm flex items-center gap-6" @click="load">
            <span v-html="icon('refresh', 12)"></span> Refresh
          </button>
        </div>
      </div>

      <div v-if="loading" class="loading">Loading…</div>
      <div v-else-if="error" class="loading text-err">Error: {{ error }}</div>

      <template v-else-if="!data.is_configured">
        <div class="card">
          <div class="card-body" style="text-align:center;padding:56px 48px;display:flex;flex-direction:column;align-items:center;gap:16px">
            <div class="fw-500 text-0 fs-14">Instance sync is not configured.</div>
            <div class="text-3 fs-13">Set the Prism instances folder and a sync folder to enable launch/exit hooks.</div>
            <button class="btn btn-primary btn-sm" @click="openModuleSettings">Setup Instance Sync</button>
          </div>
        </div>
      </template>

      <template v-else>
        <!-- Global Defaults card -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="kicker">Global</div>
              <div class="card-title">Global Defaults</div>
            </div>
          </div>
          <div class="card-body" style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px">
            <!-- Exit sync toggle -->
            <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--bg-0);border:1px solid var(--line);border-radius:8px">
              <div>
                <div class="fw-500 text-0 fs-13">Exit Sync</div>
                <div class="fs-12 text-2 mt-4">Copy instance on exit</div>
              </div>
              <div :class="['toggle-track', data.defaults.exit_sync ? 'on' : 'off']" @click="toggleDefault('exit_sync')">
                <div class="toggle-thumb"></div>
              </div>
            </div>
            <!-- Startup sync toggle -->
            <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--bg-0);border:1px solid var(--line);border-radius:8px">
              <div>
                <div class="fw-500 text-0 fs-13">Startup Sync</div>
                <div class="fs-12 text-2 mt-4">Restore instance on launch</div>
              </div>
              <div :class="['toggle-track', data.defaults.startup_sync ? 'on' : 'off']" @click="toggleDefault('startup_sync')">
                <div class="toggle-thumb"></div>
              </div>
            </div>
            <!-- Sync path -->
            <div style="padding:12px 14px;background:var(--bg-0);border:1px solid var(--line);border-radius:8px">
              <div class="fw-500 text-0 fs-13">Sync Path</div>
              <div class="mono fs-12 text-2 mt-4 text-ellipsis" style="overflow:hidden;white-space:nowrap;text-overflow:ellipsis" :title="data.sync_path">
                {{ data.sync_path || '—' }}
              </div>
            </div>
          </div>
        </div>

        <!-- Instance table -->
        <div class="card">
          <div class="card-header" style="align-items:center">
            <div>
              <div class="kicker">Instances</div>
              <div class="card-title">Instance List <span class="text-3 fw-500">· {{ data.instances.length }}</span></div>
            </div>
            <div class="flex items-center gap-8">
              <div class="relative">
                <span style="position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--text-3);display:inline-flex" v-html="icon('search',13)"></span>
                <input v-model="query" placeholder="Filter instances…" class="input input-search" style="width:220px;padding:6px 10px 6px 28px">
              </div>
            </div>
          </div>

          <div style="overflow-x:auto">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="text-align:left">Instance</th>
                  <th style="text-align:center">Exit Sync</th>
                  <th style="text-align:center">Startup Sync</th>
                  <th style="text-align:left">Last Exit Sync</th>
                  <th style="text-align:left">Last Startup Sync</th>
                  <th style="text-align:right">Size</th>
                  <th style="text-align:right">Actions</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="inst in filtered" :key="inst.name">
                <tr>
                  <td>
                    <div class="flex items-center gap-10">
                      <div class="inst-avatar">{{ abbr(inst.name) }}</div>
                      <div>
                        <div class="text-0 fw-500">{{ inst.name }}</div>
                        <div class="mono fs-12 text-3 mt-4">Prism · —</div>
                      </div>
                    </div>
                  </td>
                  <td style="text-align:center">
                    <div style="display:flex;justify-content:center">
                      <div :class="['toggle-track', inst.exit_sync ? 'on' : 'off']" @click="toggleOverride(inst, 'exit_sync')">
                        <div class="toggle-thumb"></div>
                      </div>
                    </div>
                  </td>
                  <td style="text-align:center">
                    <div style="display:flex;justify-content:center">
                      <div :class="['toggle-track', inst.startup_sync ? 'on' : 'off']" @click="toggleOverride(inst, 'startup_sync')">
                        <div class="toggle-thumb"></div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span class="mono fs-12 text-2" :title="inst.last_exit_sync || ''">{{ fmtDate(inst.last_exit_sync) }}</span>
                    <span v-if="inst.last_errors?.length" style="margin-left:6px;cursor:pointer;color:var(--warn)"
                      :title="inst.last_errors.join(' | ')"
                      @click="expandedError = expandedError === inst.name ? null : inst.name">⚠</span>
                  </td>
                  <td>
                    <span class="mono fs-12 text-2" :title="inst.last_startup_sync || ''">{{ fmtDate(inst.last_startup_sync) }}</span>
                  </td>
                  <td style="text-align:right">
                    <span class="mono fs-12 text-2">{{ inst.synced_size_mb ? inst.synced_size_mb + ' MB' : '—' }}</span>
                  </td>
                  <td style="text-align:right">
                    <button class="icon-btn" title="Instance actions" @click.stop="openArchiveModal(inst.name, false)">
                      <span v-html="icon('settings', 14)"></span>
                    </button>
                  </td>
                </tr>
                <tr v-if="expandedError === inst.name && inst.last_errors?.length">
                  <td colspan="7" style="padding:8px 16px;background:var(--err-soft)">
                    <div v-for="e in inst.last_errors" :key="e" class="fs-12" style="color:var(--err)">{{ e }}</div>
                  </td>
                </tr>
                </template>
                <tr v-if="!filtered.length">
                  <td colspan="7" class="loading">No instances found</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <!-- Restore modal -->
      <teleport to="body">
        <div v-if="showRestoreModal"
          style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px">
          <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:480px;overflow:hidden">
            <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line)">
              <div class="fw-600 text-0 fs-13">Restore Archived Instance</div>
            </div>
            <div style="padding:20px 24px;display:flex;flex-direction:column;gap:14px">
              <template v-if="!restoreResult">
                <div v-if="!archivedList.length" class="fs-13 text-3">No archived instances found.</div>
                <template v-else>
                  <div>
                    <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Select instance to restore</div>
                    <select v-model="selectedArchive" class="input">
                      <option value="" disabled>Choose…</option>
                      <option v-for="name in archivedList" :key="name" :value="name">{{ name }}</option>
                    </select>
                  </div>
                </template>
              </template>
              <template v-else-if="restoreResult.ok">
                <div style="display:flex;align-items:center;gap:10px;color:var(--ok)">
                  <span v-html="icon('check', 16)"></span>
                  <span class="fw-500 fs-13">Restored successfully.</span>
                </div>
                <div v-if="restoreResult.has_zip" class="fs-13 text-1">
                  A backup zip still exists. Delete it?
                </div>
              </template>
              <template v-else>
                <div class="fs-13 text-err">{{ restoreResult.error }}</div>
              </template>
            </div>
            <div style="padding:16px 24px;border-top:1px solid var(--line);display:flex;justify-content:flex-end;gap:8px">
              <template v-if="!restoreResult">
                <button class="btn btn-ghost btn-sm" @click="closeRestoreModal">Cancel</button>
                <button class="btn btn-primary btn-sm" :disabled="restoring || !selectedArchive" @click="doRestore">
                  {{ restoring ? 'Restoring…' : 'Restore' }}
                </button>
              </template>
              <template v-else-if="restoreResult.ok">
                <button v-if="restoreResult.has_zip" class="btn btn-ghost btn-sm" style="color:var(--err);border-color:var(--err)" @click="deleteZip">Yes, delete zip</button>
                <button class="btn btn-primary btn-sm" @click="closeRestoreModal">{{ restoreResult.has_zip ? 'No, keep it' : 'Close' }}</button>
              </template>
              <template v-else>
                <button class="btn btn-ghost btn-sm" @click="closeRestoreModal">Close</button>
              </template>
            </div>
          </div>
        </div>
      </teleport>

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
                <div style="display:flex;gap:6px">
                  <input v-model="moduleSettingsForm.instances_path" class="input input-mono" style="flex:1;min-width:0" placeholder="C:\Users\…\PrismLauncher\instances">
                  <button class="icon-btn" title="Browse" style="flex:none;width:34px;height:34px" @click="pickFolderInto(moduleSettingsForm, 'instances_path')"><span v-html="icon('folder',16)"></span></button>
                </div>
                <div class="fs-12 text-3 mt-4">Folder containing all Prism instance subfolders.</div>
              </div>
              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Sync Folder Path</div>
                <div style="display:flex;gap:6px">
                  <input v-model="moduleSettingsForm.sync_path" class="input input-mono" style="flex:1;min-width:0" placeholder="C:\Users\…\Nextcloud\Minecraft">
                  <button class="icon-btn" title="Browse" style="flex:none;width:34px;height:34px" @click="pickFolderInto(moduleSettingsForm, 'sync_path')"><span v-html="icon('folder',16)"></span></button>
                </div>
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

      <!-- Setup wizard modal — outside v-if/v-else chain so it doesn't break Vue's sibling check -->
      <teleport to="body">
        <div v-if="showSetup"
          style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px">
          <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:520px;overflow:hidden">
            <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line)">
              <div class="fw-600 text-0 fs-13">Setup Instance Sync</div>
              <div class="fs-13 text-2 mt-4">Set the paths for Prism instances and the sync folder.</div>
            </div>
            <div style="padding:20px 24px;display:flex;flex-direction:column;gap:14px">
              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Prism Instances Path</div>
                <div style="display:flex;gap:6px">
                  <input v-model="setupForm.instances_path" class="input input-mono" style="flex:1;min-width:0" placeholder="C:\Users\…\PrismLauncher\instances">
                  <button class="icon-btn" title="Browse" style="flex:none;width:34px;height:34px" @click="pickFolderInto(setupForm, 'instances_path')"><span v-html="icon('folder',16)"></span></button>
                </div>
                <div class="fs-12 text-3 mt-4">Folder containing all Prism instance subfolders.</div>
              </div>
              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Sync Folder Path</div>
                <div style="display:flex;gap:6px">
                  <input v-model="setupForm.sync_path" class="input input-mono" style="flex:1;min-width:0" placeholder="C:\Users\…\Nextcloud\Minecraft">
                  <button class="icon-btn" title="Browse" style="flex:none;width:34px;height:34px" @click="pickFolderInto(setupForm, 'sync_path')"><span v-html="icon('folder',16)"></span></button>
                </div>
                <div class="fs-12 text-3 mt-4">Folder where instance files will be synced (e.g. Nextcloud).</div>
              </div>
              <div v-if="setupError" style="padding:8px 12px;border-radius:6px;background:var(--err-soft);color:var(--err);font-size:12px">{{ setupError }}</div>
            </div>
            <div style="padding:16px 24px;border-top:1px solid var(--line);display:flex;justify-content:flex-end;gap:8px">
              <button class="btn btn-ghost btn-sm" @click="showSetup = false">Cancel</button>
              <button class="btn btn-primary btn-sm" :disabled="setupSaving" @click="saveSetup">
                {{ setupSaving ? 'Saving…' : 'Save & Enable' }}
              </button>
            </div>
          </div>
        </div>
      </teleport>

      <!-- Instance gear modal -->
      <teleport to="body">
        <div v-if="archiveModal.show && archiveModal.phase === 'summary'"
          style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px"
          @mousedown.self="closeArchiveModal">
          <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:440px;overflow:hidden">
            <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between">
              <div>
                <div class="kicker">Instance</div>
                <div class="fw-600 text-0" style="font-size:15px">{{ archiveModal.instance }}</div>
              </div>
              <button class="icon-btn" @click="closeArchiveModal"><span v-html="icon('x',13)"></span></button>
            </div>
            <div style="padding:20px 24px;display:flex;flex-direction:column;gap:0">
              <div class="danger-zone">
                <div class="danger-zone-label">Danger Zone</div>

                <!-- Archive (with zip) -->
                <div style="margin-bottom:8px">
                  <template v-if="archiveConfirm === 'archive'">
                    <div class="fs-12 text-1" style="margin-bottom:6px">This will sync, zip, and remove the instance from Prism. Continue?</div>
                    <div class="flex items-center gap-6">
                      <button class="btn-danger" @click="archiveModal.moveOnly = false; confirmArchive()">Confirm Archive</button>
                      <button class="btn btn-ghost btn-sm" @click="archiveConfirm = null">Cancel</button>
                    </div>
                  </template>
                  <template v-else>
                    <button class="btn-danger" @click="archiveConfirm = 'archive'">
                      <span v-html="icon('archive',12)"></span> Archive
                    </button>
                    <div class="fs-11 text-3" style="margin-top:4px">Sync + create zip backup + remove from Prism</div>
                  </template>
                </div>

                <!-- Archive Move Only -->
                <div>
                  <template v-if="archiveConfirm === 'move_only'">
                    <div class="fs-12" style="color:var(--err);margin-bottom:6px">⚠ Warning: No zip backup — cannot recover if sync folder is lost.</div>
                    <div class="flex items-center gap-6">
                      <button class="btn-danger" @click="archiveModal.moveOnly = true; confirmArchive()">Yes, move only</button>
                      <button class="btn btn-ghost btn-sm" @click="archiveConfirm = null">Cancel</button>
                    </div>
                  </template>
                  <template v-else>
                    <button class="btn-danger" @click="archiveConfirm = 'move_only'">
                      <span v-html="icon('archive',12)"></span> Archive (Move only)
                    </button>
                    <div class="fs-11 text-3" style="margin-top:4px">Sync + remove from Prism — no zip backup</div>
                  </template>
                </div>

              </div>
            </div>
            <div style="padding:16px 24px;border-top:1px solid var(--line);display:flex;justify-content:flex-end">
              <button class="btn btn-ghost btn-sm" @click="closeArchiveModal">Cancel</button>
            </div>
          </div>
        </div>
      </teleport>

      <!-- Archive progress modal -->
      <action-modal
        :show="archiveModal.show && archiveModal.phase === 'progress'"
        :title="'Archiving ' + (archiveModal.instance || '')"
        phase="progress"
        :steps="archiveModal.steps"
        :logs="archiveModal.logs"
        :done="archiveModal.done"
        :error="archiveModal.error"
        @cancel="closeArchiveModal"
        @retry="confirmArchive"
      />
    </main>
  `
}
