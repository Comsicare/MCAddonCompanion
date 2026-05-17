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

    window.__onProgress = (event) => {
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

    return { page, progress, version, updateInfo, NAV, PAGES, icon, isUpdatePrompt, UpdatePromptPage }
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
          <div class="prism-status">
            <span class="dot dot-ok"></span>
            <span style="color: var(--text-1)">Prism</span>
            <span>connected</span>
          </div>
          <button class="icon-btn" title="Notifications">
            <span v-html="icon('bell', 15)"></span>
          </button>
          <button class="icon-btn" title="Menu">
            <span v-html="icon('dots', 15)"></span>
          </button>
        </div>
      </header>

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
            <span class="dot dot-ok"></span>
            <span>Up to date</span>
          </span>
          <span class="text-3">·</span>
          <a href="#" style="color: var(--text-2); text-decoration: none;">Release notes</a>
        </div>
      </footer>
    </div>
  `
}

createApp(App)
  .component('update-prompt-page', UpdatePromptPage)
  .mount('#app')
