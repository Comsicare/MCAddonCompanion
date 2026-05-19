import { ref, onMounted, onUnmounted } from '../vue.esm-browser.js'

export default {
  setup() {
    const data = ref(null)
    const loading = ref(true)
    const countdown = ref(30)
    const icon = (name, size = 16) => window.__icon(name, size)

    let timer = null

    const choose = async (choice) => {
      clearInterval(timer)
      await window.__apiReady
      await window.pywebview.api.set_deletion_choice(choice)
    }

    onMounted(async () => {
      await window.__apiReady
      data.value = await window.pywebview.api.get_deletion_data()
      countdown.value = data.value.timeout || 30
      loading.value = false
      timer = setInterval(() => {
        countdown.value--
        if (countdown.value <= 0) {
          clearInterval(timer)
          choose('cancel')
        }
      }, 1000)
    })

    onUnmounted(() => clearInterval(timer))

    return { data, loading, countdown, icon, choose }
  },
  template: `
    <div style="display:flex;flex-direction:column;height:100vh;background:var(--bg-1);padding:24px;box-sizing:border-box;gap:16px">
      <div v-if="loading" class="fs-13 text-2">Loading...</div>
      <template v-else>
        <div style="display:flex;align-items:center;gap:10px">
          <span v-html="icon('alert', 22)" style="color:#f59e0b;flex:none"></span>
          <div>
            <div class="fw-600 text-0 fs-14">Files deleted since last sync</div>
            <div class="fs-12 text-2">{{ data.instance }}</div>
          </div>
        </div>

        <div style="padding:10px 14px;background:var(--bg-2);border:1px solid var(--line);border-radius:8px;flex:1;overflow-y:auto;min-height:0">
          <div class="fs-12 text-3 fw-500" style="margin-bottom:6px">{{ data.deleted.length }} file{{ data.deleted.length !== 1 ? 's' : '' }} removed from instance:</div>
          <div v-for="f in data.deleted" :key="f" class="mono fs-11 text-2" style="padding:1px 0">{{ f }}</div>
        </div>

        <div style="padding:10px 14px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.35);border-radius:8px;font-size:12px;color:#f59e0b">
          No response in {{ countdown }}s will cancel the sync.
        </div>

        <div style="display:flex;gap:8px">
          <button class="btn btn-ghost btn-sm" style="flex:1;font-size:11px" @click="choose('cancel')">
            Cancel sync
          </button>
          <button class="btn btn-ghost btn-sm" style="flex:1;font-size:11px" @click="choose('keep')">
            Keep in sync
          </button>
          <button class="btn btn-primary btn-sm" style="flex:1;font-size:11px" @click="choose('sync')">
            Sync deletions
          </button>
        </div>
      </template>
    </div>
  `
}
