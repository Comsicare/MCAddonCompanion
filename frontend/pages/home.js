import { ref, onMounted, onUnmounted, computed } from '../vue.esm-browser.js'
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
    let _mounted = true
    onUnmounted(() => { _mounted = false })

    const load = async () => {
      loading.value = true
      error.value = null
      try {
        await window.__apiReady
        const d = await window.pywebview.api.get_home_data()
        if (_mounted) data.value = d
      } catch(e) {
        if (_mounted) error.value = String(e)
        console.error('get_home_data failed:', e)
      }
      if (_mounted) loading.value = false
    }

    onMounted(load)

    const filtered = computed(() => {
      if (!data.value) return []
      const q = query.value.toLowerCase()
      return data.value.instances.filter(i => i.name.toLowerCase().includes(q))
    })

    const syncedCount = computed(() =>
      data.value?.instances.filter(i => i.schematic_sync || i.exit_sync).length ?? 0
    )

    const icon = (name, size = 16) => window.__icon(name, size)
    const abbr = name => name.slice(0, 2).toUpperCase()

    const openInstancesFolder = async () => {
      try {
        await window.__apiReady
        await window.pywebview.api.open_instances_folder()
      } catch(e) {}
    }

    // Expandable row detail
    const expandedRow = ref(null)
    const rowDetail = ref({})

    const toggleRow = (instName) => {
      if (expandedRow.value === instName) {
        expandedRow.value = null
        return
      }
      expandedRow.value = instName
      if (rowDetail.value[instName]) return
      rowDetail.value = { ...rowDetail.value, [instName]: { loading: true, data: null } }
      window.__apiReady.then(() =>
        window.pywebview.api.get_instance_detail(instName)
          .then(d => { if (_mounted) rowDetail.value = { ...rowDetail.value, [instName]: { loading: false, data: d } } })
          .catch(() => { if (_mounted) rowDetail.value = { ...rowDetail.value, [instName]: { loading: false, data: null } } })
      )
    }

    const refreshRowDetail = (instName) => {
      rowDetail.value = { ...rowDetail.value, [instName]: { loading: true, data: null } }
      window.__apiReady.then(() =>
        window.pywebview.api.get_instance_detail(instName)
          .then(d => { if (_mounted) rowDetail.value = { ...rowDetail.value, [instName]: { loading: false, data: d } } })
          .catch(() => { if (_mounted) rowDetail.value = { ...rowDetail.value, [instName]: { loading: false, data: null } } })
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

    // Archive modal (ActionModal-based)
    const archiveConfirm = ref(null)  // 'archive' | 'move_only' | null — controls inline confirm in danger zone
    const _makeArchiveModal = () => ({
      show: false, moveOnly: false, phase: 'summary', done: false, error: false, steps: [], logs: [],
    })
    const archiveModal = ref(_makeArchiveModal())

    const closeArchiveModal = () => { archiveModal.value = _makeArchiveModal() }

    const doArchive = async (instName, moveOnly) => {
      const stepLabels = moveOnly
        ? ['Sync files to sync folder', 'Remove instance folder']
        : ['Sync files to sync folder', 'Create zip backup', 'Remove instance folder']
      archiveModal.value = {
        show: true, moveOnly, phase: 'progress', done: false, error: false,
        steps: stepLabels.map((label, i) => ({ label, state: i === 0 ? 'run' : 'wait', pct: i === 0 ? 0 : null, detail: '' })),
        logs: [],
      }
      archiveConfirm.value = null

      const prevHandler = window.__onProgress
      window.__onProgress = async (event) => {
        if (event.type === 'archive_progress') {
          const running = archiveModal.value.steps.find(s => s.state === 'run')
          if (running) running.pct = event.pct
        } else if (event.type === 'archive_step') {
          const steps = archiveModal.value.steps
          const runIdx = steps.findIndex(s => s.state === 'run')
          if (runIdx >= 0) { steps[runIdx].state = 'done'; steps[runIdx].pct = null }
          const next = steps.find(s => s.state === 'wait')
          if (next) { next.state = 'run'; next.pct = event.pct ?? 0 }
        } else if (event.type === 'archive_done') {
          window.__onProgress = prevHandler
          const steps = archiveModal.value.steps
          if (event.ok) {
            steps.forEach(s => { if (s.state !== 'done') s.state = 'done' })
            if (event.logs) archiveModal.value.logs = event.logs
            archiveModal.value.done = true
            archiveModal.value.error = false
            load()  // refresh in background — don't await, user dismisses modal manually
          } else {
            const running = steps.find(s => s.state === 'run')
            if (running) running.state = 'err'
            archiveModal.value.logs = [event.error || 'Archive failed']
            archiveModal.value.done = true
            archiveModal.value.error = true
          }
        } else if (prevHandler) {
          prevHandler(event)
        }
      }
      try {
        await window.__apiReady
        const method = moveOnly ? 'archive_instance_move_only' : 'archive_instance'
        const r = await window.pywebview.api[method](instName)
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

    // Per-instance settings modal
    const settingsModal = ref({ show: false, loading: false, saving: false, instance: null, form: null })

    const openSettings = async (instName) => {
      settingsModal.value = { show: true, loading: true, saving: false, instance: instName, form: null }
      archiveConfirm.value = null
      try {
        await window.__apiReady
        const s = await window.pywebview.api.get_instance_settings(instName)
        settingsModal.value.form = {
          schematic_sync: s.schematic_sync,
          exit_sync: s.exit_sync,
          startup_sync: s.startup_sync,
          hook_enabled: s.hook_enabled,
          tracked: s.tracked,
          installed: s.installed,
          pack_name: s.pack_name,
        }
      } catch(e) {
        closeSettings()
        return
      }
      settingsModal.value.loading = false
    }

    const closeSettings = () => {
      settingsModal.value = { show: false, loading: false, saving: false, instance: null, form: null }
      archiveConfirm.value = null
    }

    const saveSettings = async () => {
      if (!settingsModal.value.form) return
      settingsModal.value.saving = true
      try {
        await window.__apiReady
        await window.pywebview.api.save_instance_settings(
          settingsModal.value.instance,
          settingsModal.value.form
        )
        settingsModal.value.saving = false
        closeSettings()
        await load()
      } catch(e) {
        settingsModal.value.saving = false
      }
    }

    return {
      data, loading, error, query, filtered, syncedCount, load, icon, abbr,
      openInstancesFolder,
      expandedRow, rowDetail, toggleRow, refreshRowDetail, fmtDate,
      archiveConfirm, archiveModal, closeArchiveModal, doArchive,
      settingsModal, openSettings, closeSettings, saveSettings,
    }
  },
  template: `
    <main class="page-wrap">
      <!-- Page header -->
      <div class="page-header">
        <div>
          <div class="kicker">Dashboard</div>
          <h1>Home</h1>
        </div>
        <div class="flex items-center gap-10">
          <button class="btn btn-ghost btn-sm flex items-center gap-6" @click="load">
            <span v-html="icon('refresh', 12)"></span> Refresh all
          </button>
        </div>
      </div>

      <div v-if="loading" class="loading">Loading…</div>
      <div v-else-if="error" class="loading text-err">Error: {{ error }}</div>

      <template v-else>
        <!-- 3 summary cards -->
        <section style="display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:16px">
          <!-- Launcher card -->
          <div class="card">
            <div class="card-header">
              <div>
                <div class="kicker">Launcher</div>
                <div class="card-title">Prism Launcher</div>
              </div>
              <div class="flex items-center gap-6">
                <span class="pill pill-ok"><span v-html="icon('check',11)"></span> Healthy</span>
                <button class="icon-btn" @click="load"><span v-html="icon('refresh',14)"></span></button>
              </div>
            </div>
            <div class="card-body">
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px">
                <div>
                  <div class="stat-label">Instances</div>
                  <div class="flex items-center gap-8 mt-4">
                    <div class="stat-value">{{ data.instances.length }}</div>
                  </div>
                </div>
                <div>
                  <div class="stat-label">Synced</div>
                  <div class="flex items-center gap-8 mt-4">
                    <div class="stat-value">{{ syncedCount }}</div>
                    <div class="stat-sub">{{ data.instances.length ? Math.round(syncedCount/data.instances.length*100) + '%' : '' }}</div>
                  </div>
                </div>
              </div>
              <div class="flex items-center justify-between mt-14" style="padding-top:12px; border-top:1px solid var(--line)">
                <span class="mono fs-12 text-3">PrismLauncher/instances</span>
                <button class="ghost-link fs-12" @click="openInstancesFolder">Open <span v-html="icon('external',11)"></span></button>
              </div>
            </div>
          </div>

          <!-- Schematic Sync card -->
          <div class="card">
            <div class="card-header">
              <div>
                <div class="kicker">Sync</div>
                <div class="card-title">Schematic Sync</div>
              </div>
              <div class="flex items-center gap-6">
                <span class="pill pill-ok"><span v-html="icon('check',11)"></span> All good</span>
                <button class="icon-btn" @click="load"><span v-html="icon('refresh',14)"></span></button>
              </div>
            </div>
            <div class="card-body">
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px">
                <div>
                  <div class="stat-label">Active instances</div>
                  <div class="flex items-center gap-8 mt-4">
                    <div class="stat-value">{{ data.instances.filter(i=>i.schematic_sync).length }}</div>
                    <div class="stat-sub">of {{ data.instances.length }}</div>
                  </div>
                </div>
              </div>
              <div class="flex items-center justify-between mt-14" style="padding-top:12px; border-top:1px solid var(--line)">
                <div class="flex items-center gap-8 fs-12 text-2">
                  <span>Last sync</span>
                  <span class="mono text-1">—</span>
                </div>
<button class="btn btn-primary btn-sm flex items-center gap-6" @click="$emit('navigate','schematic_sync')">
                  <span v-html="icon('refresh',12)"></span> Sync now
                </button>
              </div>
            </div>
          </div>

          <!-- Pack Repos card -->
          <div class="card">
            <div class="card-header">
              <div>
                <div class="kicker">Registry</div>
                <div class="card-title">Pack Repos</div>
              </div>
              <button class="icon-btn" @click="load"><span v-html="icon('refresh',14)"></span></button>
            </div>
            <div class="card-body" style="padding: 8px 8px 12px">
              <div v-if="!data.repos || !data.repos.length" class="text-3 fs-12" style="padding:8px 10px">No repos configured</div>
              <div v-for="r in (data.repos || [])" :key="r.id"
                style="display:flex; align-items:center; justify-content:space-between; padding:8px 10px; border-radius:6px">
                <div class="flex items-center gap-10 min-w-0">
                  <span class="dot dot-ok"></span>
                  <span class="mono fs-12 text-0 text-ellipsis">{{ r.name }}</span>
                </div>
                <span class="fs-12 text-3">{{ r.package_name }}</span>
              </div>
              <div style="padding:4px 10px 0; display:flex; justify-content:space-between; align-items:center">
                <button class="ghost-link" @click="$emit('navigate','pack_registry')"><span v-html="icon('plus',11)"></span> Add repo</button>
              </div>
            </div>
          </div>
        </section>

        <!-- Instance Overview table -->
        <div class="card">
          <div class="card-header" style="align-items:center">
            <div>
              <div class="kicker">Instances</div>
              <div class="card-title">Instance Overview <span class="text-3 fw-500">· {{ data.instances.length }}</span></div>
            </div>
            <div class="flex items-center gap-8">
              <div class="relative">
                <span style="position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--text-3);display:inline-flex" v-html="icon('search',13)"></span>
                <input v-model="query" placeholder="Filter instances…" class="input input-search" style="width:220px; font-size:12.5px; padding:6px 10px 6px 28px">
              </div>
            </div>
          </div>
          <div style="overflow-x:auto">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="text-align:left">Instance</th>
                  <th style="text-align:center">Schematic</th>
                  <th style="text-align:center">Exit</th>
                  <th style="text-align:center">Startup</th>
                  <th style="text-align:left">Last sync</th>
                  <th style="text-align:right">Actions</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="inst in filtered" :key="inst.name">
                <tr @click="toggleRow(inst.name)" style="cursor:pointer">
                  <td>
                    <div class="flex items-center gap-10">
                      <div class="inst-avatar">{{ abbr(inst.name) }}</div>
                      <div>
                        <div class="text-0 fw-500">{{ inst.name }}</div>
                        <div class="mono fs-12 text-3 mt-4">Prism</div>
                      </div>
                    </div>
                  </td>
                  <td style="text-align:center">
                    <span v-if="inst.schematic_sync" style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:20px;background:var(--ok-soft);color:var(--ok)" v-html="icon('check',12)"></span>
                    <span v-else style="display:inline-flex;width:8px;height:8px;border-radius:8px;border:1.5px solid var(--text-3);opacity:.7"></span>
                  </td>
                  <td style="text-align:center">
                    <span v-if="inst.exit_sync" style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:20px;background:var(--ok-soft);color:var(--ok)" v-html="icon('check',12)"></span>
                    <span v-else style="display:inline-flex;width:8px;height:8px;border-radius:8px;border:1.5px solid var(--text-3);opacity:.7"></span>
                  </td>
                  <td style="text-align:center">
                    <span v-if="inst.startup_sync" style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:20px;background:var(--ok-soft);color:var(--ok)" v-html="icon('check',12)"></span>
                    <span v-else style="display:inline-flex;width:8px;height:8px;border-radius:8px;border:1.5px solid var(--text-3);opacity:.7"></span>
                  </td>
                  <td><span class="mono fs-12 text-2">—</span></td>
                  <td style="text-align:right">
                    <div class="flex items-center gap-4" style="justify-content:flex-end">
                      <button class="icon-btn" title="Settings" @click.stop="openSettings(inst.name)"><span v-html="icon('settings',14)"></span></button>
                    </div>
                  </td>
                </tr>
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
                          <span class="row-detail-value mono fs-12" :title="rowDetail[inst.name].data.last_exit_sync || ''">{{ fmtDate(rowDetail[inst.name].data.last_exit_sync) }}</span>
                        </div>
                        <div class="row-detail-field">
                          <span class="row-detail-label">Last Startup Sync</span>
                          <span class="row-detail-value mono fs-12" :title="rowDetail[inst.name].data.last_startup_sync || ''">{{ fmtDate(rowDetail[inst.name].data.last_startup_sync) }}</span>
                        </div>
                        <div class="row-detail-field">
                          <span class="row-detail-label">Synced</span>
                          <span class="row-detail-value fs-12">{{ rowDetail[inst.name].data.synced_file_count }} files · {{ rowDetail[inst.name].data.synced_size_mb }} MB</span>
                        </div>
                        <div class="row-detail-field">
                          <span class="row-detail-label">Instance Size</span>
                          <span class="row-detail-value fs-12">{{ rowDetail[inst.name].data.instance_folder_size_mb != null ? rowDetail[inst.name].data.instance_folder_size_mb + ' MB' : '—' }}</span>
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
                        <div v-if="(rowDetail[inst.name].data.last_exit_errors||[]).length || (rowDetail[inst.name].data.last_startup_errors||[]).length"
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
                </template>
                <tr v-if="!filtered.length">
                  <td colspan="6" class="loading">No instances found</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

    <!-- Per-instance settings modal -->
    <teleport to="body">
      <div v-if="settingsModal.show"
        style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px"
        @mousedown.self="closeSettings">
        <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:440px;overflow:hidden">

          <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between">
            <div>
              <div class="kicker">Instance</div>
              <div class="fw-600 text-0" style="font-size:15px">{{ settingsModal.instance }}</div>
            </div>
            <button class="icon-btn" @click="closeSettings"><span v-html="icon('x',13)"></span></button>
          </div>

          <div v-if="settingsModal.loading" style="padding:32px;text-align:center" class="text-3 fs-13">Loading…</div>

          <template v-else-if="settingsModal.form">
            <div style="padding:20px 24px;display:flex;flex-direction:column;gap:0;overflow-y:auto;max-height:60vh">

              <!-- Schematic Sync -->
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
                    Instance Sync not set up — <a @click="closeSettings(); $emit('navigate','instance_sync')">Configure →</a>
                  </div>
                </div>
                <div class="toggle-track"
                  :class="[settingsModal.form.hook_enabled ? 'on' : 'off', !data.instance_sync_configured ? 'disabled-hint' : '']"
                  @click="data.instance_sync_configured && (settingsModal.form.hook_enabled = !settingsModal.form.hook_enabled)"
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
                      Instance Sync not set up — <a @click="closeSettings(); $emit('navigate','instance_sync')">Configure →</a>
                    </div>
                  </div>
                  <div class="toggle-track"
                    :class="[(settingsModal.form.exit_sync || settingsModal.form.startup_sync) ? 'on' : 'off', !data.instance_sync_configured ? 'disabled-hint' : '']"
                    style="flex:none;opacity:.5;cursor:not-allowed">
                    <div class="toggle-thumb"></div>
                  </div>
                </div>
                <!-- TODO: wire exit_sync and startup_sync save logic when instance sync feature is reworked -->
                <div style="margin-top:8px;padding-left:16px;display:flex;flex-direction:column;gap:6px;border-left:2px solid var(--line)">
                  <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0">
                    <div>
                      <div class="fs-12 fw-500 text-1">Exit Sync</div>
                      <div class="fs-11 text-3">Sync files when Prism closes</div>
                    </div>
                    <div class="toggle-track"
                      :class="[settingsModal.form.exit_sync ? 'on' : 'off', !data.instance_sync_configured ? 'disabled-hint' : '']"
                      @click="data.instance_sync_configured && (settingsModal.form.exit_sync = !settingsModal.form.exit_sync)"
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
                      @click="data.instance_sync_configured && (settingsModal.form.startup_sync = !settingsModal.form.startup_sync)"
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

              <!-- Pack update shortcut -->
              <div v-if="settingsModal.form.installed && rowDetail[settingsModal.instance]?.data?.pack?.has_update"
                style="padding:10px 0;border-bottom:1px solid var(--line)">
                <div class="fs-12 text-2">Update available — v{{ rowDetail[settingsModal.instance].data.pack.latest_version }}</div>
                <button class="ghost-link" style="margin-top:4px" @click="closeSettings(); $emit('navigate','pack_registry')">
                  <span v-html="icon('download',11)"></span> Go to Pack Registry to update
                </button>
              </div>

              <!-- Danger Zone -->
              <div class="danger-zone">
                <div class="danger-zone-label">Danger Zone</div>

                <!-- Archive (with zip) -->
                <div style="margin-bottom:8px">
                  <template v-if="archiveConfirm === 'archive'">
                    <div class="fs-12 text-1" style="margin-bottom:6px">This will sync, zip, and remove the instance from Prism. Continue?</div>
                    <div class="flex items-center gap-6">
                      <button class="btn-danger" @click="doArchive(settingsModal.instance, false)">Confirm Archive</button>
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
                      <button class="btn-danger" @click="doArchive(settingsModal.instance, true)">Yes, move only</button>
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

            <div style="padding:16px 24px;border-top:1px solid var(--line);display:flex;justify-content:flex-end;gap:8px">
              <button class="btn btn-ghost btn-sm" @click="closeSettings">Cancel</button>
              <button class="btn btn-primary btn-sm" :disabled="settingsModal.saving" @click="saveSettings">
                {{ settingsModal.saving ? 'Saving…' : 'Save' }}
              </button>
            </div>
          </template>

        </div>
      </div>
    </teleport>

    <!-- Archive progress modal -->
    <action-modal
      :show="archiveModal.show"
      :title="'Archiving ' + (settingsModal.instance || '')"
      phase="progress"
      :steps="archiveModal.steps"
      :logs="archiveModal.logs"
      :done="archiveModal.done"
      :error="archiveModal.error"
      @cancel="closeArchiveModal(); closeSettings()"
      @retry="doArchive(settingsModal.instance, archiveModal.moveOnly)"
    />
    </main>
  `
}
