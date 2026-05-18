import { ref, onMounted, computed, watch } from '../vue.esm-browser.js'
import ActionModal from '../components/action-modal.js'

const PUBLISH_STEPS = ['Build zip', 'Upload pack', 'Upload metadata']

export default {
  props: ['progress'],
  emits: ['navigate'],
  components: { ActionModal },
  setup(props) {
    const tab = ref('repos')

    // ── Instances tab ────────────────────────────────────────────────────────
    const installedInstances = ref([])
    const instancesLoading = ref(false)
    // Per-instance progress: { [instance_name]: {steps, summary, active} }
    const instanceProgress = ref({})

    const _initInstProgress = (instName) => {
      instanceProgress.value[instName] = {
        steps: INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })),
        summary: null,
        active: true,
      }
    }

    const loadInstalledInstances = async () => {
      instancesLoading.value = true
      try {
        await window.__apiReady
        installedInstances.value = await window.pywebview.api.get_installed_instances()
      } catch(e) {
        installedInstances.value = []
      }
      instancesLoading.value = false
      // Fetch update status in background — never blocks or resets the table
      try {
        const updates = await window.pywebview.api.get_instance_update_status()
        const map = {}
        updates.forEach(u => { map[u.instance_name] = u })
        installedInstances.value = installedInstances.value.map(inst => ({
          ...inst,
          ...(map[inst.instance_name] || {}),
        }))
      } catch(e) {}
    }

    const untrackInstance = async (instName) => {
      try {
        await window.__apiReady
        await window.pywebview.api.untrack_pack(instName)
        await loadInstalledInstances()
      } catch(e) {}
    }

    const toggleHook = async (inst) => {
      try {
        await window.__apiReady
        const next = !inst.hook_enabled
        await window.pywebview.api.set_instance_hook(inst.instance_name, next)
        inst.hook_enabled = next
      } catch(e) {}
    }

    const removeInstalledRecord = async (instName) => {
      try {
        await window.__apiReady
        await window.pywebview.api.remove_installed_instance(instName)
        await loadInstalledInstances()
      } catch(e) {}
    }

    const reinstallInstance = async (inst) => {
      try {
        await window.__apiReady
        _initInstProgress(inst.instance_name)
        const params = {
          repo_id: inst.repo_id,
          pack_name: inst.pack_name,
          version: inst.installed_version,
          instance_name: inst.instance_name,
          mode: 'new',
          track: inst.tracked,
        }
        await window.pywebview.api.install_pack({ ...params, skip_files: [] })
      } catch(e) {
        if (instanceProgress.value[inst.instance_name])
          instanceProgress.value[inst.instance_name].summary = { tone: 'error', text: String(e) }
      }
    }

    const installUpdate = async (inst) => {
      try {
        await window.__apiReady
        const conflicts = await window.pywebview.api.check_conflicts(
          inst.repo_id,
          inst.pack_name,
          inst.latest_version,
          inst.instance_name
        )
        const params = {
          repo_id: inst.repo_id,
          pack_name: inst.pack_name,
          version: inst.latest_version,
          instance_name: inst.instance_name,
          mode: 'existing',
          track: inst.tracked,
        }
        if (conflicts.length) {
          conflictGroups.value = groupConflicts(conflicts)
          conflictInstallParams.value = params
          showConflictModal.value = true
        } else {
          _initInstProgress(inst.instance_name)
          await window.pywebview.api.install_pack({ ...params, skip_files: [] })
        }
      } catch(e) {
        if (instanceProgress.value[inst.instance_name])
          instanceProgress.value[inst.instance_name].summary = { tone: 'error', text: String(e) }
      }
    }
    const icon = (name, size = 16) => window.__icon(name, size)

    // ── Repos tab ────────────────────────────────────────────────────────────
    const repos = ref([])
    const reposLoading = ref(true)
    const selectedRepo = ref(null)
    const repoForm = ref({ id: null, name: '', url: '', pat_token: '', deploy_token: '' })
    const repoSaving = ref(false)
    const repoError = ref(null)
    const repoSuccess = ref(false)
    const testResult = ref(null)
    const testLoading = ref(false)

    const loadRepos = async () => {
      reposLoading.value = true
      try {
        await window.__apiReady
        repos.value = await window.pywebview.api.get_repos()
      } catch(e) {}
      reposLoading.value = false
    }

    const selectRepo = (repo) => {
      selectedRepo.value = repo
      repoForm.value = {
        id: repo.id,
        name: repo.name,
        url: repo.project_url || repo.base_url,
        pat_token: repo.read_token || '',
        deploy_token: repo.upload_token || '',
      }
      repoError.value = null
      repoSuccess.value = false
      testResult.value = null
    }

    const newRepo = () => {
      selectedRepo.value = null
      repoForm.value = { id: null, name: '', url: '', pat_token: '', deploy_token: '' }
      repoError.value = null
      repoSuccess.value = false
      testResult.value = null
    }

    const saveRepo = async () => {
      repoSaving.value = true
      repoError.value = null
      repoSuccess.value = false
      try {
        const saved = await window.pywebview.api.save_repo(repoForm.value)
        repoSuccess.value = true
        await loadRepos()
        selectedRepo.value = saved
      } catch(e) {
        repoError.value = String(e)
      }
      repoSaving.value = false
    }

    const deleteRepo = async (id) => {
      try {
        await window.pywebview.api.delete_repo(id)
        selectedRepo.value = null
        await loadRepos()
      } catch(e) {}
    }

    const testConnection = async () => {
      testLoading.value = true
      testResult.value = null
      try {
        await window.pywebview.api.save_repo({ ...repoForm.value, _test_only: true })
        testResult.value = { ok: true, msg: 'Connection successful' }
      } catch(e) {
        testResult.value = { ok: false, msg: String(e) }
      }
      testLoading.value = false
    }

    // ── Publish tab ──────────────────────────────────────────────────────────
    const allInstances = ref([])
    const publishForm = ref({
      repo_id: '',
      instance_name: '',
      pack_name: '',
      version: '',
      description: '',
      changenotes: '',
      mc_version: '',
      loader: 'fabric',
      loader_version: '',
      categories: { mods: true, config: true, resourcepacks: false, shaderpacks: false, saves: false, schematics: false },
    })
    const modFiles = ref([])  // [{file: string, side: string}]
    const publishSteps = computed(() => {
      const p = props.progress || {}
      return PUBLISH_STEPS.map((label, i) => {
        if (p.step === i) return { label, state: p.state || 'run', detail: p.detail || '' }
        if (typeof p.step === 'number' && i < p.step) return { label, state: 'ok', detail: '' }
        return { label, state: 'idle', detail: '' }
      })
    })
    const publishSummary = computed(() => props.progress?.text || '')
    const publishTone = computed(() => props.progress?.tone || 'ok')
    const publishing = ref(false)
    const existingPacks = ref([])
    const packNameIsNew = ref(false)

    const loadExistingPacks = async () => {
      const repoId = publishForm.value.repo_id
      if (!repoId) { existingPacks.value = []; return }
      try {
        await window.__apiReady
        existingPacks.value = await window.pywebview.api.get_packs(repoId)
      } catch(e) { existingPacks.value = [] }
    }

    watch(() => publishForm.value.repo_id, () => {
      loadExistingPacks()
      packNameIsNew.value = false
    })

    const loadInstances = async () => {
      try {
        await window.__apiReady
        allInstances.value = await window.pywebview.api.get_all_instances()
        if (allInstances.value.length && !publishForm.value.instance_name) {
          publishForm.value.instance_name = allInstances.value[0]
          await loadMeta(allInstances.value[0])
        }
      } catch(e) {}
    }

    const loadMeta = async (name) => {
      try {
        await window.__apiReady
        const m = await window.pywebview.api.read_instance_meta(name)
        publishForm.value.mc_version = m.mc_version || ''
        publishForm.value.loader = m.loader || ''
        publishForm.value.loader_version = m.loader_version || ''
      } catch(e) {}
    }

    const loadModFiles = async () => {
      if (!publishForm.value.instance_name || !publishForm.value.categories.mods) {
        modFiles.value = []
        return
      }
      try {
        await window.__apiReady
        const files = await window.pywebview.api.get_instance_mod_files(publishForm.value.instance_name)
        // Start with defaults, then overlay tags from previous version if pack is selected
        const tagged = files.map(f => ({ file: f, side: 'required', excluded: false }))
        modFiles.value = tagged
        const packName = publishForm.value.pack_name
        const repoId = publishForm.value.repo_id
        if (packName && repoId && !packNameIsNew.value) {
          try {
            const prevMeta = await window.pywebview.api.get_latest_pack_metadata(repoId, packName)
            if (prevMeta && prevMeta.mods) {
              const sideMap = {}
              const excludedSet = new Set()
              prevMeta.mods.forEach(m => { sideMap[m.file] = m.side })
              // files not in previous mods list were excluded (not in metadata = excluded or new)
              // only auto-exclude if they were present before but removed (i.e., in removed_mods)
              ;(prevMeta.removed_mods || []).forEach(f => excludedSet.add(f))
              modFiles.value = tagged.map(m => ({
                ...m,
                side: sideMap[m.file] || 'required',
                excluded: excludedSet.has(m.file),
              }))
            }
          } catch(e) {}
        }
      } catch(e) {
        modFiles.value = []
      }
    }

    watch(() => publishForm.value.instance_name, (name) => {
      if (name) {
        loadMeta(name)
        // only pre-fill pack_name when in "new" mode and it's still empty
        if (packNameIsNew.value && !publishForm.value.pack_name) {
          publishForm.value.pack_name = name
        }
        loadModFiles()
      }
    })

    watch(() => publishForm.value.categories.mods, () => loadModFiles())
    watch(() => publishForm.value.pack_name, () => { if (!packNameIsNew.value) loadModFiles() })

    const publish = async () => {
      if (publishing.value) return
      publishing.value = true
      try {
        const mod_tags = {}
        modFiles.value.forEach(m => { if (!m.excluded) mod_tags[m.file] = m.side })
        await window.__apiReady
        await window.pywebview.api.publish_pack({
          repo_id: publishForm.value.repo_id,
          instance_name: publishForm.value.instance_name,
          pack_name: publishForm.value.pack_name,
          version: publishForm.value.version,
          description: publishForm.value.description,
          changenotes: publishForm.value.changenotes,
          mc_version: publishForm.value.mc_version,
          loader: publishForm.value.loader,
          loader_version: publishForm.value.loader_version,
          categories: publishForm.value.categories,
          mod_tags,
        })
      } catch(e) {}
      publishing.value = false
    }

    const clearPublish = () => {
      // reset progress by emitting reset — can only suggest user refresh
    }

    // ── Browse tab ───────────────────────────────────────────────────────────
    const browseRepoId = ref('')
    const packs = ref([])
    const packsLoading = ref(false)
    const selectedPack = ref(null)
    const packVersions = ref([])           // [{version, metadata}]
    const versionsLoading = ref(false)
    const selectedVersionObj = ref(null)   // {version, metadata}
    const trackOnInstall = ref(false)
    // conflict modal state
    const showConflictModal = ref(false)
    const conflictGroups = ref([])   // [{folder, files: [{path, keep}]}]
    const conflictInstallParams = ref(null)  // params to pass to install after resolution
    const showClientModModal = ref(false)
    const clientModList = ref([])   // [{ file, name, include }]
    const clientInstallParams = ref(null)
    const installMode = ref('new')         // 'new' | 'existing'
    const installInstanceName = ref('')
    const installExistingInstance = ref('')
    const installing = ref(false)
    const INSTALL_STEPS = ['Download zip', 'Extract files', 'Create instance']
    const _makeModal = () => ({
      show: false, phase: 'summary', done: false, error: false,
      title: '', summary: '', deletions: [],
      steps: [], logs: [],
    })
    const installModal = ref(_makeModal())
    const publishModal = ref(_makeModal())
    const updateModal  = ref(_makeModal())

    const routeToModal = (modal, event) => {
      if (event.type === 'reset') {
        modal.value.steps = modal.value.steps.map(s => ({ ...s, state: 'idle', detail: '' }))
        modal.value.logs = []
      } else if (event.type === 'step') {
        const s = modal.value.steps[event.step]
        if (s) {
          s.state = event.state === 'ok' ? 'done' : event.state === 'error' ? 'err' : 'run'
          s.detail = event.detail || ''
          const label = s.label
          const logLine = `[${label}] ${event.detail || s.state}`
          const existingIdx = modal.value.logs.findLastIndex(l => l.startsWith(`[${label}]`))
          if (existingIdx >= 0) modal.value.logs[existingIdx] = logLine
          else modal.value.logs.push(logLine)
        }
      } else if (event.type === 'summary') {
        modal.value.done = true
        modal.value.error = event.tone !== 'ok'
        modal.value.logs.push(event.text)
      }
    }
    const installSteps = ref(INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })))
    const installSummary = ref(null)

    const SERVER_PACK_STEPS = ['Download pack', 'Build server pack', 'Save to folder']
    const showServerModal = ref(false)
    const serverModalStep = ref(1)
    const serverDest = ref('')
    const serverAsZip = ref(true)
    const serverIncludeConfig = ref(true)
    const serverProgress = ref(SERVER_PACK_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })))
    const serverSummary = ref(null)

    const loadPacks = async () => {
      if (!browseRepoId.value) return
      packsLoading.value = true
      packs.value = []
      selectedPack.value = null
      packVersions.value = []
      selectedVersionObj.value = null
      try {
        await window.__apiReady
        packs.value = await window.pywebview.api.get_packs(browseRepoId.value)
      } catch(e) {}
      packsLoading.value = false
    }

    const selectPack = async (name) => {
      selectedPack.value = name
      packVersions.value = []
      selectedVersionObj.value = null
      versionsLoading.value = true
      try {
        await window.__apiReady
        const versions = await window.pywebview.api.get_versions(browseRepoId.value, name)
        packVersions.value = versions  // [{version, metadata}]
        if (versions.length) selectVersion(versions[0])
      } catch(e) {}
      versionsLoading.value = false
    }

    const selectVersion = (versionObj) => {
      selectedVersionObj.value = versionObj
      const meta = versionObj?.metadata || {}
      installInstanceName.value = meta.pack_name || selectedPack.value || ''
    }

    // Group flat conflict paths by first folder segment
    const groupConflicts = (paths) => {
      const map = {}
      for (const p of paths) {
        const slash = p.indexOf('/')
        const folder = slash >= 0 ? p.slice(0, slash) : '(root)'
        if (!map[folder]) map[folder] = []
        map[folder].push({ path: p, keep: false })
      }
      return Object.entries(map).map(([folder, files]) => ({
        folder,
        files,
        get allKeep() { return files.every(f => f.keep) },
        toggleAll(v) { files.forEach(f => f.keep = v) },
      }))
    }

    const doInstall = async (params, skipFiles = []) => {
      installing.value = true
      installSteps.value = INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' }))
      installSummary.value = null
      try {
        await window.__apiReady
        await window.pywebview.api.install_pack({ ...params, skip_files: skipFiles })
      } catch(e) {
        installSummary.value = { tone: 'error', text: String(e) }
        installing.value = false
      }
    }

    const installPack = async (extraSkipFiles = []) => {
      if (installing.value) return
      const instName = installMode.value === 'new'
        ? installInstanceName.value
        : installExistingInstance.value
      if (!instName || !selectedPack.value || !selectedVersionObj.value) return
      await doInstall({
        repo_id: browseRepoId.value,
        pack_name: selectedPack.value,
        version: selectedVersionObj.value.version,
        instance_name: instName,
        mode: installMode.value,
        track: trackOnInstall.value,
      }, extraSkipFiles)
    }

    const checkAndInstall = async () => {
      if (installMode.value === 'existing' && installExistingInstance.value) {
        try {
          await window.__apiReady
          const conflicts = await window.pywebview.api.check_conflicts(
            browseRepoId.value,
            selectedPack.value,
            selectedVersionObj.value.version,
            installExistingInstance.value
          )
          if (conflicts.length) {
            conflictGroups.value = groupConflicts(conflicts)
            conflictInstallParams.value = {
              repo_id: browseRepoId.value,
              pack_name: selectedPack.value,
              version: selectedVersionObj.value.version,
              instance_name: installExistingInstance.value,
              mode: 'existing',
              track: trackOnInstall.value,
            }
            showConflictModal.value = true
            return
          }
        } catch(e) {}
      }
      const instName = installMode.value === 'new'
        ? installInstanceName.value
        : installExistingInstance.value
      openClientModReview({
        repo_id: browseRepoId.value,
        pack_name: selectedPack.value,
        version: selectedVersionObj.value.version,
        instance_name: instName,
        mode: installMode.value,
        track: trackOnInstall.value,
        skip_files: [],
      })
    }

    const openClientModReview = (params) => {
      const mods = selectedVersionObj.value?.metadata?.mods || []
      const clientMods = mods.filter(m => m.side === 'client')
      if (!clientMods.length) {
        openInstallModal(params, params.skip_files || [], [])
        return
      }
      clientModList.value = clientMods.map(m => ({
        file: m.file,
        name: m.file.replace(/\.jar$/i, ''),
        include: true,
      }))
      clientInstallParams.value = params
      showClientModModal.value = true
    }

    const clientModAllSelected = computed(() =>
      clientModList.value.every(m => m.include)
    )

    const toggleAllClientMods = (val) => {
      clientModList.value.forEach(m => { m.include = val })
    }

    const confirmClientModInstall = async () => {
      showClientModModal.value = false
      const excluded = clientModList.value.filter(m => !m.include).map(m => m.file)
      const params = { ...clientInstallParams.value, excluded_mods: excluded }
      openInstallModal(params, clientInstallParams.value.skip_files || [], excluded)
    }

    const openInstallModal = (params, skipFiles, excludedMods) => {
      const mode = params.mode === 'new' ? 'new instance' : 'existing instance'
      installModal.value = {
        show: true, phase: 'summary', done: false, error: false,
        title: 'Install Pack',
        summary: `${params.pack_name} v${params.version} → ${params.instance_name} (${mode})`,
        deletions: [...(skipFiles || []), ...(excludedMods || [])],
        steps: INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' })),
        logs: [],
        _params: params,
      }
    }

    const confirmInstall = async () => {
      const params = installModal.value._params
      installModal.value.phase = 'progress'
      try {
        await window.__apiReady
        await window.pywebview.api.install_pack(params)
      } catch(e) {
        installModal.value.done = true
        installModal.value.error = true
        installModal.value.logs.push(`Error: ${e}`)
      }
    }

    const retryInstall = async () => {
      installModal.value.steps = INSTALL_STEPS.map(l => ({ label: l, state: 'idle', detail: '' }))
      installModal.value.logs = []
      installModal.value.done = false
      installModal.value.error = false
      await confirmInstall()
    }

    const closeInstallModal = () => {
      const wasOk = installModal.value.done && !installModal.value.error
      installModal.value = _makeModal()
      if (wasOk) loadInstalledInstances()
    }

    const openServerModal = async () => {
      serverModalStep.value = 1
      serverAsZip.value = true
      serverIncludeConfig.value = true
      serverProgress.value = SERVER_PACK_STEPS.map(l => ({ label: l, state: 'idle', detail: '' }))
      serverSummary.value = null
      try {
        await window.__apiReady
        serverDest.value = await window.pywebview.api.get_downloads_folder()
      } catch(e) { serverDest.value = '' }
      showServerModal.value = true
    }

    const pickServerFolder = async () => {
      try {
        await window.__apiReady
        const folder = await window.pywebview.api.pick_folder()
        if (folder) serverDest.value = folder
      } catch(e) {}
    }

    const startServerDownload = async () => {
      serverModalStep.value = 3
      serverProgress.value = SERVER_PACK_STEPS.map(l => ({ label: l, state: 'idle', detail: '' }))
      serverSummary.value = null
      try {
        await window.__apiReady
        await window.pywebview.api.download_server_pack({
          repo_id: browseRepoId.value,
          pack_name: selectedPack.value,
          version: selectedVersionObj.value.version,
          dest_folder: serverDest.value,
          as_zip: serverAsZip.value,
          include_config: serverIncludeConfig.value,
        })
      } catch(e) {
        serverSummary.value = { tone: 'error', text: String(e) }
      }
    }

    const confirmConflictInstall = async () => {
      showConflictModal.value = false
      const skip = conflictGroups.value.flatMap(g => g.files.filter(f => f.keep).map(f => f.path))
      openClientModReview({ ...conflictInstallParams.value, skip_files: skip })
    }

    const modDiff = computed(() => {
      if (!selectedVersionObj.value || !packVersions.value.length) return { added: [], removed: [] }
      const idx = packVersions.value.findIndex(v => v.version === selectedVersionObj.value.version)
      const curMeta = selectedVersionObj.value.metadata || {}
      const curModList = curMeta.mods || []
      const curMods = new Set(curModList.map(m => m.file))
      const removed = curMeta.removed_mods || []
      let addedFiles = []
      const isFirst = idx === packVersions.value.length - 1
      if (isFirst) {
        // First version — all mods are "added"
        addedFiles = curModList.map(m => m.file)
      } else {
        const prevMeta = packVersions.value[idx + 1].metadata || {}
        const prevMods = new Set((prevMeta.mods || []).map(m => m.file))
        addedFiles = [...curMods].filter(f => !prevMods.has(f))
      }
      // Enrich added with side info from mods list
      const sideMap = {}
      curModList.forEach(m => { sideMap[m.file] = m.side || 'required' })
      const added = addedFiles.map(f => ({ file: f, side: sideMap[f] || 'required' }))
      return { added, removed }
    })

    watch(browseRepoId, loadPacks)

    const stepIconState = (state) => {
      if (state === 'ok') return 'done'
      if (state === 'running') return 'run'
      if (state === 'error') return 'err'
      return 'idle'
    }

    const packAbbr = name => name.slice(0, 2).toUpperCase()
    const PACK_COLORS = ['#8a5cf6','#6fae8a','#c9a25b','#5b8ec9','#c97070','#8a7fc9']
    const packColor = (name) => PACK_COLORS[name.charCodeAt(0) % PACK_COLORS.length]

    // Progress handler — routes to publish or install steps based on active tab
    const _baseHandler = window.__onProgress
    window.__onProgress = (event) => {
      if (_baseHandler) _baseHandler(event)

      if (event.type === 'server_pack') {
        if (event.step !== undefined && serverProgress.value[event.step]) {
          serverProgress.value[event.step].state = event.state === 'ok' ? 'done' : event.state === 'error' ? 'err' : 'run'
          serverProgress.value[event.step].detail = event.detail || ''
        }
        return
      }
      if (event.type === 'server_pack_summary') {
        serverSummary.value = { tone: event.tone, text: event.text }
        return
      }

      const flow = event.flow
      if (flow === 'install') {
        routeToModal(installModal, event)
        if (event.type === 'summary' && event.tone === 'ok') loadInstalledInstances()
        return
      }
      if (flow === 'publish') {
        routeToModal(publishModal, event)
        return
      }
    }

    onMounted(async () => {
      await loadRepos()
      await loadInstances()
      await loadInstalledInstances()
      if (repos.value.length) {
        browseRepoId.value = repos.value[0].id
        publishForm.value.repo_id = repos.value[0].id
        await loadExistingPacks()
      }
    })

    return {
      tab, icon,
      installModal, publishModal, updateModal, routeToModal, ActionModal,
      openInstallModal, confirmInstall, retryInstall, closeInstallModal,
      // repos
      repos, reposLoading, selectedRepo, repoForm, repoSaving, repoError, repoSuccess,
      testResult, testLoading,
      loadRepos, selectRepo, newRepo, saveRepo, deleteRepo, testConnection,
      // publish
      allInstances, publishForm, modFiles, loadModFiles, publishSteps, publishSummary, publishTone, publishing,
      existingPacks, packNameIsNew,
      publish, clearPublish,
      // browse
      browseRepoId, packs, packsLoading, selectedPack,
      packVersions, versionsLoading, selectedVersionObj,
      showConflictModal, conflictGroups, conflictInstallParams, confirmConflictInstall, trackOnInstall,
      showClientModModal, clientModList, clientModAllSelected,
      toggleAllClientMods, confirmClientModInstall,
      showServerModal, serverModalStep, serverDest, serverAsZip, serverIncludeConfig,
      serverProgress, serverSummary, SERVER_PACK_STEPS,
      openServerModal, pickServerFolder, startServerDownload,
      installMode, installInstanceName, installExistingInstance,
      installSteps, installSummary, INSTALL_STEPS,
      installing, installPack, selectPack, selectVersion, checkAndInstall, modDiff,
      stepIconState, packAbbr, packColor, PUBLISH_STEPS,
      // instances tab
      installedInstances, instancesLoading, instanceProgress, loadInstalledInstances,
      untrackInstance, installUpdate, removeInstalledRecord, reinstallInstance, toggleHook,
    }
  },
  template: `
    <main class="page-wrap">
      <div class="page-header">
        <div>
          <div class="kicker">Registry</div>
          <h1>Pack Registry</h1>
        </div>
        <div class="sub-tabs">
          <button class="sub-tab" :class="{ active: tab === 'repos' }" @click="tab = 'repos'">Repos</button>
          <button class="sub-tab" :class="{ active: tab === 'publish' }" @click="tab = 'publish'">Publish</button>
          <button class="sub-tab" :class="{ active: tab === 'browse' }" @click="tab = 'browse'">Browse</button>
          <button class="sub-tab" :class="{ active: tab === 'instances' }" @click="tab = 'instances'; loadInstalledInstances()">Instances</button>
          <button class="sub-tab" :class="{ active: tab === 'servers' }" @click="tab = 'servers'">Servers</button>
        </div>
      </div>

      <!-- ─── REPOS TAB ─────────────────────────────────────────────────────── -->
      <template v-if="tab === 'repos'">
        <div style="display:grid;grid-template-columns:300px 1fr;gap:16px;align-items:start">
          <!-- Repo list -->
          <div class="card" style="overflow:hidden">
            <div class="card-header" style="align-items:center">
              <div class="card-title" style="margin-top:0">Repos</div>
              <button class="btn btn-primary btn-sm flex items-center gap-6" @click="newRepo">
                <span v-html="icon('plus',12)"></span> Add
              </button>
            </div>
            <div v-if="reposLoading" class="loading">Loading…</div>
            <div v-else-if="!repos.length" class="loading fs-12">No repos configured</div>
            <div v-for="r in repos" :key="r.id"
              @click="selectRepo(r)"
              style="display:flex;align-items:center;gap:12px;padding:11px 14px;cursor:pointer;border-bottom:1px solid var(--line);transition:background .1s"
              :style="selectedRepo && selectedRepo.id === r.id ? 'background:var(--bg-2)' : ''">
              <span class="dot dot-ok"></span>
              <div style="flex:1;min-width:0">
                <div class="fw-500 text-0 text-ellipsis">{{ r.name }}</div>
                <div class="mono fs-12 text-3 mt-4 text-ellipsis">{{ r.project_url || r.base_url }}</div>
              </div>
            </div>
          </div>

          <!-- Repo form -->
          <div class="card">
            <div class="card-header">
              <div class="card-title" style="margin-top:0">{{ selectedRepo ? 'Edit Repo' : 'New Repo' }}</div>
              <div class="flex items-center gap-8" v-if="selectedRepo">
                <button class="btn btn-ghost btn-sm" style="color:var(--err);border-color:var(--err)" @click="deleteRepo(selectedRepo.id)">Delete</button>
              </div>
            </div>
            <div class="card-body" style="display:flex;flex-direction:column;gap:14px">
              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Name</div>
                <input v-model="repoForm.name" placeholder="My Pack Repo" class="input">
              </div>
              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">GitLab URL</div>
                <input v-model="repoForm.url" placeholder="https://gitlab.com/user/repo" class="input input-mono">
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">
                    Personal Access Token
                    <span class="text-3 fs-11" style="font-weight:400; margin-left:6px">for browsing private repos</span>
                  </div>
                  <input v-model="repoForm.pat_token" type="password" placeholder="glpat-… (leave empty if public)" class="input input-mono">
                </div>
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">
                    Deploy Token
                    <span class="text-3 fs-11" style="font-weight:400; margin-left:6px">for publishing packs</span>
                  </div>
                  <input v-model="repoForm.deploy_token" type="password" placeholder="gldt-… (leave empty for read-only)" class="input input-mono">
                </div>
              </div>

              <!-- Test result -->
              <div v-if="testResult" style="padding:8px 12px;border-radius:6px"
                :style="testResult.ok ? 'background:var(--ok-soft);color:var(--ok)' : 'background:var(--err-soft);color:var(--err)'">
                <span class="fs-12 fw-500">{{ testResult.msg }}</span>
              </div>
              <div v-if="repoError" style="padding:8px 12px;border-radius:6px;background:var(--err-soft);color:var(--err)">
                <span class="fs-12">{{ repoError }}</span>
              </div>
              <div v-if="repoSuccess" style="padding:8px 12px;border-radius:6px;background:var(--ok-soft);color:var(--ok)">
                <span class="fs-12 fw-500">Saved successfully</span>
              </div>

              <div class="flex items-center gap-8" style="justify-content:space-between;padding-top:4px">
                <button class="btn btn-quiet btn-sm flex items-center gap-6" :disabled="testLoading" @click="testConnection">
                  <span :class="testLoading ? 'spin' : ''" v-html="icon('refresh',12)"></span>
                  {{ testLoading ? 'Testing…' : 'Test connection' }}
                </button>
                <div class="flex items-center gap-8">
                  <button class="btn btn-ghost btn-sm" @click="newRepo">Cancel</button>
                  <button class="btn btn-primary btn-sm" :disabled="repoSaving" @click="saveRepo">
                    {{ repoSaving ? 'Saving…' : 'Save' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ─── PUBLISH TAB ────────────────────────────────────────────────────── -->
      <template v-else-if="tab === 'publish'">
        <div style="display:grid;grid-template-columns:1fr 340px;gap:16px;align-items:start">
          <!-- Publish form -->
          <div class="card">
            <div class="card-header">
              <div class="card-title" style="margin-top:0">Publish Pack</div>
            </div>
            <div class="card-body" style="display:flex;flex-direction:column;gap:16px">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Repo</div>
                  <select v-model="publishForm.repo_id" class="input">
                    <option v-for="r in repos" :key="r.id" :value="r.id">{{ r.name }}</option>
                  </select>
                </div>
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Instance (template)</div>
                  <select v-model="publishForm.instance_name" class="input">
                    <option v-for="i in allInstances" :key="i" :value="i">{{ i }}</option>
                  </select>
                </div>
              </div>

              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:6px;display:flex;align-items:center;justify-content:space-between">
                    Pack Name
                    <button class="btn btn-ghost btn-sm" style="font-size:11px;padding:2px 8px"
                      @click="packNameIsNew = !packNameIsNew; publishForm.pack_name = ''">
                      {{ packNameIsNew ? '← Existing' : '+ New' }}
                    </button>
                  </div>
                  <input v-if="packNameIsNew" v-model="publishForm.pack_name" placeholder="New pack name" class="input" autofocus>
                  <select v-else v-model="publishForm.pack_name" class="input">
                    <option value="" disabled>Select pack…</option>
                    <option v-for="p in existingPacks" :key="p" :value="p">{{ p }}</option>
                  </select>
                </div>
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Version</div>
                  <input v-model="publishForm.version" placeholder="e.g. 1.0.0" class="input input-mono">
                </div>
              </div>

              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Description</div>
                <input v-model="publishForm.description" placeholder="Short description…" class="input">
              </div>

              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Changenotes</div>
                <textarea v-model="publishForm.changenotes" placeholder="What changed in this version?" class="input" rows="3" style="resize:vertical;width:100%"></textarea>
              </div>

              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">MC Version</div>
                  <input v-model="publishForm.mc_version" placeholder="1.20.1" class="input input-mono">
                </div>
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Loader</div>
                  <input v-model="publishForm.loader" placeholder="fabric" class="input input-mono">
                </div>
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">
                    Loader Version
                    <span v-if="!publishForm.loader_version" style="color:var(--err);margin-left:4px" title="Loader version missing — Prism will show red X">!</span>
                  </div>
                  <input v-model="publishForm.loader_version" placeholder="auto-filled" class="input input-mono">
                </div>
              </div>

              <!-- Include checkboxes -->
              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:10px">Include</div>
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
                  <label v-for="(val, key) in publishForm.categories" :key="key"
                    style="display:flex;align-items:center;gap:8px;cursor:pointer;padding:8px 10px;background:var(--bg-0);border:1px solid var(--line);border-radius:6px">
                    <div :class="['checkbox-box', val ? 'on' : 'off']"
                      @click.prevent="publishForm.categories[key] = !val">
                      <span v-if="val" v-html="icon('check', 10)"></span>
                    </div>
                    <span class="fs-13 text-0" style="text-transform:capitalize">{{ key }}</span>
                  </label>
                </div>
              </div>

              <!-- Mod tags table -->
              <template v-if="publishForm.categories.mods && modFiles.length">
                <div>
                  <div class="fs-12 text-2 fw-500" style="margin-bottom:8px">Mod Side Tags</div>
                  <div style="overflow-x:auto">
                    <table class="data-table">
                      <thead>
                        <tr>
                          <th style="text-align:left">File</th>
                          <th style="text-align:center">Side</th>
                          <th style="text-align:center">Exclude</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="mod in modFiles" :key="mod.file" :style="mod.excluded ? 'opacity:0.4' : ''">
                          <td class="mono fs-12">{{ mod.file }}</td>
                          <td style="text-align:center">
                            <select v-model="mod.side" class="input" :disabled="mod.excluded" style="width:110px;padding:3px 6px">
                              <option value="required">required</option>
                              <option value="client">client</option>
                              <option value="server">server</option>
                            </select>
                          </td>
                          <td style="text-align:center">
                            <input type="checkbox" v-model="mod.excluded" style="width:14px;height:14px;cursor:pointer">
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <!-- Progress panel -->
          <div style="display:flex;flex-direction:column;gap:12px">
            <div class="card">
              <div class="card-header">
                <div class="card-title" style="margin-top:0">Progress</div>
              </div>
              <div class="card-body" style="padding:8px">
                <div v-for="(step, i) in publishSteps" :key="i" class="progress-step">
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

                <div v-if="publishSummary" style="margin-top:8px;padding:8px 10px;border-radius:6px"
                  :style="publishTone==='ok' ? 'background:var(--ok-soft);color:var(--ok)' : 'background:var(--err-soft);color:var(--err)'">
                  <span class="fs-12 fw-500">{{ publishSummary }}</span>
                </div>
              </div>
              <div style="padding:12px 16px;border-top:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:8px">
                <button class="btn btn-ghost btn-sm flex items-center gap-6">
                  <span v-html="icon('external', 12)"></span> View on GitLab
                </button>
                <button class="btn btn-primary btn-sm flex items-center gap-6"
                  :disabled="publishing || !publishForm.repo_id || !publishForm.instance_name || !publishForm.pack_name || !publishForm.version"
                  @click="publish">
                  <span :class="publishing ? 'spin' : ''" v-html="icon('download', 12)"></span>
                  {{ publishing ? 'Publishing…' : 'Publish pack' }}
                </button>
              </div>
            </div>

            <!-- Summary tags -->
            <div v-if="publishSummary" class="card">
              <div class="card-body" style="display:flex;flex-wrap:wrap;gap:6px">
                <span class="tag">{{ publishForm.pack_name || publishForm.instance_name }}</span>
                <span class="tag" v-if="publishForm.version">v{{ publishForm.version }}</span>
                <span v-for="(val, key) in publishForm.categories" :key="key" v-if="val" class="tag">{{ key }}</span>
                <span v-if="publishForm.mc_version" class="tag">{{ publishForm.mc_version }}</span>
                <span v-if="publishForm.loader" class="tag">{{ publishForm.loader }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ─── BROWSE TAB ─────────────────────────────────────────────────────── -->
      <template v-else-if="tab === 'browse'">
        <!-- Repo selector row -->
        <div class="flex items-center gap-10" style="flex-wrap:wrap;margin-bottom:16px">
          <span class="fs-12 text-2 fw-500">Repository:</span>
          <div class="sub-tabs">
            <button v-for="r in repos" :key="r.id"
              class="sub-tab" :class="{ active: browseRepoId === r.id }"
              @click="browseRepoId = r.id">{{ r.name }}</button>
          </div>
          <span v-if="!repos.length" class="fs-12 text-3">No repos configured</span>
        </div>

        <div v-if="repos.length" style="display:grid;grid-template-columns:240px 1fr;gap:16px;align-items:start">
          <!-- Left: pack list -->
          <div class="card" style="overflow:hidden">
            <div class="card-header" style="align-items:center">
              <div class="card-title" style="margin-top:0">Packs</div>
              <span class="text-3 fs-12">{{ packs.length }}</span>
            </div>
            <div v-if="packsLoading" class="loading">Loading…</div>
            <div v-else-if="!packs.length" class="loading fs-12">No packs found</div>
            <div v-for="name in packs" :key="name"
              @click="selectPack(name)"
              style="display:flex;align-items:center;gap:12px;padding:11px 14px;cursor:pointer;border-bottom:1px solid var(--line);transition:background .1s"
              :style="selectedPack === name ? 'background:var(--bg-2)' : ''">
              <div style="width:30px;height:30px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:monospace;font-size:11px;font-weight:600;color:#fff;flex:none"
                :style="'background:' + packColor(name)">
                {{ packAbbr(name) }}
              </div>
              <div class="fw-500 text-0 text-ellipsis">{{ name }}</div>
            </div>
          </div>

          <!-- Right: pack detail -->
          <div v-if="!selectedPack" class="card">
            <div class="card-body loading fs-13 text-3" style="padding:48px;text-align:center">Select a pack to view details.</div>
          </div>
          <template v-else>
            <div style="display:flex;flex-direction:column;gap:16px">

              <!-- Version selector -->
              <div class="card">
                <div class="card-header"><div class="kicker">Version</div></div>
                <div class="card-body" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
                  <div v-if="versionsLoading" class="loading fs-13">Loading…</div>
                  <template v-else>
                    <select class="input" style="width:180px" @change="e => selectVersion(packVersions.find(v => v.version === e.target.value))">
                      <option v-for="v in packVersions" :key="v.version" :value="v.version">{{ v.version }}</option>
                    </select>
                    <template v-if="selectedVersionObj">
                      <span class="mono fs-12 text-3">{{ selectedVersionObj.metadata?.mc_version }}</span>
                      <span class="mono fs-12 text-3">{{ selectedVersionObj.metadata?.loader }}</span>
                    </template>
                  </template>
                </div>
              </div>

              <!-- Changenotes + mod diff -->
              <div v-if="selectedVersionObj" class="card">
                <div class="card-header"><div class="kicker">Changenotes</div></div>
                <div class="card-body">
                  <div v-if="selectedVersionObj.metadata?.changenotes" class="fs-13 text-1" style="white-space:pre-wrap;margin-bottom:12px">{{ selectedVersionObj.metadata.changenotes }}</div>
                  <div v-else class="fs-13 text-3">No changenotes for this version.</div>
                  <div v-if="modDiff.added.length || modDiff.removed.length" style="margin-top:12px;display:flex;flex-direction:column;gap:10px">
                    <template v-if="modDiff.added.length">
                      <template v-for="side in ['required','client','server']" :key="side">
                        <div v-if="modDiff.added.filter(m => m.side === side).length">
                          <div class="fs-12 text-3 mb-4">
                            {{ side === 'required' ? 'Added' : 'Added ' + side[0].toUpperCase() + side.slice(1) + '-side' }}
                          </div>
                          <div v-for="m in modDiff.added.filter(x => x.side === side)" :key="m.file"
                            class="mono fs-12" style="color:var(--ok);padding:1px 0">
                            + {{ m.file.replace(/\.jar$/i, '') }}
                          </div>
                        </div>
                      </template>
                    </template>
                    <div v-if="modDiff.removed.length">
                      <div class="fs-12 text-3 mb-4">Removed</div>
                      <div v-for="f in modDiff.removed" :key="f" class="mono fs-12 text-err" style="padding:1px 0">
                        − {{ f.replace(/\.jar$/i, '') }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Install section -->
              <div class="card">
                <div class="card-header"><div class="kicker">Install</div></div>
                <div class="card-body" style="display:flex;flex-direction:column;gap:14px">

                  <!-- Mode toggle -->
                  <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:space-between">
                    <div class="sub-tabs">
                      <button class="sub-tab" :class="{ active: installMode === 'new' }" @click="installMode = 'new'">Create new instance</button>
                      <button class="sub-tab" :class="{ active: installMode === 'existing' }" @click="installMode = 'existing'">Install to existing</button>
                    </div>
                    <button class="btn btn-ghost btn-sm flex items-center gap-6" @click="openServerModal">
                      <span v-html="icon('download', 12)"></span> Download server pack
                    </button>
                  </div>

                  <!-- New instance name -->
                  <div v-if="installMode === 'new'" style="display:flex;align-items:center;gap:8px">
                    <label class="fs-13 text-2" style="width:120px">Instance name</label>
                    <input v-model="installInstanceName" class="input" style="flex:1" placeholder="Instance name">
                  </div>

                  <!-- Existing instance dropdown -->
                  <div v-if="installMode === 'existing'" style="display:flex;align-items:center;gap:8px">
                    <label class="fs-13 text-2" style="width:120px">Instance</label>
                    <select v-model="installExistingInstance" class="input" style="flex:1">
                      <option value="">Select instance…</option>
                      <option v-for="inst in allInstances" :key="inst" :value="inst">{{ inst }}</option>
                    </select>
                  </div>

                  <!-- Track checkbox -->
                  <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;color:var(--text-1)">
                    <input type="checkbox" v-model="trackOnInstall" style="width:14px;height:14px">
                    Track for updates (auto-update prompt on game launch)
                  </label>

                  <button class="btn btn-primary btn-sm flex items-center gap-8" :disabled="installing" @click="checkAndInstall">
                    <span :class="installing ? 'spin' : ''" v-html="icon('download', 13)"></span>
                    {{ installing ? 'Installing…' : 'Install' }}
                  </button>
                </div>
              </div>

              <!-- Mod list -->
              <div v-if="selectedVersionObj?.metadata?.mods?.length" class="card">
                <div class="card-header"><div class="kicker">Mods</div></div>
                <div style="overflow-x:auto">
                  <table class="data-table">
                    <thead><tr><th style="text-align:left">File</th><th style="text-align:center">Side</th></tr></thead>
                    <tbody>
                      <tr v-for="mod in selectedVersionObj.metadata.mods" :key="mod.file">
                        <td class="mono fs-12">{{ mod.file }}</td>
                        <td style="text-align:center">
                          <span class="tag" :style="mod.side === 'client' ? 'color:var(--accent)' : mod.side === 'server' ? 'color:var(--ok)' : ''">{{ mod.side }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          </template>
        </div>

        <div v-else class="card">
          <div class="card-body" style="text-align:center;padding:48px">
            <div class="text-2 fs-13">No repos configured. Add a repo in the Repos tab.</div>
          </div>
        </div>
      </template>

      <!-- ─── INSTANCES TAB ───────────────────────────────────────────────────── -->
      <template v-else-if="tab === 'instances'">
        <div class="card">
          <div class="card-header" style="align-items:center">
            <div>
              <div class="kicker">Installed</div>
              <div class="card-title" style="margin-top:0">Pack Registry Instances <span class="text-3 fw-500 fs-13">· {{ installedInstances.length }}</span></div>
            </div>
            <button class="btn btn-ghost btn-sm flex items-center gap-6" @click="loadInstalledInstances">
              <span v-html="icon('refresh', 12)"></span> Refresh
            </button>
          </div>
          <div v-if="instancesLoading" class="loading">Loading…</div>
          <div v-else-if="!installedInstances.length" class="loading fs-13 text-3" style="padding:48px;text-align:center">No instances installed from the pack registry yet.</div>
          <div v-else style="overflow-x:auto">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="text-align:left">Instance</th>
                  <th style="text-align:left">Pack</th>
                  <th style="text-align:left">Version</th>
                  <th style="text-align:left">Repo</th>
                  <th style="text-align:center">Tracked</th>
                  <th style="text-align:center">Auto Update</th>
                  <th style="text-align:right">Actions</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="inst in installedInstances" :key="inst.instance_name">
                <tr :style="!inst.prism_exists ? 'opacity:0.6' : ''">
                  <td>
                    <div class="fw-500 text-0">{{ inst.instance_name }}</div>
                    <div v-if="!inst.prism_exists" class="fs-11 text-3" style="color:var(--err);margin-top:2px">Not found in Prism</div>
                  </td>
                  <td><span class="mono fs-12">{{ inst.pack_name }}</span></td>
                  <td><span class="mono fs-12 text-2">{{ inst.installed_version }}</span></td>
                  <td><span class="fs-12 text-2">{{ inst.repo_name || inst.repo_id }}</span></td>
                  <td style="text-align:center">
                    <span v-if="inst.tracked" class="tag" style="color:var(--ok)">tracked</span>
                    <span v-else class="tag text-3">—</span>
                  </td>
                  <td style="text-align:center">
                    <div style="display:flex;justify-content:center" :title="inst.prism_exists ? '' : 'Instance not found in Prism'">
                      <div :class="['toggle-track', inst.hook_enabled ? 'on' : 'off', !inst.prism_exists ? 'disabled' : '']"
                        @click="inst.prism_exists && toggleHook(inst)">
                        <div class="toggle-thumb"></div>
                      </div>
                    </div>
                  </td>
                  <td style="text-align:right">
                    <div class="flex items-center gap-6" style="justify-content:flex-end">
                      <template v-if="!inst.prism_exists">
                        <button class="btn btn-primary btn-sm flex items-center gap-4" style="font-size:11px" @click="reinstallInstance(inst)">
                          <span v-html="icon('download', 11)"></span> Reinstall
                        </button>
                        <button class="btn btn-ghost btn-sm" style="font-size:11px;color:var(--err);border-color:var(--err)" @click="removeInstalledRecord(inst.instance_name)">Remove</button>
                      </template>
                      <template v-else>
                        <button v-if="inst.has_update" class="btn btn-primary btn-sm flex items-center gap-4" style="font-size:11px" @click="installUpdate(inst)">
                          <span v-html="icon('download', 11)"></span> {{ inst.latest_version }}
                        </button>
                        <span v-else class="tag text-3 fs-11">up to date</span>
                        <button v-if="inst.tracked" class="btn btn-ghost btn-sm" style="font-size:11px" @click="untrackInstance(inst.instance_name)">Untrack</button>
                      </template>
                    </div>
                  </td>
                </tr>
                <!-- Per-instance progress row -->
                <tr v-if="instanceProgress[inst.instance_name]">
                  <td colspan="7" style="padding:0 16px 12px;background:var(--bg-0)">
                    <div style="display:flex;flex-direction:column;gap:4px;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--bg-1)">
                      <div v-for="(s, i) in instanceProgress[inst.instance_name].steps" :key="i"
                        style="display:flex;align-items:center;gap:8px">
                        <span class="progress-step-icon" :class="s.state">
                          <span v-if="s.state==='done'" v-html="icon('check',10)"></span>
                          <span v-else-if="s.state==='run'" class="spin" v-html="icon('spin',10)"></span>
                          <span v-else-if="s.state==='err'" v-html="icon('x',10)"></span>
                        </span>
                        <span class="fs-12 text-0">{{ s.label }}</span>
                        <span v-if="s.detail" class="mono fs-11 text-3">{{ s.detail }}</span>
                      </div>
                      <div v-if="instanceProgress[inst.instance_name].summary"
                        style="margin-top:6px;padding:6px 8px;border-radius:4px;font-size:12px;font-weight:500"
                        :style="instanceProgress[inst.instance_name].summary.tone==='ok' ? 'background:var(--ok-soft);color:var(--ok)' : 'background:var(--err-soft);color:var(--err)'">
                        {{ instanceProgress[inst.instance_name].summary.text }}
                        <button @click="delete instanceProgress[inst.instance_name]"
                          style="margin-left:10px;background:none;border:none;cursor:pointer;color:inherit;font-size:11px;opacity:.7">✕</button>
                      </div>
                    </div>
                  </td>
                </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <!-- ─── SERVERS TAB ──────────────────────────────────────────────────────── -->
      <template v-else-if="tab === 'servers'">
        <div class="card">
          <div class="card-body" style="text-align:center;padding:64px 48px">
            <div v-html="icon('link', 32)" style="color:var(--text-3);margin-bottom:16px;display:flex;justify-content:center"></div>
            <div class="fw-500 text-0 fs-14" style="margin-bottom:8px">Server Packs</div>
            <div class="fs-13 text-3">Coming soon — server middleware integration for deploying and syncing packs directly to servers.</div>
          </div>
        </div>
      </template>

      <!-- ─── INSTALL ACTION MODAL ──────────────────────────────────────────────── -->
      <action-modal
        :show="installModal.show"
        :title="installModal.title"
        :summary="installModal.summary"
        :deletions="installModal.deletions"
        :steps="installModal.steps"
        :logs="installModal.logs"
        :phase="installModal.phase"
        :done="installModal.done"
        :error="installModal.error"
        @confirm="confirmInstall"
        @cancel="closeInstallModal"
        @retry="retryInstall"
      />

      <!-- ─── CONFLICT MODAL ───────────────────────────────────────────────────── -->
      <teleport to="body">
        <div v-if="showConflictModal"
          style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px">
          <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:640px;max-height:80vh;display:flex;flex-direction:column;overflow:hidden">

            <!-- Header -->
            <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line);flex:none">
              <div class="fw-600 text-0" style="font-size:15px;margin-bottom:4px">File conflicts detected</div>
              <div class="fs-13 text-2">These files already exist in the instance. Choose which ones to keep (skip overwriting).</div>
            </div>

            <!-- Grouped file list -->
            <div style="overflow-y:auto;flex:1;padding:16px 24px;display:flex;flex-direction:column;gap:16px">
              <div v-for="group in conflictGroups" :key="group.folder">
                <!-- Group header with select-all toggle -->
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
                  <input type="checkbox"
                    :checked="group.allKeep"
                    @change="group.toggleAll($event.target.checked)"
                    style="width:14px;height:14px;cursor:pointer">
                  <span class="fw-500 text-0 fs-13" style="text-transform:uppercase;letter-spacing:.04em">{{ group.folder }}</span>
                  <span class="fs-12 text-3">{{ group.files.length }} file{{ group.files.length !== 1 ? 's' : '' }}</span>
                </div>
                <!-- Files (collapsed when all kept) -->
                <div v-if="!group.allKeep" style="display:flex;flex-direction:column;gap:2px;padding-left:24px">
                  <label v-for="file in group.files" :key="file.path"
                    style="display:flex;align-items:center;gap:8px;cursor:pointer;padding:4px 6px;border-radius:4px"
                    :style="file.keep ? 'background:var(--bg-2)' : ''">
                    <input type="checkbox" v-model="file.keep" style="width:13px;height:13px;cursor:pointer">
                    <span class="mono fs-12" :class="file.keep ? 'text-3' : 'text-1'">{{ file.path }}</span>
                    <span v-if="file.keep" class="fs-11 text-3" style="margin-left:auto">keep</span>
                    <span v-else class="fs-11" style="margin-left:auto;color:var(--accent)">overwrite</span>
                  </label>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <div style="padding:16px 24px;border-top:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;flex:none">
              <div class="fs-12 text-3">
                {{ conflictGroups.flatMap(g => g.files).filter(f => !f.keep).length }} files will be overwritten,
                {{ conflictGroups.flatMap(g => g.files).filter(f => f.keep).length }} kept
              </div>
              <div style="display:flex;gap:8px">
                <button class="btn btn-ghost btn-sm" @click="showConflictModal = false">Cancel</button>
                <button class="btn btn-primary btn-sm" @click="confirmConflictInstall">Install</button>
              </div>
            </div>
          </div>
        </div>
      </teleport>

      <!-- ─── CLIENT MOD REVIEW MODAL ──────────────────────────────────────────── -->
      <teleport to="body">
        <div v-if="showClientModModal"
          style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px">
          <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:560px;max-height:80vh;display:flex;flex-direction:column;overflow:hidden">

            <!-- Header -->
            <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line);flex:none">
              <div class="fw-600 text-0" style="font-size:15px;margin-bottom:4px">Client-only mods</div>
              <div class="fs-13 text-2">These mods are client-side only. Deselect any you don't want installed.</div>
            </div>

            <!-- List -->
            <div style="overflow-y:auto;flex:1;padding:16px 24px">
              <table class="data-table">
                <thead>
                  <tr>
                    <th style="width:32px">
                      <input type="checkbox"
                        :checked="clientModAllSelected"
                        @change="toggleAllClientMods($event.target.checked)"
                        style="width:13px;height:13px;cursor:pointer">
                    </th>
                    <th style="text-align:left">Mod</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="mod in clientModList" :key="mod.file" :style="!mod.include ? 'opacity:0.45' : ''">
                    <td>
                      <input type="checkbox" v-model="mod.include" style="width:13px;height:13px;cursor:pointer">
                    </td>
                    <td class="mono fs-12">{{ mod.name }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Footer -->
            <div style="padding:16px 24px;border-top:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;flex:none">
              <div class="fs-12 text-3">
                {{ clientModList.filter(m => m.include).length }} of {{ clientModList.length }} selected
              </div>
              <div style="display:flex;gap:8px">
                <button class="btn btn-ghost btn-sm" @click="showClientModModal = false">Cancel</button>
                <button class="btn btn-primary btn-sm" @click="confirmClientModInstall">Install</button>
              </div>
            </div>

          </div>
        </div>
      </teleport>

      <!-- ─── SERVER DOWNLOAD MODAL ─────────────────────────────────────────────── -->
      <teleport to="body">
        <div v-if="showServerModal"
          style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px">
          <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:12px;width:100%;max-width:520px;display:flex;flex-direction:column;overflow:hidden">

            <!-- Header -->
            <div style="padding:20px 24px 16px;border-bottom:1px solid var(--line)">
              <div class="fw-600 text-0" style="font-size:15px;margin-bottom:4px">Download server pack</div>
              <div class="fs-12 text-3">
                <span v-if="serverModalStep < 3">Step {{ serverModalStep }} of 2 — {{ serverModalStep === 1 ? 'Destination' : 'Content' }}</span>
                <span v-else>Downloading…</span>
              </div>
            </div>

            <!-- Step 1: Destination -->
            <div v-if="serverModalStep === 1" style="padding:20px 24px;display:flex;flex-direction:column;gap:16px">
              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:6px">Save to folder</div>
                <div style="display:flex;gap:8px">
                  <input v-model="serverDest" class="input input-mono" style="flex:1" placeholder="Choose folder…">
                  <button class="btn btn-ghost btn-sm" @click="pickServerFolder">Browse…</button>
                </div>
              </div>
              <div>
                <div class="fs-12 text-2 fw-500" style="margin-bottom:8px">Format</div>
                <div class="sub-tabs">
                  <button class="sub-tab" :class="{ active: serverAsZip }" @click="serverAsZip = true">Save as zip</button>
                  <button class="sub-tab" :class="{ active: !serverAsZip }" @click="serverAsZip = false">Extract to folder</button>
                </div>
              </div>
            </div>

            <!-- Step 2: Content -->
            <div v-if="serverModalStep === 2" style="padding:20px 24px;display:flex;flex-direction:column;gap:14px">
              <div style="padding:10px 12px;background:var(--bg-0);border:1px solid var(--line);border-radius:6px">
                <div class="fs-12 fw-500 text-0">Required + server-side mods</div>
                <div class="fs-12 text-3 mt-4">Always included</div>
              </div>
              <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px 12px;background:var(--bg-0);border:1px solid var(--line);border-radius:6px">
                <input type="checkbox" v-model="serverIncludeConfig" style="width:14px;height:14px;cursor:pointer">
                <div>
                  <div class="fs-12 fw-500 text-0">Config files</div>
                  <div class="fs-12 text-3 mt-4">Include the config/ folder</div>
                </div>
              </label>
              <div class="fs-12 text-3" style="padding:0 2px">
                Saves, resource packs, and shader packs are excluded from server packs.
              </div>
            </div>

            <!-- Step 3: Progress -->
            <div v-if="serverModalStep === 3" style="padding:16px 24px;display:flex;flex-direction:column;gap:4px">
              <div v-for="(s, i) in serverProgress" :key="i" class="progress-step">
                <span class="progress-step-icon" :class="s.state">
                  <span v-if="s.state==='done'" v-html="icon('check',10)"></span>
                  <span v-else-if="s.state==='run'" class="spin" v-html="icon('spin',10)"></span>
                  <span v-else-if="s.state==='err'" v-html="icon('x',10)"></span>
                </span>
                <span class="fs-13 text-0">{{ s.label }}</span>
                <span v-if="s.detail" class="mono fs-11 text-3" style="margin-left:auto">{{ s.detail }}</span>
              </div>
              <div v-if="serverSummary" style="margin-top:10px;padding:10px 12px;border-radius:6px;font-size:12px;font-weight:500;word-break:break-all"
                :style="serverSummary.tone==='ok' ? 'background:var(--ok-soft);color:var(--ok)' : 'background:var(--err-soft);color:var(--err)'">
                {{ serverSummary.tone === 'ok' ? 'Saved to: ' : '' }}{{ serverSummary.text }}
              </div>
            </div>

            <!-- Footer -->
            <div style="padding:16px 24px;border-top:1px solid var(--line);display:flex;justify-content:space-between;align-items:center">
              <div>
                <button v-if="serverModalStep === 2" class="btn btn-ghost btn-sm" @click="serverModalStep = 1">← Back</button>
              </div>
              <div style="display:flex;gap:8px">
                <button v-if="serverModalStep < 3" class="btn btn-ghost btn-sm" @click="showServerModal = false">Cancel</button>
                <button v-if="serverModalStep === 1" class="btn btn-primary btn-sm" :disabled="!serverDest" @click="serverModalStep = 2">Next →</button>
                <button v-if="serverModalStep === 2" class="btn btn-primary btn-sm" @click="startServerDownload">Confirm &amp; Download</button>
                <button v-if="serverModalStep === 3" class="btn btn-ghost btn-sm" :disabled="!serverSummary" @click="showServerModal = false">
                  {{ serverSummary ? 'Close' : 'Cancel' }}
                </button>
              </div>
            </div>

          </div>
        </div>
      </teleport>

    </main>
  `
}
