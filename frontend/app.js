import { createApp, ref } from './vue.esm-browser.js'
import HomePage from './pages/home.js'
import SchematicSyncPage from './pages/schematic_sync.js'
import InstanceSyncPage from './pages/instance_sync.js'
import PackRegistryPage from './pages/pack_registry.js'
import UpdatePromptPage from './pages/update_prompt.js'

// SVG icon helper — renders inline SVG with given path content
export function icon(name, size = 16) {
  const paths = {
    cube: `<path d="M12 2.5 3.5 7v10L12 21.5 20.5 17V7L12 2.5Z" stroke-width="1.6" stroke-linejoin="round"/><path d="M3.5 7 12 11.5 20.5 7" stroke-width="1.6"/><path d="M12 11.5V21.5" stroke-width="1.6"/>`,
    home: `<path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v10h14V10"/><path d="M10 20v-5h4v5"/>`,
    layers: `<path d="M12 3 3 7.5l9 4.5 9-4.5L12 3Z"/><path d="m3 12 9 4.5L21 12"/><path d="m3 16.5 9 4.5 9-4.5"/>`,
    link: `<path d="M10.5 13.5a4 4 0 0 0 5.66 0l2.5-2.5a4 4 0 1 0-5.66-5.66L11.5 6.85"/><path d="M13.5 10.5a4 4 0 0 0-5.66 0l-2.5 2.5a4 4 0 1 0 5.66 5.66l1.5-1.5"/>`,
    repo: `<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v14H6.5A2.5 2.5 0 0 0 4 19.5v-14Z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20"/><path d="M9 3v10l2.5-1.8L14 13V3"/>`,
    refresh: `<path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v4.5H15.5"/>`,
    check: `<path d="m5 12.5 4.5 4.5L20 6.5"/>`,
    x: `<path d="M6 6l12 12"/><path d="M18 6 6 18"/>`,
    alert: `<path d="M12 4 2.5 20h19L12 4Z"/><path d="M12 10v5"/><circle cx="12" cy="17.5" r=".9" fill="currentColor"/>`,
    plus: `<path d="M12 5v14"/><path d="M5 12h14"/>`,
    search: `<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>`,
    settings: `<circle cx="12" cy="12" r="3"/><path d="M19.4 14.4a1.7 1.7 0 0 0 .3 1.9l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.55 1.7 1.7 0 0 0-1.9.3l-.06.06A2 2 0 1 1 4.08 16.9l.06-.06a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.55-1.1 1.7 1.7 0 0 0-.3-1.9l-.06-.06A2 2 0 1 1 7.12 4.08l.06.06a1.7 1.7 0 0 0 1.9.3H9.1a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.9-.3l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.3 1.9v.06a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.55 1Z"/>`,
    bell: `<path d="M6 9a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z"/><path d="M10 19a2 2 0 0 0 4 0"/>`,
    download: `<path d="M12 4v11"/><path d="m7 11 5 5 5-5"/><path d="M5 20h14"/>`,
    external: `<path d="M14 4h6v6"/><path d="m20 4-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>`,
    caret: `<path d="m6 9 6 6 6-6"/>`,
    filter: `<path d="M3 5h18"/><path d="M6 12h12"/><path d="M10 19h4"/>`,
    dots: `<circle cx="12" cy="5" r=".9" fill="currentColor"/><circle cx="12" cy="12" r=".9" fill="currentColor"/><circle cx="12" cy="19" r=".9" fill="currentColor"/>`,
    spin: `<path d="M21 12a9 9 0 1 1-9-9"/><path d="M21 4v5h-5" opacity=".5"/>`,
    play: `<path d="M7 4.5v15l13-7.5L7 4.5Z"/>`,
    archive: `<path d="M3 5h18v4H3z"/><path d="M5 9v10h14V9"/><path d="M10 14h4"/>`,
  }
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || ''}</svg>`
}

// Make icon available globally for page components
window.__icon = icon

// Shared promise that resolves when pywebview API is ready
// Pages should await window.__apiReady before calling window.pywebview.api
let __apiReadyResolve
window.__apiReady = new Promise(resolve => { __apiReadyResolve = resolve })
window.addEventListener('pywebviewready', () => {
  __apiReadyResolve()
  // Wrap API with a logging proxy — traces every call to js_errors.log
  const _raw = window.pywebview.api
  window.pywebview.api = new Proxy(_raw, {
    get(target, method) {
      const fn = target[method]
      if (typeof fn !== 'function') return fn
      // Don't proxy the raw log bypass itself (infinite loop guard)
      if (method === '_raw_log' || method === 'log_js_error') return fn.bind(target)
      return (...args) => {
        const argStr = JSON.stringify(args).slice(0, 300)
        _raw._raw_log('debug', `api.call method=${method} args=${argStr}`).catch(() => {})
        return Promise.resolve(fn.apply(target, args)).then(result => {
          _raw._raw_log('debug', `api.result method=${method}`).catch(() => {})
          return result
        }).catch(err => {
          _raw._raw_log('error', `api.error method=${method} error=${err}`).catch(() => {})
          throw err
        })
      }
    }
  })
})

// Global unhandled error capture — forwards to js_errors.log via Python
window.onerror = (msg, src, line, col, err) => {
  const text = `${msg} (${src}:${line}:${col})${err ? ' ' + err.stack : ''}`
  window.__apiReady.then(() => window.pywebview.api.log_js_error('error', '[onerror] ' + text).catch(() => {}))
}
window.addEventListener('unhandledrejection', e => {
  const text = String(e.reason?.stack || e.reason || e)
  window.__apiReady.then(() => window.pywebview.api.log_js_error('error', '[unhandledrejection] ' + text).catch(() => {}))
})

const PAGES = {
  home: HomePage,
  schematic_sync: SchematicSyncPage,
  instance_sync: InstanceSyncPage,
  pack_registry: PackRegistryPage,
}
const NAV = [
  { key: 'home',           label: 'Home',           icon: 'home' },
  { key: 'schematic_sync', label: 'Schematic Sync', icon: 'layers' },
  { key: 'instance_sync',  label: 'Instance Sync',  icon: 'link' },
  { key: 'pack_registry',  label: 'Pack Registry',  icon: 'repo' },
]

const App = {
  setup() {
    const urlParams = new URLSearchParams(window.location.search)
    const isUpdatePrompt = urlParams.get('mode') === 'update_prompt'

    const page = ref('home')
    const progress = ref({})
    const version = ref('')
    const updateInfo = ref(null)
    const updateDismissed = ref(false)
    const appUpdateState = ref(null)  // null | {state:'downloading'|'installing'|'done'|'error', pct:0-100}

    window.__onProgress = (event) => {
      if (event.type === 'app_update') {
        appUpdateState.value = { state: event.state, pct: event.pct }
        return
      }
      if (event.type === 'reset') { progress.value = {}; return }
      progress.value = { ...progress.value, ...event }
    }

    window.addEventListener('pywebviewready', async () => {
      try {
        version.value = await window.pywebview.api.get_version()
        const info = await window.pywebview.api.check_update()
        if (info) updateInfo.value = info
      } catch(e) { console.warn('API not ready:', e) }
    })

    const startUpdate = async () => {
      if (!updateInfo.value) return
      appUpdateState.value = { state: 'downloading', pct: 0 }
      await window.pywebview.api.start_app_update(
        updateInfo.value.download_url,
        updateInfo.value._pat || null,
      )
    }

    // Menu
    const showMenu = ref(false)

    // Version & Updates modal
    const showVersionModal = ref(false)
    const manualUpdateResult = ref(null)

    const openVersionModal = async () => {
      showMenu.value = false
      manualUpdateResult.value = null
      showVersionModal.value = true
      try {
        await window.__apiReady
        updateStream.value = await window.pywebview.api.get_update_stream_api()
      } catch(e) {}
    }

    const checkUpdateManual = async () => {
      manualUpdateResult.value = { checking: true }
      try {
        await window.__apiReady
        const info = await window.pywebview.api.check_update()
        manualUpdateResult.value = info ? { update: info } : { upToDate: true }
        if (info) updateInfo.value = info
      } catch(e) {
        manualUpdateResult.value = { error: String(e) }
      }
    }

    // Help & Debug modal
    const showDebugModal = ref(false)
    const hostInfo = ref(null)
    const resetConfirm = ref(null)
    const resetResult = ref({})

    const confirmReset = async (module) => {
      try {
        await window.__apiReady
        const r = await window.pywebview.api.reset_module(module)
        resetResult.value = { ...resetResult.value, [module]: r.ok ? 'ok' : 'error' }
      } catch(e) {
        resetResult.value = { ...resetResult.value, [module]: 'error' }
      }
      resetConfirm.value = null
    }

    const updateStream = ref('alpha')
    const streamSaving = ref(false)

    const setStream = async (stream) => {
      streamSaving.value = true
      try {
        await window.__apiReady
        await window.pywebview.api.set_update_stream_api(stream)
        updateStream.value = stream
        manualUpdateResult.value = null
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

    const dumpState = ref(null) // null | {running:true} | {ok,filename?,error?}
    const createDump = async () => {
      dumpState.value = { running: true }
      try {
        await window.__apiReady
        const r = await window.pywebview.api.create_debug_dump()
        dumpState.value = r
      } catch(e) {
        dumpState.value = { ok: false, error: String(e) }
      }
    }

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

    return { page, progress, version, updateInfo, updateDismissed, appUpdateState, startUpdate, NAV, PAGES, icon, isUpdatePrompt, UpdatePromptPage, showMenu, showVersionModal, manualUpdateResult, openVersionModal, checkUpdateManual, showDebugModal, hostInfo, resetConfirm, resetResult, confirmReset, openDebugModal, updateStream, streamSaving, setStream, gitlabPat, savePat, dumpState, createDump }
  },
  template: `
    <template v-if="isUpdatePrompt">
      <update-prompt-page />
    </template>
    <div v-else class="app-shell">
      <header class="top-bar">
        <div class="top-bar-left">
          <div class="logo-mark">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round">
              <path d="M12 2.5 3.5 7v10L12 21.5 20.5 17V7L12 2.5Z"/>
              <path d="M3.5 7 12 11.5 20.5 7"/>
              <path d="M12 11.5V21.5"/>
            </svg>
          </div>
          <div class="logo-text">
            <strong>MCAddonCompanion</strong>
            <span class="mono">{{ version ? 'v' + version : '' }}</span>
          </div>
        </div>

        <nav class="top-bar-nav">
          <button v-for="n in NAV" :key="n.key"
            class="nav-btn" :class="{ active: page === n.key }"
            @click="page = n.key">
            <span v-html="icon(n.icon, 14)"></span>
            {{ n.label }}
          </button>
        </nav>

        <div class="top-bar-right">
          <template v-if="updateInfo && !updateDismissed">
            <div style="display:flex;align-items:center;gap:8px;padding:4px 10px;background:var(--accent-soft,rgba(139,92,246,.15));border:1px solid var(--accent);border-radius:6px">
              <span class="fs-12 fw-500" style="color:var(--accent)">{{ updateInfo.label }} v{{ updateInfo.version }}</span>
              <button class="btn btn-primary btn-sm" style="font-size:11px;padding:3px 10px"
                :disabled="!!appUpdateState"
                @click="startUpdate">
                <span v-if="appUpdateState && appUpdateState.state==='downloading'" class="spin" v-html="icon('spin',11)"></span>
                <span v-else v-html="icon('download',11)"></span>
                {{ appUpdateState ? (appUpdateState.state === 'downloading' ? appUpdateState.pct + '%' : appUpdateState.state) : 'Update' }}
              </button>
              <button v-if="!appUpdateState" class="icon-btn" style="color:var(--text-3)" @click="updateDismissed = true">
                <span v-html="icon('x', 11)"></span>
              </button>
            </div>
          </template>
          <div style="position:relative">
            <button class="icon-btn" title="Menu" @click.stop="showMenu = !showMenu">
              <span v-html="icon('dots', 15)"></span>
            </button>
            <div v-if="showMenu" style="position:absolute;right:0;top:calc(100% + 6px);background:var(--bg-1);border:1px solid var(--line);border-radius:8px;padding:4px;min-width:180px;z-index:9998;box-shadow:0 4px 16px rgba(0,0,0,.3)">
              <button class="menu-item" style="display:flex;align-items:center;gap:8px;width:100%;padding:7px 10px;background:none;border:none;color:var(--text-0);cursor:pointer;border-radius:5px;font-size:13px;text-align:left" @click="openVersionModal">
                <span v-html="icon('bell', 14)"></span> Version &amp; Updates
              </button>
              <button class="menu-item" style="display:flex;align-items:center;gap:8px;width:100%;padding:7px 10px;background:none;border:none;color:var(--text-0);cursor:pointer;border-radius:5px;font-size:13px;text-align:left" @click="openDebugModal">
                <span v-html="icon('settings', 14)"></span> Help &amp; Debug
              </button>
            </div>
          </div>
        </div>
      </header>

      <div v-if="showMenu" style="position:fixed;inset:0;z-index:9997" @click="showMenu = false"></div>

      <div class="app-content">
        <component :is="PAGES[page]" :progress="progress" @navigate="page = $event" />
      </div>

      <footer class="footer">
        <div class="flex items-center gap-14">
          <span>© 2026 MCAddonCompanion</span>
          <span class="text-3">·</span>
          <span class="mono">{{ version ? 'v' + version : '' }}</span>
        </div>
        <div class="flex items-center gap-14">
          <span class="flex items-center gap-6">
            <span :class="['dot', updateInfo && !updateDismissed ? 'dot-warn' : 'dot-ok']"></span>
            <span>{{ updateInfo && !updateDismissed ? 'Update available' : 'Up to date' }}</span>
          </span>
        </div>
      </footer>
    </div>

    <!-- Version & Updates modal -->
    <teleport to="body">
      <div v-if="showVersionModal" style="position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:300" @click.self="showVersionModal = false">
        <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:420px;max-width:95vw;overflow:hidden">
          <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid var(--line)">
            <span class="fw-600 fs-14">Version &amp; Updates</span>
            <button class="icon-btn" @click="showVersionModal = false"><span v-html="icon('x', 14)"></span></button>
          </div>
          <div style="padding:20px;display:flex;flex-direction:column;gap:12px">
            <div class="kicker" style="margin-bottom:2px">App Info</div>
            <div style="padding:8px 12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--line);display:flex;flex-direction:column;gap:8px">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span class="text-2 fs-13">Version</span>
                <span class="mono fs-13">{{ version ? 'v' + version : '—' }}</span>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span class="text-2 fs-13">Status</span>
                <span class="fs-13" :style="updateInfo && !updateDismissed ? 'color:var(--accent)' : 'color:var(--text-ok,#4ade80)'">
                  {{ updateInfo && !updateDismissed ? 'Update available: v' + updateInfo.version : 'Up to date' }}
                </span>
              </div>
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
            </div>
            <button class="btn btn-ghost btn-sm" style="align-self:flex-start" @click="checkUpdateManual">
              <span v-html="icon('refresh', 13)"></span> Check for updates
            </button>
            <div v-if="manualUpdateResult" class="fs-12" style="padding:8px 12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--line)">
              <template v-if="manualUpdateResult.checking">Checking…</template>
              <template v-else-if="manualUpdateResult.upToDate">You are on the latest version.</template>
              <template v-else-if="manualUpdateResult.update">Update available: v{{ manualUpdateResult.update.version }}</template>
              <template v-else-if="manualUpdateResult.error">Error: {{ manualUpdateResult.error }}</template>
            </div>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Help & Debug modal -->
    <teleport to="body">
      <div v-if="showDebugModal" style="position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:300" @click.self="showDebugModal = false">
        <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:480px;max-width:95vw;max-height:85vh;overflow-y:auto">
          <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg-1);z-index:1">
            <span class="fw-600 fs-14">Help &amp; Debug</span>
            <button class="icon-btn" @click="showDebugModal = false"><span v-html="icon('x', 14)"></span></button>
          </div>
          <div style="padding:20px;display:flex;flex-direction:column;gap:16px">
            <div>
              <div class="kicker" style="margin-bottom:10px">Diagnostics</div>
              <div style="padding:8px 12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--line);display:flex;flex-direction:column;gap:6px">
                <template v-if="hostInfo">
                  <div v-for="(val, key) in hostInfo" :key="key" style="display:flex;justify-content:space-between;align-items:center">
                    <span class="text-2 fs-13">{{ key }}</span>
                    <span class="mono fs-12 text-0">{{ val }}</span>
                  </div>
                </template>
                <span v-else class="fs-13 text-3">Loading…</span>
              </div>
              <div style="margin-top:10px;padding:8px 12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--line)">
                <div class="fs-13 fw-500 text-0" style="margin-bottom:6px">Debug Dump</div>
                <div class="fs-12 text-3" style="margin-bottom:8px">Saves a zip with logs, redacted config, and system info to your Downloads folder.</div>
                <button class="btn btn-ghost btn-sm" :disabled="dumpState && dumpState.running" @click="createDump">
                  <span v-html="icon('download', 12)"></span>
                  {{ dumpState && dumpState.running ? 'Creating…' : 'Save Debug Dump' }}
                </button>
                <div v-if="dumpState && !dumpState.running" style="margin-top:6px" :style="dumpState.ok ? 'color:var(--ok)' : 'color:var(--err)'" class="fs-12">
                  <template v-if="dumpState.ok">Saved: {{ dumpState.filename }} — Downloads folder opened</template>
                  <template v-else>Error: {{ dumpState.error }}</template>
                </div>
              </div>
            </div>

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

            <div>
              <div class="kicker" style="margin-bottom:10px">Reset Module Data</div>
              <div style="display:flex;flex-direction:column;gap:8px">
                <template v-for="mod in ['schematic_sync','instance_sync','pack_registry']" :key="mod">
                  <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--line)">
                    <div>
                      <div class="fs-13 fw-500 text-0">{{ {'schematic_sync':'Schematic Sync','instance_sync':'Instance Sync','pack_registry':'Pack Registry'}[mod] }}</div>
                      <div v-if="resetResult[mod] === 'ok'" class="fs-12" style="color:var(--ok)">Reset complete</div>
                      <div v-else-if="resetResult[mod] === 'error'" class="fs-12" style="color:var(--err)">Reset failed</div>
                    </div>
                    <template v-if="resetConfirm === mod">
                      <div class="flex items-center gap-6">
                        <span class="fs-12 text-2">Sure?</span>
                        <button class="btn btn-sm" style="background:var(--err);border-color:var(--err);color:#fff;font-size:11px" @click="confirmReset(mod)">Yes, reset</button>
                        <button class="btn btn-ghost btn-sm" style="font-size:11px" @click="resetConfirm = null">Cancel</button>
                      </div>
                    </template>
                    <button v-else class="btn btn-ghost btn-sm" style="font-size:11px;color:var(--err);border-color:var(--err)" @click="resetConfirm = mod">Reset</button>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </teleport>
  `
}

const app = createApp(App)
app.config.errorHandler = (err, _instance, info) => {
  const text = `${info}: ${err?.stack || err}`
  window.__apiReady.then(() => window.pywebview.api.log_js_error('error', '[vue] ' + text).catch(() => {}))
  console.error('[vue errorHandler]', err)
}
app.component('update-prompt-page', UpdatePromptPage).mount('#app')
