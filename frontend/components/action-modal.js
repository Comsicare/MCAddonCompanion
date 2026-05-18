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
            <template v-for="(s, i) in steps" :key="i">
              <div class="progress-step">
                <span class="progress-step-icon" :class="s.state">
                  <span v-if="s.state === 'done'" style="font-size:10px">✓</span>
                  <span v-else-if="s.state === 'run'" class="spin" style="font-size:10px">↻</span>
                  <span v-else-if="s.state === 'err'" style="font-size:10px">✕</span>
                </span>
                <span class="fs-13 text-0">{{ s.label }}</span>
                <span class="mono fs-11 text-3" style="margin-left:auto">
                  <span v-if="s.state === 'run' && s.pct !== null">{{ s.pct }}%</span>
                  <span v-else-if="s.detail">{{ s.detail }}</span>
                </span>
              </div>
              <div v-if="s.state === 'run' && s.pct !== null"
                style="margin:2px 0 6px 28px;height:4px;background:var(--bg-0);border-radius:2px;overflow:hidden">
                <div :style="'width:' + s.pct + '%;height:100%;background:var(--accent);border-radius:2px;transition:width .15s linear'"></div>
              </div>
            </template>
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
