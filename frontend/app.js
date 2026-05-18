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
window.addEventListener('pywebviewready', () => __apiReadyResolve())

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

    const showMenu = ref(false)
    const showVersionModal = ref(false)
    const checkingUpdate = ref(false)
    const manualUpdateResult = ref(null) // null | 'ok' | 'none' | 'error'

    const toggleMenu = () => { showMenu.value = !showMenu.value }
    const closeMenu = () => { showMenu.value = false }

    const openVersionModal = () => {
      showMenu.value = false
      manualUpdateResult.value = null
      showVersionModal.value = true
    }

    const checkUpdateManual = async () => {
      checkingUpdate.value = true
      manualUpdateResult.value = null
      try {
        await window.__apiReady
        const info = await window.pywebview.api.check_update()
        if (info) {
          updateInfo.value = info
          updateDismissed.value = false
          manualUpdateResult.value = 'ok'
        } else {
          manualUpdateResult.value = 'none'
        }
      } catch(e) {
        manualUpdateResult.value = 'error'
      }
      checkingUpdate.value = false
    }

    const openDebugModal = () => {}  // implemented in Task 3

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

    return {
      page, progress, version, updateInfo, updateDismissed, appUpdateState, startUpdate,
      NAV, PAGES, icon, isUpdatePrompt, UpdatePromptPage,
      showMenu, toggleMenu, closeMenu,
      showVersionModal, checkingUpdate, manualUpdateResult, openVersionModal, checkUpdateManual, openDebugModal,
    }
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
          <div class="dropdown-wrap" v-click-outside="closeMenu">
            <button class="icon-btn" :class="{ active: showMenu }" title="Menu" @click="toggleMenu">
              <span v-html="icon('dots', 15)"></span>
            </button>
            <div v-if="showMenu" class="dropdown-panel">
              <button class="dropdown-item" @click="page = 'instance_sync'; closeMenu()">
                <span v-html="icon('settings', 14)"></span> Settings
              </button>
              <div class="dropdown-sep"></div>
              <button class="dropdown-item" @click="openVersionModal">
                <span v-html="icon('bell', 14)"></span> Version &amp; Updates
              </button>
              <button class="dropdown-item" @click="openDebugModal(); closeMenu()">
                <span v-html="icon('alert', 14)"></span> Help &amp; Debug
              </button>
            </div>
          </div>
        </div>
      </header>

      <div class="app-content">
        <component :is="PAGES[page]" :progress="progress" @navigate="page = $event" />
      </div>

      <!-- Version & Updates modal -->
      <teleport to="body">
        <div v-if="showVersionModal"
          style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px"
          @mousedown.self="showVersionModal = false">
          <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:420px;overflow:hidden">
            <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between">
              <div class="fw-600 text-0" style="font-size:15px">Version &amp; Updates</div>
              <button class="icon-btn" @click="showVersionModal = false"><span v-html="icon('x',13)"></span></button>
            </div>
            <div style="padding:20px 24px;display:flex;flex-direction:column;gap:16px">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span class="text-2 fs-13">Current version</span>
                <span class="mono fw-600 text-0">{{ version ? 'v' + version : '—' }}</span>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span class="text-2 fs-13">Status</span>
                <span v-if="updateInfo && !updateDismissed" class="pill pill-warn">Update available — v{{ updateInfo.version }}</span>
                <span v-else-if="manualUpdateResult === 'none'" class="pill pill-ok">Up to date</span>
                <span v-else class="pill pill-off">—</span>
              </div>
              <template v-if="updateInfo && !updateDismissed">
                <button class="btn btn-primary btn-sm flex items-center gap-6"
                  :disabled="!!appUpdateState"
                  @click="startUpdate">
                  <span v-if="appUpdateState && appUpdateState.state==='downloading'" v-html="icon('spin',13)"></span>
                  <span v-else v-html="icon('download',13)"></span>
                  {{ appUpdateState ? (appUpdateState.state === 'downloading' ? appUpdateState.pct + '%' : appUpdateState.state) : 'Install update' }}
                </button>
              </template>
              <div style="border-top:1px solid var(--line);padding-top:16px;display:flex;justify-content:flex-end">
                <button class="btn btn-ghost btn-sm flex items-center gap-6"
                  :disabled="checkingUpdate"
                  @click="checkUpdateManual">
                  <span v-if="checkingUpdate" v-html="icon('spin',13)"></span>
                  <span v-else v-html="icon('refresh',13)"></span>
                  {{ checkingUpdate ? 'Checking…' : 'Check for updates' }}
                </button>
              </div>
              <div v-if="manualUpdateResult === 'error'" class="fs-12" style="color:var(--err)">Check failed — verify your connection.</div>
            </div>
          </div>
        </div>
      </teleport>

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
  `
}

const app = createApp(App)
  .component('update-prompt-page', UpdatePromptPage)

app.directive('click-outside', {
  mounted(el, binding) {
    el.__clickOutside = (e) => { if (!el.contains(e.target)) binding.value(e) }
    document.addEventListener('mousedown', el.__clickOutside)
  },
  unmounted(el) {
    document.removeEventListener('mousedown', el.__clickOutside)
    delete el.__clickOutside
  },
})

app.mount('#app')
