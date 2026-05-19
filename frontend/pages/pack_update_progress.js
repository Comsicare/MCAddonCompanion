import { ref, onMounted, onUnmounted } from '../vue.esm-browser.js'
import ActionModal from '../components/action-modal.js'

const STEPS = ['Download zip', 'Extract files']

export default {
  components: { ActionModal },
  setup() {
    const modal = ref({
      show: true, phase: 'progress', done: false, error: false,
      title: 'Updating pack…', summary: '', deletions: [],
      steps: STEPS.map(l => ({ label: l, state: 'idle', detail: '', pct: null })),
      logs: [],
    })

    const onProgress = (event) => {
      if (event.flow !== 'install') return
      if (event.type === 'progress') {
        const s = modal.value.steps[event.step]
        if (s) s.pct = event.pct
      } else if (event.type === 'step') {
        const s = modal.value.steps[event.step]
        if (s) {
          s.state = event.state === 'ok' ? 'done' : event.state === 'error' ? 'err' : 'run'
          s.detail = event.detail || ''
          if (event.state === 'ok' || event.state === 'error') s.pct = null
        }
      } else if (event.type === 'summary') {
        modal.value.done = true
        modal.value.error = event.tone !== 'ok'
        modal.value.title = event.tone === 'ok' ? 'Update complete' : 'Update failed'
        modal.value.summary = event.text
        modal.value.logs.push(event.text)
      }
    }

    const close = async () => {
      await window.__apiReady
      await window.pywebview.api.close_progress_window()
    }

    onMounted(() => { window.__onProgress = onProgress })
    onUnmounted(() => { window.__onProgress = null })

    return { modal, close, ActionModal }
  },
  template: `
    <div style="display:flex;flex-direction:column;height:100vh;background:var(--bg-1);padding:24px;box-sizing:border-box">
      <action-modal
        :show="modal.show"
        :phase="modal.phase"
        :title="modal.title"
        :summary="modal.summary"
        :steps="modal.steps"
        :logs="modal.logs"
        :done="modal.done"
        :error="modal.error"
        @confirm="close"
        @cancel="close"
      />
    </div>
  `
}
