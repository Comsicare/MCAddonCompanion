import { ref, onMounted, onUnmounted, computed } from '../vue.esm-browser.js'

export default {
  setup() {
    const data = ref(null)
    const loading = ref(true)
    const countdown = ref(20)
    const icon = (name, size = 16) => window.__icon(name, size)

    let timer = null

    const skip = async () => {
      clearInterval(timer)
      await window.__apiReady
      await window.pywebview.api.submit_update_choice('skip')
    }

    const update = async () => {
      clearInterval(timer)
      await window.__apiReady
      await window.pywebview.api.submit_update_choice('update')
    }

    onMounted(async () => {
      await window.__apiReady
      data.value = await window.pywebview.api.get_update_prompt_data()
      loading.value = false
      timer = setInterval(() => {
        countdown.value--
        if (countdown.value <= 0) {
          clearInterval(timer)
          skip()
        }
      }, 1000)
    })

    onUnmounted(() => clearInterval(timer))

    const modDiff = computed(() => {
      if (!data.value) return { added: [], removed: [] }
      return {
        added: data.value.added_mods || [],
        removed: data.value.removed_mods || [],
      }
    })

    return { data, loading, countdown, icon, skip, update, modDiff }
  },
  template: `
    <div style="display:flex;flex-direction:column;height:100vh;background:var(--bg-1);padding:32px;box-sizing:border-box">
      <div v-if="loading" class="loading">Loading…</div>
      <template v-else>
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px">
          <span v-html="icon('cube', 28)" style="color:var(--accent)"></span>
          <div>
            <div class="fw-600 text-0" style="font-size:16px">Update available</div>
            <div class="text-2 fs-13">{{ data.pack_name }}</div>
          </div>
        </div>

        <div class="card" style="margin-bottom:16px">
          <div class="card-body" style="display:flex;align-items:center;gap:24px;padding:16px 20px">
            <div style="text-align:center">
              <div class="fs-12 text-3 mb-4">Installed</div>
              <div class="mono fw-500 text-2">{{ data.installed_version }}</div>
            </div>
            <span v-html="icon('caret', 16)" style="color:var(--text-3);transform:rotate(-90deg);display:inline-flex"></span>
            <div style="text-align:center">
              <div class="fs-12 text-3 mb-4">New</div>
              <div class="mono fw-500 text-0">{{ data.new_version }}</div>
            </div>
          </div>
        </div>

        <div v-if="data.changenotes" class="card" style="margin-bottom:16px;flex:1;overflow:auto">
          <div class="card-header" style="padding:12px 16px">
            <div class="kicker">Changenotes</div>
          </div>
          <div class="card-body fs-13 text-1" style="padding:12px 16px;white-space:pre-wrap">{{ data.changenotes }}</div>
        </div>

        <div v-if="(modDiff.added && modDiff.added.length) || (modDiff.removed && modDiff.removed.length)" class="card" style="margin-bottom:16px">
          <div class="card-header" style="padding:12px 16px">
            <div class="kicker">Mod changes</div>
          </div>
          <div class="card-body" style="padding:8px 16px">
            <template v-if="modDiff.added && modDiff.added.length">
              <div class="fs-11 text-3 fw-500" style="margin-bottom:4px;margin-top:4px">Added</div>
              <div v-for="jar in modDiff.added" :key="'a'+jar" class="mono fs-12" style="padding:2px 0;color:var(--ok)">+ {{ jar }}</div>
            </template>
            <template v-if="modDiff.removed && modDiff.removed.length">
              <div class="fs-11 text-3 fw-500" style="margin-bottom:4px;margin-top:8px">Removed</div>
              <div v-for="jar in modDiff.removed" :key="'r'+jar" class="mono fs-12 text-err" style="padding:2px 0">- {{ jar }}</div>
            </template>
          </div>
        </div>

        <div style="display:flex;gap:10px;margin-top:auto;padding-top:16px">
          <button class="btn btn-ghost btn-sm" style="flex:1" @click="skip">
            Skip ({{ countdown }}s)
          </button>
          <button class="btn btn-primary btn-sm" style="flex:1" @click="update">
            Update
          </button>
        </div>
      </template>
    </div>
  `
}
