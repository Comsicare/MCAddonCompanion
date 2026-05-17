import { ref, onMounted, computed, watch } from '../vue.esm-browser.js'

const SYNC_STEPS = ['Scan files', 'Sync to archive', 'Verify']

export default {
  props: ['progress'],
  emits: ['navigate'],
  setup(props) {
    const data = ref(null)
    const loading = ref(true)
    const error = ref(null)
    const selected = ref(null)
    const counts = ref({})
    const syncing = ref(false)

    const icon = (name, size = 16) => window.__icon(name, size)
    const abbr = name => name.slice(0, 2).toUpperCase()

    const load = async () => {
      loading.value = true
      error.value = null
      try {
        await window.__apiReady
        data.value = await window.pywebview.api.get_schematic_data()
        if (data.value.instances.length && !selected.value) {
          selected.value = data.value.instances[0]
          await loadCounts(selected.value)
        }
      } catch(e) {
        error.value = String(e)
      }
      loading.value = false
    }

    const loadCounts = async (name) => {
      counts.value = {}
      try {
        counts.value = await window.pywebview.api.get_schematic_counts(name)
      } catch(e) {}
    }

    onMounted(load)

    const selectInstance = async (name) => {
      selected.value = name
      await loadCounts(name)
    }

    const isAutoSync = computed(() =>
      data.value?.autosync_instances?.includes(selected.value) ?? false
    )

    const toggleAutoSync = async () => {
      if (!selected.value) return
      const next = !isAutoSync.value
      try {
        await window.pywebview.api.set_autosync(selected.value, next)
        await load()
      } catch(e) {}
    }

    const runSync = async () => {
      if (!selected.value || syncing.value) return
      syncing.value = true
      try {
        await window.pywebview.api.run_schematic_sync(selected.value)
      } catch(e) {}
      syncing.value = false
    }

    const syncAll = async () => {
      if (syncing.value) return
      syncing.value = true
      try {
        await window.pywebview.api.sync_all('exit')
      } catch(e) {}
      syncing.value = false
    }

    const steps = computed(() => {
      const p = props.progress || {}
      return SYNC_STEPS.map((label, i) => {
        if (p.step === i) return { label, state: p.state || 'run', detail: p.detail || '' }
        return { label, state: 'idle', detail: '' }
      })
    })

    const summary = computed(() => props.progress?.text || '')
    const summaryTone = computed(() => props.progress?.tone || 'ok')

    const stepIconState = (state) => {
      if (state === 'ok') return 'done'
      if (state === 'running') return 'run'
      if (state === 'error') return 'err'
      return 'idle'
    }

    const totalFiles = computed(() => Object.values(counts.value).reduce((a, b) => a + b, 0))

    return {
      data, loading, error, selected, counts, syncing,
      isAutoSync, steps, summary, summaryTone, totalFiles,
      icon, abbr, selectInstance, toggleAutoSync, runSync, syncAll, load,
      stepIconState
    }
  },
  template: `
    <main class="page-wrap">
      <div class="page-header">
        <div>
          <div class="kicker">Sync</div>
          <h1>Schematic Sync</h1>
        </div>
        <div class="flex items-center gap-10">
          <button class="btn btn-ghost btn-sm flex items-center gap-6" @click="load">
            <span v-html="icon('refresh', 12)"></span> Refresh
          </button>
          <button class="btn btn-primary btn-sm flex items-center gap-6" :disabled="syncing" @click="syncAll">
            <span v-html="icon('refresh', 12)"></span> Sync all
          </button>
        </div>
      </div>

      <div v-if="loading" class="loading">Loading…</div>
      <div v-else-if="error" class="loading text-err">Error: {{ error }}</div>

      <template v-else>
        <div style="display:grid; grid-template-columns:360px 1fr; gap:16px; align-items:start">

          <!-- Left: instance list -->
          <div class="card" style="overflow:hidden">
            <div class="card-header" style="align-items:center">
              <div class="card-title" style="margin-top:0">Instances</div>
              <span class="text-3 fs-12">{{ data.instances.length }}</span>
            </div>
            <div style="max-height:520px; overflow-y:auto">
              <div v-if="!data.instances.length" class="loading">No instances</div>
              <div v-for="name in data.instances" :key="name"
                @click="selectInstance(name)"
                style="display:flex;align-items:center;gap:12px;padding:11px 14px;cursor:pointer;border-bottom:1px solid var(--line);transition:background .1s"
                :style="selected === name ? 'background:var(--bg-2)' : ''"
                class="inst-row">
                <div class="inst-avatar">{{ abbr(name) }}</div>
                <div style="flex:1;min-width:0">
                  <div class="text-0 fw-500 text-ellipsis">{{ name }}</div>
                  <div class="mono fs-12 text-3 mt-4">Last sync · —</div>
                </div>
                <span v-if="data.autosync_instances.includes(name)" class="pill pill-ok" style="font-size:10px;padding:2px 6px">Auto</span>
                <span v-else class="pill pill-off" style="font-size:10px;padding:2px 6px">Manual</span>
              </div>
            </div>
          </div>

          <!-- Right: detail panel -->
          <div v-if="selected" style="display:flex;flex-direction:column;gap:16px">
            <!-- Instance header -->
            <div class="card">
              <div class="card-header" style="align-items:center">
                <div class="flex items-center gap-12">
                  <div class="inst-avatar" style="width:36px;height:36px;font-size:12px">{{ abbr(selected) }}</div>
                  <div>
                    <div class="kicker">Instance</div>
                    <div class="card-title" style="margin-top:0">{{ selected }}</div>
                  </div>
                </div>
                <div class="flex items-center gap-10">
                  <!-- Auto-sync toggle -->
                  <div class="flex items-center gap-8">
                    <span class="fs-12 text-2">Auto-sync</span>
                    <div :class="['toggle-track', isAutoSync ? 'on' : 'off']" @click="toggleAutoSync">
                      <div class="toggle-thumb"></div>
                    </div>
                  </div>
                  <button class="btn btn-primary btn-sm flex items-center gap-6" :disabled="syncing" @click="runSync">
                    <span :class="syncing ? 'spin' : ''" v-html="icon('refresh', 12)"></span>
                    {{ syncing ? 'Syncing…' : 'Sync now' }}
                  </button>
                </div>
              </div>

              <!-- Stat boxes -->
              <div class="card-body" style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
                <div style="background:var(--bg-0);border:1px solid var(--line);border-radius:8px;padding:12px 14px">
                  <div class="stat-label">.nbt files</div>
                  <div class="stat-value mt-4">{{ counts['.nbt'] ?? 0 }}</div>
                </div>
                <div style="background:var(--bg-0);border:1px solid var(--line);border-radius:8px;padding:12px 14px">
                  <div class="stat-label">.litematic files</div>
                  <div class="stat-value mt-4">{{ counts['.litematic'] ?? 0 }}</div>
                </div>
                <div style="background:var(--bg-0);border:1px solid var(--line);border-radius:8px;padding:12px 14px">
                  <div class="stat-label">.schematic files</div>
                  <div class="stat-value mt-4">{{ counts['.schematic'] ?? 0 }}</div>
                </div>
              </div>
            </div>

            <!-- Progress + Last Sync -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
              <!-- Progress steps -->
              <div class="card">
                <div class="card-header">
                  <div class="card-title" style="margin-top:0">Progress</div>
                </div>
                <div class="card-body" style="padding:8px">
                  <div v-for="(step, i) in steps" :key="i" class="progress-step">
                    <div :class="['progress-step-icon', stepIconState(step.state)]">
                      <span v-if="step.state === 'ok'" v-html="icon('check', 10)"></span>
                      <span v-else-if="step.state === 'running'" class="spin" v-html="icon('spin', 10)"></span>
                      <span v-else-if="step.state === 'error'" v-html="icon('x', 10)"></span>
                    </div>
                    <div style="flex:1;min-width:0">
                      <div class="fs-13 text-0">{{ step.label }}</div>
                      <div v-if="step.detail" class="mono fs-12 text-2 mt-4">{{ step.detail }}</div>
                    </div>
                  </div>
                  <div v-if="summary" style="margin-top:8px;padding:8px 10px;border-radius:6px"
                    :style="summaryTone==='ok' ? 'background:var(--ok-soft);color:var(--ok)' : 'background:var(--err-soft);color:var(--err)'">
                    <span class="fs-12 fw-500">{{ summary }}</span>
                  </div>
                </div>
              </div>

              <!-- Last sync info -->
              <div class="card">
                <div class="card-header">
                  <div class="card-title" style="margin-top:0">Last Sync</div>
                </div>
                <div class="card-body">
                  <div class="flex items-center gap-8">
                    <span class="dot dot-off"></span>
                    <span class="fs-13 text-2">No sync recorded</span>
                  </div>
                  <div class="mt-14 flex items-center gap-8 fs-12 text-3">
                    <span>Total files</span>
                    <span class="mono text-1">{{ totalFiles }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="loading" style="padding:60px">Select an instance</div>
        </div>
      </template>
    </main>
  `
}
