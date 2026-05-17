# Pack Registry v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign Pack Registry so one repo holds multiple named packs, each with user-supplied versioning, changenotes, mod side-tagging, publisher-declared mod removals, conflict-detected installs, and tracked-instance auto-update on game launch.

**Architecture:** Each named pack maps to one GitLab Generic Package (slug = pack name lowercased, spaces→hyphens). The `metadata.json` sidecar gains `pack_name`, `version`, `changenotes`, `mods[]`, and `removed_mods[]`. Tracked instances are stored in `state.json`; `--startup` opens a small PyWebView prompt window when an update is available.

**Tech Stack:** Python 3.11, pywebview, Vue 3 ESM (no build step), GitLab Generic Package Registry, stdlib only.

---

## Codebase Context

**Repo root:** `C:\Users\comsi\Nextcloud\Dev\MCAddonCompanion\`

**Key files:**
- `core/state.py` — state helpers; `get_pack_registry_repos()`, `save_pack_registry_repos()`, `load_state()`, `save_state()`
- `core/gitlab.py` — `GitLabClient`; `list_all_packages()`, `list_packages(name)`, `get_metadata()`, `upload_file()`, `upload_file_path()`
- `main.py` — `Api` class; pack registry methods at lines ~333–560; headless entry points `_headless_startup()` at line 644
- `frontend/pages/pack_registry.js` — Vue 3 component, three tabs: Repos / Publish / Browse
- `frontend/app.js` — root Vue app, `window.__apiReady` promise, `window.__icon()` helper, nav routing
- `frontend/index.html` — SPA shell
- `tests/test_pack_registry_state.py` — existing state tests (pattern to follow)
- `tests/test_gitlab.py` — existing GitLab client tests (pattern to follow)

**Patterns:**
- All JS pages: `await window.__apiReady` before first API call
- Progress events: `self._emit({"type": "step", "step": N, "state": "running"|"ok"|"error", "detail": "..."})` from Python threads
- State: `load_state()` / `save_state(state)` — always reload before mutating
- Tests: `unittest.TestCase`, mock `urllib.request.urlopen` with `MagicMock`, patch `core.config.STATEFILE` for state tests

---

## File Map

| File | Change |
|---|---|
| `core/state.py` | Add `get_tracked_packs()`, `save_tracked_packs()`, `add_tracked_pack()`, `remove_tracked_pack()` |
| `core/gitlab.py` | Add `get_versions_with_metadata(package_name)` returning `[{version, metadata}]` |
| `main.py` | Rewrite `publish_pack`, `get_versions`, `install_pack`; add `check_conflicts`, `get_tracked_packs`, `untrack_pack`, `get_update_prompt_data`, `submit_update_choice`; rewrite `_headless_startup` |
| `frontend/pages/pack_registry.js` | Full rewrite: Repos tab unchanged; Publish tab gains name/version/changenotes/mod-tags fields; Browse tab gains pack list, version detail panel, conflict UI, track checkbox |
| `frontend/pages/update_prompt.js` | New file — update prompt page (countdown, changenotes, Skip/Update) |
| `frontend/app.js` | Add `?mode=update_prompt` query param routing |
| `tests/test_pack_registry_state.py` | Add tests for tracked_packs helpers |
| `tests/test_gitlab.py` | Add test for `get_versions_with_metadata` |

---

## Task 1: Data model — tracked_packs state helpers

**Files:**
- Modify: `core/state.py`
- Modify: `tests/test_pack_registry_state.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_pack_registry_state.py`:

```python
def test_get_tracked_packs_empty_by_default(self):
    from core.state import get_tracked_packs
    with self._patch():
        result = get_tracked_packs()
    self.assertEqual(result, [])

def test_add_and_get_tracked_pack(self):
    from core.state import add_tracked_pack, get_tracked_packs
    entry = {
        "instance_name": "Create Combined",
        "repo_id": "abc123",
        "pack_name": "Create Combined",
        "pack_slug": "create-combined",
        "installed_version": "1.0.0",
    }
    with self._patch():
        add_tracked_pack(entry)
        result = get_tracked_packs()
    self.assertEqual(len(result), 1)
    self.assertEqual(result[0]["pack_slug"], "create-combined")
    self.assertEqual(result[0]["installed_version"], "1.0.0")

def test_add_tracked_pack_overwrites_existing_instance(self):
    from core.state import add_tracked_pack, get_tracked_packs
    entry1 = {"instance_name": "Create Combined", "repo_id": "abc", "pack_name": "Create Combined", "pack_slug": "create-combined", "installed_version": "1.0.0"}
    entry2 = {"instance_name": "Create Combined", "repo_id": "abc", "pack_name": "Create Combined", "pack_slug": "create-combined", "installed_version": "2.0.0"}
    with self._patch():
        add_tracked_pack(entry1)
        add_tracked_pack(entry2)
        result = get_tracked_packs()
    self.assertEqual(len(result), 1)
    self.assertEqual(result[0]["installed_version"], "2.0.0")

def test_remove_tracked_pack(self):
    from core.state import add_tracked_pack, remove_tracked_pack, get_tracked_packs
    entry = {"instance_name": "Create Combined", "repo_id": "abc", "pack_name": "Create Combined", "pack_slug": "create-combined", "installed_version": "1.0.0"}
    with self._patch():
        add_tracked_pack(entry)
        remove_tracked_pack("Create Combined")
        result = get_tracked_packs()
    self.assertEqual(result, [])

def test_remove_tracked_pack_noop_if_missing(self):
    from core.state import remove_tracked_pack, get_tracked_packs
    with self._patch():
        remove_tracked_pack("Nonexistent")  # should not raise
        result = get_tracked_packs()
    self.assertEqual(result, [])
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd C:\Users\comsi\Nextcloud\Dev\MCAddonCompanion
venv\Scripts\python -m pytest tests/test_pack_registry_state.py -v -k "tracked"
```

Expected: 5 failures (ImportError or AttributeError on `get_tracked_packs` etc.)

- [ ] **Step 3: Implement tracked_packs helpers in `core/state.py`**

Add after the `get_repo_by_id` function:

```python
# ---------------------------------------------------------------------------
# tracked_packs helpers
# ---------------------------------------------------------------------------

def get_tracked_packs() -> list[dict]:
    state = load_state()
    return state.get("tracked_packs", [])


def save_tracked_packs(packs: list[dict]) -> None:
    state = load_state()
    state["tracked_packs"] = packs
    save_state(state)


def add_tracked_pack(entry: dict) -> None:
    """Upsert by instance_name."""
    packs = get_tracked_packs()
    packs = [p for p in packs if p.get("instance_name") != entry["instance_name"]]
    packs.append(entry)
    save_tracked_packs(packs)


def remove_tracked_pack(instance_name: str) -> None:
    packs = [p for p in get_tracked_packs() if p.get("instance_name") != instance_name]
    save_tracked_packs(packs)
```

- [ ] **Step 4: Run tests to confirm they pass**

```
venv\Scripts\python -m pytest tests/test_pack_registry_state.py -v -k "tracked"
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add core/state.py tests/test_pack_registry_state.py
git commit -m "feat: add tracked_packs state helpers"
```

---

## Task 2: GitLab client — `get_versions_with_metadata`

**Files:**
- Modify: `core/gitlab.py`
- Modify: `tests/test_gitlab.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_gitlab.py`:

```python
def test_get_versions_with_metadata(self):
    client = self._client()
    versions_resp = [
        {"name": "create-combined", "version": "2.0.0"},
        {"name": "create-combined", "version": "1.0.0"},
    ]
    meta_20 = {"pack_name": "Create Combined", "version": "2.0.0", "changenotes": "New stuff", "mods": [], "removed_mods": []}
    meta_10 = {"pack_name": "Create Combined", "version": "1.0.0", "changenotes": "Initial", "mods": [], "removed_mods": []}

    call_count = [0]
    def fake_urlopen(req, timeout=15):
        url = req.full_url
        call_count[0] += 1
        if "packages?" in url:
            return self._mock_resp(versions_resp)
        elif "2.0.0/metadata.json" in url:
            return self._mock_resp(meta_20)
        else:
            return self._mock_resp(meta_10)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = client.get_versions_with_metadata("create-combined")

    self.assertEqual(len(result), 2)
    self.assertEqual(result[0]["version"], "2.0.0")
    self.assertEqual(result[0]["metadata"]["changenotes"], "New stuff")
    self.assertEqual(result[1]["version"], "1.0.0")
    self.assertEqual(result[1]["metadata"]["changenotes"], "Initial")
```

- [ ] **Step 2: Run test to confirm it fails**

```
venv\Scripts\python -m pytest tests/test_gitlab.py::TestGitLabClient::test_get_versions_with_metadata -v
```

Expected: FAIL with AttributeError.

- [ ] **Step 3: Implement `get_versions_with_metadata` in `core/gitlab.py`**

Add after `get_latest_version`:

```python
def get_versions_with_metadata(self, package_name: str) -> list[dict]:
    """All versions of package_name with their metadata.json, newest first."""
    packages = self.list_packages(package_name)
    result = []
    for p in packages:
        version = p.get("version", "")
        if not version:
            continue
        meta = self.get_metadata(package_name, version)
        result.append({"version": version, "metadata": meta})
    return result
```

- [ ] **Step 4: Run test to confirm it passes**

```
venv\Scripts\python -m pytest tests/test_gitlab.py::TestGitLabClient::test_get_versions_with_metadata -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite to check no regressions**

```
venv\Scripts\python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```
git add core/gitlab.py tests/test_gitlab.py
git commit -m "feat: add get_versions_with_metadata to GitLabClient"
```

---

## Task 3: Backend — slugify helper + rewrite `publish_pack`

**Files:**
- Modify: `main.py` (publish_pack method, ~lines 414–469)

Context: `publish_pack` currently uses `repo["package_name"]` as GitLab package name and generates a UTC timestamp version. We replace this with user-supplied `pack_name`, `version`, `changenotes`, and `mod_tags`. We also compute `removed_mods` by fetching the previous version's metadata.

- [ ] **Step 1: Add `_slugify` helper near top of main.py**

Find the imports section at the top of `main.py` and add this function after the imports (before `_plan_instance`):

```python
import re as _re

def _slugify(name: str) -> str:
    """Convert pack name to GitLab package name slug."""
    s = name.lower().strip()
    s = _re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")
```

- [ ] **Step 2: Rewrite `publish_pack` in `main.py`**

Replace the existing `publish_pack` method (lines ~414–469) with:

```python
def publish_pack(self, params: dict) -> None:
    import tempfile, json as _json
    from core.gitlab import GitLabClient
    from core.sharing import build_export_zip, get_export_file_list
    from core.config import INSTANCES_DIR as INST_DIR

    repo_id = params["repo_id"]
    inst_name = params["instance_name"]
    pack_name = params.get("pack_name", inst_name).strip()
    version = params.get("version", "").strip()
    changenotes = params.get("changenotes", "").strip()
    categories = params.get("categories", {})
    mod_tags = params.get("mod_tags", {})  # {filename: "required"|"client"|"server"}

    if not pack_name:
        self._emit({"type": "summary", "text": "Pack name is required.", "tone": "error"})
        return
    if not version:
        self._emit({"type": "summary", "text": "Version is required.", "tone": "error"})
        return

    repos = get_pack_registry_repos()
    repo = next((r for r in repos if r["id"] == repo_id), None)
    if not repo:
        self._emit({"type": "summary", "text": "Repo not found.", "tone": "error"})
        return

    mc_dir = get_minecraft_dir(INST_DIR, inst_name)
    if not mc_dir:
        self._emit({"type": "summary", "text": "Instance not found.", "tone": "error"})
        return

    slug = _slugify(pack_name)

    def _run():
        try:
            self._emit({"type": "reset"})
            instance_dir = INST_DIR / inst_name
            file_list = get_export_file_list(mc_dir, categories, [])

            # Build mods list from mods/ folder
            mods = []
            if categories.get("mods"):
                mods_dir = mc_dir / "mods"
                if mods_dir.exists():
                    for jar in sorted(mods_dir.glob("*.jar")):
                        side = mod_tags.get(jar.name, "required")
                        mods.append({"name": jar.stem, "file": jar.name, "side": side})

            # Compute removed_mods vs previous version
            client = GitLabClient(repo["base_url"], repo["project_id"],
                                  repo.get("upload_token"), repo.get("read_token"))
            removed_mods = []
            prev_meta = client.get_metadata(slug, "__latest__") if False else {}
            prev_versions = client.list_packages(slug)
            if prev_versions:
                latest_ver = prev_versions[0].get("version", "")
                if latest_ver:
                    prev_meta = client.get_metadata(slug, latest_ver)
            prev_mod_files = {m["file"] for m in prev_meta.get("mods", []) if isinstance(m, dict)}
            new_mod_files = {m["file"] for m in mods}
            removed_mods = sorted(prev_mod_files - new_mod_files)

            zip_filename = f"{slug}-{version}.zip"
            metadata = {
                "pack_name": pack_name,
                "version": version,
                "mc_version": params.get("mc_version", ""),
                "loader": params.get("loader", ""),
                "description": params.get("description", ""),
                "changenotes": changenotes,
                "categories": [k for k, v in categories.items() if v],
                "mods": mods,
                "removed_mods": removed_mods,
            }

            self._emit({"type": "step", "step": 0, "state": "running", "detail": ""})
            with tempfile.TemporaryDirectory() as tmp:
                zip_path = Path(tmp) / zip_filename
                build_export_zip(inst_name, mc_dir, instance_dir, file_list, zip_path)
                size_mb = zip_path.stat().st_size / 1_048_576
                self._emit({"type": "step", "step": 0, "state": "ok", "detail": f"{size_mb:.1f} MB"})

                self._emit({"type": "step", "step": 1, "state": "running", "detail": ""})
                client.upload_file_path(slug, version, zip_filename, zip_path)
                self._emit({"type": "step", "step": 1, "state": "ok", "detail": ""})

                self._emit({"type": "step", "step": 2, "state": "running", "detail": ""})
                client.upload_file(slug, version, "metadata.json",
                                   _json.dumps(metadata, indent=2).encode(),
                                   content_type="application/json")
                self._emit({"type": "step", "step": 2, "state": "ok", "detail": ""})

            self._emit({"type": "summary",
                        "text": f"Published {pack_name} v{version}. Removed: {removed_mods}",
                        "tone": "ok"})
        except Exception as e:
            self._emit({"type": "summary", "text": f"Error: {e}", "tone": "error"})

    threading.Thread(target=_run, daemon=True).start()
```

- [ ] **Step 3: Update `get_versions` to return `[{version, metadata}]` objects**

Replace the existing `get_versions` method (~lines 400–412):

```python
def get_versions(self, repo_id: str, pack_name: str) -> list:
    from core.gitlab import GitLabClient
    repos = get_pack_registry_repos()
    repo = next((r for r in repos if r["id"] == repo_id), None)
    if not repo:
        return []
    client = GitLabClient(repo["base_url"], repo["project_id"],
                          repo.get("upload_token"), repo.get("read_token"))
    return client.get_versions_with_metadata(pack_name)
```

- [ ] **Step 4: Run existing tests to confirm no regressions**

```
venv\Scripts\python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```
git add main.py
git commit -m "feat: rewrite publish_pack with named packs, version, changenotes, mod tags, removed_mods"
```

---

## Task 4: Backend — `check_conflicts`, `install_pack` rewrite, tracked pack API methods

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add `check_conflicts` API method**

Add after `get_versions` in `main.py`:

```python
def check_conflicts(self, repo_id: str, pack_name: str, version: str, inst_name: str) -> list:
    """Return list of relative paths that already exist in the instance's minecraft/ folder."""
    import zipfile, io, urllib.request
    repos = get_pack_registry_repos()
    repo = next((r for r in repos if r["id"] == repo_id), None)
    if not repo:
        return []
    from core.gitlab import GitLabClient
    client = GitLabClient(repo["base_url"], repo["project_id"],
                          repo.get("upload_token"), repo.get("read_token"))
    slug = _slugify(pack_name)
    zip_filename = f"{slug}-{version}.zip"
    url = client.build_download_url(slug, version, zip_filename)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "MCAddonCompanion")
    if repo.get("read_token"):
        req.add_header("PRIVATE-TOKEN", repo["read_token"])
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()

    inst_dir = INSTANCES_DIR / inst_name
    mc_dir = get_minecraft_dir(INSTANCES_DIR, inst_name)
    if not mc_dir:
        mc_dir = inst_dir / "minecraft"

    conflicts = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = zf.namelist()
        has_mc_prefix = any(m.startswith(".minecraft/") for m in members)
        has_plain_prefix = any(m.startswith("minecraft/") for m in members)
        prefix = ".minecraft/" if has_mc_prefix else ("minecraft/" if has_plain_prefix else "")
        for member in members:
            if member.endswith("/"):
                continue
            rel = member[len(prefix):] if prefix else member
            dest = mc_dir / Path(rel)
            if dest.exists():
                conflicts.append(rel)
    return conflicts
```

- [ ] **Step 2: Rewrite `install_pack` to support `mode` and `removed_mods`**

Replace the existing `install_pack` method (~lines 471–end of method) with:

```python
def install_pack(self, params: dict) -> None:
    import urllib.request, urllib.error, zipfile, io, json as _json

    repo_id = params["repo_id"]
    pack_name = params["pack_name"]
    version = params["version"]
    inst_name = params["instance_name"]
    mode = params.get("mode", "new")   # "new" or "existing"
    track = params.get("track", False)

    repos = get_pack_registry_repos()
    repo = next((r for r in repos if r["id"] == repo_id), None)
    if not repo:
        self._emit({"type": "summary", "text": "Repo not found.", "tone": "error"})
        return

    slug = _slugify(pack_name)

    def _run():
        try:
            self._emit({"type": "reset"})
            from core.gitlab import GitLabClient
            client = GitLabClient(repo["base_url"], repo["project_id"],
                                  repo.get("upload_token"), repo.get("read_token"))

            # Step 0: Download zip
            self._emit({"type": "step", "step": 0, "state": "running", "detail": ""})
            zip_filename = f"{slug}-{version}.zip"
            url = client.build_download_url(slug, version, zip_filename)
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "MCAddonCompanion")
            if repo.get("read_token"):
                req.add_header("PRIVATE-TOKEN", repo["read_token"])
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            size_mb = len(data) / 1_048_576
            self._emit({"type": "step", "step": 0, "state": "ok", "detail": f"{size_mb:.1f} MB"})

            # Fetch metadata for removed_mods and instance files
            meta = client.get_metadata(slug, version)
            removed_mods = meta.get("removed_mods", [])

            # Step 1: Extract
            self._emit({"type": "step", "step": 1, "state": "running", "detail": ""})
            inst_dir = INSTANCES_DIR / inst_name
            existing_mc = get_minecraft_dir(INSTANCES_DIR, inst_name)
            if existing_mc:
                mc_dir = existing_mc
            else:
                mc_dir = inst_dir / "minecraft"
                for d in INSTANCES_DIR.iterdir():
                    if d.is_dir() and (d / "minecraft").exists():
                        mc_dir = inst_dir / "minecraft"
                        break
                    elif d.is_dir() and (d / ".minecraft").exists():
                        mc_dir = inst_dir / ".minecraft"
                        break
            mc_dir.mkdir(parents=True, exist_ok=True)

            # Delete publisher-declared removed mods (only jars explicitly removed by publisher)
            if removed_mods and mode == "existing":
                mods_dir = mc_dir / "mods"
                for jar_name in removed_mods:
                    target = mods_dir / jar_name
                    if target.exists():
                        target.unlink()

            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                members = zf.namelist()
                has_mc_prefix = any(m.startswith(".minecraft/") for m in members)
                has_plain_prefix = any(m.startswith("minecraft/") for m in members)
                prefix = ".minecraft/" if has_mc_prefix else ("minecraft/" if has_plain_prefix else "")
                count = 0
                for member in members:
                    if member.endswith("/"):
                        continue
                    rel = member[len(prefix):] if prefix else member
                    dest = mc_dir / Path(rel)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        dst.write(src.read())
                    count += 1
            self._emit({"type": "step", "step": 1, "state": "ok", "detail": f"{count} files"})

            # Step 2: Write Prism instance files (only for new instances)
            self._emit({"type": "step", "step": 2, "state": "running", "detail": ""})
            if mode == "new":
                mc_ver = meta.get("mc_version", "")
                loader = meta.get("loader", "fabric")
                cfg_path = inst_dir / "instance.cfg"
                if not cfg_path.exists():
                    cfg_path.write_text(
                        f"InstanceType=OneSix\nname={inst_name}\n",
                        encoding="utf-8"
                    )
                mmc_path = inst_dir / "mmc-pack.json"
                if not mmc_path.exists():
                    uid = "net.fabricmc.fabric-loader" if loader == "fabric" else "net.minecraftforge"
                    mmc_pack = {
                        "components": [
                            {"important": True, "uid": "net.minecraft", "version": mc_ver},
                            {"uid": uid},
                        ],
                        "formatVersion": 1,
                    }
                    mmc_path.write_text(_json.dumps(mmc_pack, indent=2), encoding="utf-8")
            self._emit({"type": "step", "step": 2, "state": "ok", "detail": ""})

            # Track if requested
            if track:
                from core.state import add_tracked_pack
                add_tracked_pack({
                    "instance_name": inst_name,
                    "repo_id": repo_id,
                    "pack_name": pack_name,
                    "pack_slug": slug,
                    "installed_version": version,
                })

            self._emit({"type": "summary", "text": f"Installed {pack_name} v{version}.", "tone": "ok"})
        except Exception as e:
            self._emit({"type": "summary", "text": f"Error: {e}", "tone": "error"})

    threading.Thread(target=_run, daemon=True).start()
```

- [ ] **Step 3: Add `get_tracked_packs` and `untrack_pack` API methods**

Add after `install_pack` in `main.py`:

```python
def get_tracked_packs_api(self) -> list:
    from core.state import get_tracked_packs
    from core.gitlab import GitLabClient
    tracked = get_tracked_packs()
    result = []
    for entry in tracked:
        repo = get_repo_by_id(entry["repo_id"])
        has_update = False
        latest = None
        if repo:
            try:
                client = GitLabClient(repo["base_url"], repo["project_id"],
                                      repo.get("upload_token"), repo.get("read_token"))
                latest = client.get_latest_version(entry["pack_slug"])
                has_update = bool(latest and latest != entry["installed_version"])
            except Exception:
                pass
        result.append({**entry, "has_update": has_update, "latest_version": latest})
    return result

def untrack_pack(self, instance_name: str) -> None:
    from core.state import remove_tracked_pack
    remove_tracked_pack(instance_name)
```

- [ ] **Step 4: Run tests**

```
venv\Scripts\python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```
git add main.py
git commit -m "feat: add check_conflicts, rewrite install_pack with mode/track/removed_mods, add tracked pack API"
```

---

## Task 5: Backend — `get_update_prompt_data`, `submit_update_choice`, rewrite `_headless_startup`

**Files:**
- Modify: `main.py`

The startup hook currently runs headless (`_headless_startup` with a noop emit). When the instance has a tracked pack with a newer version, we need to open a PyWebView window instead, show the update prompt, wait for the user's choice (or 20s timeout), then proceed.

- [ ] **Step 1: Add `get_update_prompt_data` and `submit_update_choice` to the `Api` class**

Add after `untrack_pack` in `main.py`:

```python
def get_update_prompt_data(self) -> dict:
    """Called by update_prompt.js on load. Returns tracked pack update info."""
    return getattr(self, "_update_prompt_data", {})

def submit_update_choice(self, choice: str) -> None:
    """Called by update_prompt.js when user clicks Update or Skip (or countdown expires).
    choice: 'update' | 'skip'
    """
    self._update_choice = choice
    # Close the window
    win = self._win_ref[0] if self._win_ref else None
    if win:
        win.destroy()
```

- [ ] **Step 2: Rewrite `_headless_startup` to open update prompt window when needed**

Replace `_headless_startup` (~lines 644–652) with:

```python
def _headless_startup(name: str) -> None:
    from core.state import get_tracked_packs, add_tracked_pack
    from core.gitlab import GitLabClient

    instances = [d.name for d in INSTANCES_DIR.iterdir() if d.is_dir()] if INSTANCES_DIR.exists() else []
    if name not in instances:
        log.error("Instance %r not found", name)
        sys.exit(1)

    # Check if this instance has a tracked pack with an update available
    tracked = next((t for t in get_tracked_packs() if t["instance_name"] == name), None)
    if tracked:
        repo = get_repo_by_id(tracked["repo_id"])
        if repo:
            try:
                client = GitLabClient(repo["base_url"], repo["project_id"],
                                      repo.get("upload_token"), repo.get("read_token"))
                latest = client.get_latest_version(tracked["pack_slug"])
                if latest and latest != tracked["installed_version"]:
                    meta = client.get_metadata(tracked["pack_slug"], latest)
                    # Open update prompt window
                    win_ref: list = [None]
                    api = Api(win_ref)
                    api._update_prompt_data = {
                        "instance_name": name,
                        "pack_name": tracked["pack_name"],
                        "installed_version": tracked["installed_version"],
                        "new_version": latest,
                        "changenotes": meta.get("changenotes", ""),
                        "repo_id": tracked["repo_id"],
                        "pack_slug": tracked["pack_slug"],
                    }
                    api._update_choice = "skip"  # default if window closed without choice

                    frontend_dir = Path(__file__).parent / "frontend"
                    window = webview.create_window(
                        f"Update available — {tracked['pack_name']}",
                        url=str(frontend_dir / "index.html") + "?mode=update_prompt",
                        js_api=api,
                        width=560,
                        height=420,
                        resizable=False,
                    )
                    win_ref[0] = window
                    webview.start(debug=not getattr(sys, "frozen", False))

                    if api._update_choice == "update":
                        # Install update silently
                        import urllib.request, zipfile, io, json as _json
                        slug = tracked["pack_slug"]
                        version = latest
                        repo_obj = repo
                        zip_filename = f"{slug}-{version}.zip"
                        url_dl = client.build_download_url(slug, version, zip_filename)
                        req = urllib.request.Request(url_dl)
                        req.add_header("User-Agent", "MCAddonCompanion")
                        if repo_obj.get("read_token"):
                            req.add_header("PRIVATE-TOKEN", repo_obj["read_token"])
                        with urllib.request.urlopen(req, timeout=120) as resp:
                            data = resp.read()
                        removed_mods = meta.get("removed_mods", [])
                        mc_dir = get_minecraft_dir(INSTANCES_DIR, name)
                        if mc_dir:
                            mods_dir = mc_dir / "mods"
                            for jar_name in removed_mods:
                                target = mods_dir / jar_name
                                if target.exists():
                                    target.unlink()
                            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                                members = zf.namelist()
                                has_mc = any(m.startswith(".minecraft/") for m in members)
                                has_plain = any(m.startswith("minecraft/") for m in members)
                                prefix = ".minecraft/" if has_mc else ("minecraft/" if has_plain else "")
                                for member in members:
                                    if member.endswith("/"):
                                        continue
                                    rel = member[len(prefix):] if prefix else member
                                    dest = mc_dir / Path(rel)
                                    dest.parent.mkdir(parents=True, exist_ok=True)
                                    with zf.open(member) as src, open(dest, "wb") as dst:
                                        dst.write(src.read())
                        add_tracked_pack({**tracked, "installed_version": latest})
            except Exception as e:
                log.warning("Update check failed for %r: %s", name, e)

    # Run normal startup sync
    plan = _plan_instance(name, "startup")
    def _noop(event): pass
    _execute_instance_plan(_noop, name, plan)
    sys.exit(0)
```

- [ ] **Step 3: Add `_win_ref` and `_update_choice` attributes to `Api.__init__`**

Find `Api.__init__` in `main.py` and ensure it stores `win_ref`:

```python
# In Api.__init__, the existing line is:
#   self._win_ref = win_ref  (or similar)
# Add:
self._update_choice = "skip"
self._update_prompt_data = {}
```

Look for the existing `Api` class `__init__` and add these two lines to it. The class already stores `win_ref` — just add the two new attributes.

- [ ] **Step 4: Run tests**

```
venv\Scripts\python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```
git add main.py
git commit -m "feat: add update prompt API methods and rewrite headless startup with update check"
```

---

## Task 6: Frontend — update_prompt.js page

**Files:**
- Create: `frontend/pages/update_prompt.js`
- Modify: `frontend/app.js`

- [ ] **Step 1: Create `frontend/pages/update_prompt.js`**

```javascript
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
      // For update prompt we only show removed_mods from new version metadata
      // (added mods are implicit — they're in the ZIP)
      return { removed: data.value.removed_mods || [] }
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
            <span v-html="icon('arrow-right', 16)" style="color:var(--text-3)"></span>
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

        <div v-if="modDiff.removed && modDiff.removed.length" class="card" style="margin-bottom:16px">
          <div class="card-header" style="padding:12px 16px">
            <div class="kicker">Mod removals</div>
          </div>
          <div class="card-body" style="padding:8px 16px">
            <div v-for="jar in modDiff.removed" :key="jar" class="mono fs-12 text-err" style="padding:2px 0">
              − {{ jar }}
            </div>
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
```

- [ ] **Step 2: Add `?mode=update_prompt` routing to `frontend/app.js`**

Find the section in `app.js` that sets up routing / the root component. After the `window.__apiReady` setup and before the main `createApp` call, add query-string detection. The app currently renders the full nav shell unconditionally. Change the root template to detect `?mode=update_prompt` and render only the update prompt page:

In `app.js`, find the `setup()` function of the root component (or the `createApp` call). Add at the top of the component's `setup()`:

```javascript
const urlParams = new URLSearchParams(window.location.search)
const isUpdatePrompt = urlParams.get('mode') === 'update_prompt'
```

Then in the root template, wrap the entire normal shell in `<template v-if="!isUpdatePrompt">` and add:

```html
<template v-if="isUpdatePrompt">
  <update-prompt-page />
</template>
```

Register `UpdatePromptPage` as a component imported from `./pages/update_prompt.js`.

The exact edits depend on the current `app.js` structure. Read `frontend/app.js` before making changes to find the right insertion points.

- [ ] **Step 3: Hotpatch installed app to test**

```
cp frontend/pages/update_prompt.js "%LOCALAPPDATA%\MCAddonCompanion\_internal\frontend\pages\"
cp frontend/app.js "%LOCALAPPDATA%\MCAddonCompanion\_internal\frontend\"
```

Or run from repo: `venv\Scripts\pythonw.exe main.py`

- [ ] **Step 4: Commit**

```
git add frontend/pages/update_prompt.js frontend/app.js
git commit -m "feat: add update_prompt page and app.js routing for update_prompt mode"
```

---

## Task 7: Frontend — Publish tab rewrite

**Files:**
- Modify: `frontend/pages/pack_registry.js` (Publish tab section only)

The Publish tab currently has: instance dropdown, category checkboxes, mc_version/loader/description fields, progress panel. We add: pack name (pre-filled from instance), version (text), changenotes, mod tags table (shown when mods category checked).

- [ ] **Step 1: Read the current Publish tab in pack_registry.js**

Read `C:\Users\comsi\Nextcloud\Dev\MCAddonCompanion\frontend\pages\pack_registry.js` and locate the Publish tab template section and the `publishForm` ref and `publishPack` function.

- [ ] **Step 2: Update `publishForm` ref**

Find the existing `publishForm` ref in `setup()` and replace/extend it:

```javascript
const publishForm = ref({
  instance_name: '',
  pack_name: '',        // new — pre-filled from instance_name
  version: '',          // new
  description: '',      // new
  changenotes: '',      // new
  mc_version: '',
  loader: 'fabric',
  categories: { mods: true, config: true, saves: false, resourcepacks: false, shaderpacks: false, servers: false },
  mod_tags: {},         // new — {filename: side} populated when mods category checked
})
```

- [ ] **Step 3: Add `modFiles` ref and watcher**

In `setup()`, after `publishForm`:

```javascript
const modFiles = ref([])  // [{name, file, side}] — populated when instance + mods selected

const loadModFiles = async () => {
  if (!publishForm.value.instance_name || !publishForm.value.categories.mods) {
    modFiles.value = []
    return
  }
  await window.__apiReady
  const files = await window.pywebview.api.get_instance_mod_files(publishForm.value.instance_name)
  modFiles.value = files.map(f => ({ file: f, side: publishForm.value.mod_tags[f] || 'required' }))
}
```

Watch `instance_name` and `categories.mods` to trigger `loadModFiles`. Also add `watch` to imports.

Add to returned object: `modFiles, loadModFiles`.

Note: `get_instance_mod_files` is a new backend method added in Task 3b below.

- [ ] **Step 4: Auto-fill pack_name when instance_name changes**

Add a watcher on `publishForm.value.instance_name`:

```javascript
watch(() => publishForm.value.instance_name, (val) => {
  if (val && !publishForm.value.pack_name) {
    publishForm.value.pack_name = val
  }
  loadModFiles()
})
```

- [ ] **Step 5: Update `publishPack` function to send new fields**

Find the `publishPack` function and update the params sent to `window.pywebview.api.publish_pack`:

```javascript
const publishPack = async () => {
  if (!publishForm.value.instance_name || !selectedRepo.value) return
  publishing.value = true
  publishDone.value = false
  const mod_tags = {}
  modFiles.value.forEach(m => { mod_tags[m.file] = m.side })
  await window.__apiReady
  await window.pywebview.api.publish_pack({
    repo_id: selectedRepo.value.id,
    instance_name: publishForm.value.instance_name,
    pack_name: publishForm.value.pack_name,
    version: publishForm.value.version,
    description: publishForm.value.description,
    changenotes: publishForm.value.changenotes,
    mc_version: publishForm.value.mc_version,
    loader: publishForm.value.loader,
    categories: publishForm.value.categories,
    mod_tags,
  })
}
```

- [ ] **Step 6: Update Publish tab template**

In the Publish tab template, add the following fields after the instance dropdown and before the categories checkboxes:

```html
<!-- Pack name -->
<div class="field-row">
  <label class="field-label">Pack Name</label>
  <input v-model="publishForm.pack_name" class="input" placeholder="Pack name" style="width:100%">
</div>
<!-- Version -->
<div class="field-row">
  <label class="field-label">Version</label>
  <input v-model="publishForm.version" class="input" placeholder="e.g. 1.0.0" style="width:160px">
</div>
<!-- Description -->
<div class="field-row">
  <label class="field-label">Description</label>
  <input v-model="publishForm.description" class="input" placeholder="Short description" style="width:100%">
</div>
<!-- Changenotes -->
<div class="field-row">
  <label class="field-label">Changenotes</label>
  <textarea v-model="publishForm.changenotes" class="input" rows="3" placeholder="What changed in this version?" style="width:100%;resize:vertical"></textarea>
</div>
```

And after the categories checkboxes, add the mod tags table (shown only when mods category is checked):

```html
<!-- Mod tags table -->
<template v-if="publishForm.categories.mods && modFiles.length">
  <div class="card-title fs-12 text-2 mt-16 mb-8">Mod Side Tags</div>
  <table class="data-table">
    <thead>
      <tr>
        <th style="text-align:left">File</th>
        <th style="text-align:center">Side</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="mod in modFiles" :key="mod.file">
        <td class="mono fs-12">{{ mod.file }}</td>
        <td style="text-align:center">
          <select v-model="mod.side" class="input" style="width:110px;padding:3px 6px">
            <option value="required">required</option>
            <option value="client">client</option>
            <option value="server">server</option>
          </select>
        </td>
      </tr>
    </tbody>
  </table>
</template>
```

- [ ] **Step 7: Commit**

```
git add frontend/pages/pack_registry.js
git commit -m "feat: rewrite Publish tab with pack name, version, changenotes, mod tags"
```

---

## Task 3b: Backend — `get_instance_mod_files` API method

*(This task must be done before Task 7 is tested end-to-end. Insert it between Task 3 and Task 4 if executing sequentially, or add it now.)*

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add `get_instance_mod_files` to `Api` class**

Add after `get_packs` in `main.py`:

```python
def get_instance_mod_files(self, inst_name: str) -> list:
    """Return sorted list of .jar filenames from the instance's mods/ folder."""
    from core.config import INSTANCES_DIR as INST_DIR
    mc_dir = get_minecraft_dir(INST_DIR, inst_name)
    if not mc_dir:
        return []
    mods_dir = mc_dir / "mods"
    if not mods_dir.exists():
        return []
    return sorted(f.name for f in mods_dir.glob("*.jar"))
```

- [ ] **Step 2: Run tests**

```
venv\Scripts\python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```
git add main.py
git commit -m "feat: add get_instance_mod_files API method"
```

---

## Task 8: Frontend — Browse tab rewrite

**Files:**
- Modify: `frontend/pages/pack_registry.js` (Browse tab section)

The Browse tab currently has: pack list dropdown, version dropdown, install button, progress panel. We replace it with: left pack list, right detail panel (version dropdown → changenotes + mod diff + mod list), two install buttons, track checkbox, conflict warning.

- [ ] **Step 1: Add new refs to `setup()` in pack_registry.js**

In the Browse tab section of `setup()`, add:

```javascript
const selectedPack = ref(null)          // pack name string
const packVersions = ref([])            // [{version, metadata}]
const selectedVersionObj = ref(null)    // {version, metadata}
const conflictFiles = ref([])
const showConflictWarning = ref(false)
const trackOnInstall = ref(false)
const installMode = ref('new')          // 'new' | 'existing'
const installInstanceName = ref('')     // for "create new" — editable
const installExistingInstance = ref('') // for "install to existing"
```

- [ ] **Step 2: Update `selectPack` and version loading**

Replace the existing pack/version selection logic:

```javascript
const selectPack = async (packName) => {
  selectedPack.value = packName
  selectedVersionObj.value = null
  packVersions.value = []
  if (!packName || !selectedRepo.value) return
  await window.__apiReady
  const versions = await window.pywebview.api.get_versions(selectedRepo.value.id, packName)
  packVersions.value = versions  // [{version, metadata}]
  if (versions.length) selectVersion(versions[0])
}

const selectVersion = (versionObj) => {
  selectedVersionObj.value = versionObj
  // Pre-fill install instance name from pack_name in metadata
  const meta = versionObj.metadata || {}
  installInstanceName.value = meta.pack_name || selectedPack.value || ''
}
```

- [ ] **Step 3: Add mod diff computation**

```javascript
const modDiff = computed(() => {
  if (!selectedVersionObj.value || !packVersions.value.length) return { added: [], removed: [] }
  const versions = packVersions.value
  const idx = versions.findIndex(v => v.version === selectedVersionObj.value.version)
  const curMeta = selectedVersionObj.value.metadata || {}
  const curMods = new Set((curMeta.mods || []).map(m => m.file))
  const removed = curMeta.removed_mods || []
  // Added = in current but not in previous version's mods
  let added = []
  if (idx < versions.length - 1) {
    const prevMeta = versions[idx + 1].metadata || {}
    const prevMods = new Set((prevMeta.mods || []).map(m => m.file))
    added = [...curMods].filter(f => !prevMods.has(f))
  }
  return { added, removed }
})
```

- [ ] **Step 4: Update `installPack` function**

```javascript
const installPack = async () => {
  if (!selectedPack.value || !selectedVersionObj.value || !selectedRepo.value) return
  const instName = installMode.value === 'new'
    ? installInstanceName.value
    : installExistingInstance.value
  if (!instName) return
  installing.value = true
  installDone.value = false
  await window.__apiReady
  await window.pywebview.api.install_pack({
    repo_id: selectedRepo.value.id,
    pack_name: selectedPack.value,
    version: selectedVersionObj.value.version,
    instance_name: instName,
    mode: installMode.value,
    track: trackOnInstall.value,
  })
}

const checkAndInstall = async () => {
  if (installMode.value === 'existing' && installExistingInstance.value) {
    await window.__apiReady
    const conflicts = await window.pywebview.api.check_conflicts(
      selectedRepo.value.id,
      selectedPack.value,
      selectedVersionObj.value.version,
      installExistingInstance.value
    )
    if (conflicts.length) {
      conflictFiles.value = conflicts
      showConflictWarning.value = true
      return
    }
  }
  installPack()
}
```

- [ ] **Step 5: Rewrite Browse tab template**

Replace the Browse tab template with a two-column layout:

```html
<!-- Browse tab -->
<template v-if="activeTab === 'browse'">
  <div v-if="!selectedRepo" class="loading">Select a repo first.</div>
  <template v-else>
    <div style="display:grid;grid-template-columns:240px 1fr;gap:16px;align-items:start">

      <!-- Left: pack list -->
      <div class="card">
        <div class="card-header"><div class="kicker">Packs</div></div>
        <div v-if="loadingPacks" class="loading fs-13">Loading…</div>
        <div v-else-if="!packs.length" class="loading fs-13 text-3">No packs found</div>
        <div v-else>
          <div v-for="pack in packs" :key="pack"
               @click="selectPack(pack)"
               :class="['pack-list-item', selectedPack === pack ? 'selected' : '']"
               style="padding:10px 16px;cursor:pointer;border-bottom:1px solid var(--line);font-size:13px"
               :style="selectedPack === pack ? 'background:var(--bg-2);color:var(--text-0)' : 'color:var(--text-1)'">
            {{ pack }}
          </div>
        </div>
      </div>

      <!-- Right: pack detail -->
      <div v-if="!selectedPack" class="card">
        <div class="card-body loading fs-13 text-3">Select a pack to view details.</div>
      </div>
      <template v-else>
        <div style="display:flex;flex-direction:column;gap:16px">

          <!-- Version selector -->
          <div class="card">
            <div class="card-header"><div class="kicker">Version</div></div>
            <div class="card-body" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
              <select class="input" style="width:180px" @change="e => selectVersion(packVersions.find(v => v.version === e.target.value))">
                <option v-for="v in packVersions" :key="v.version" :value="v.version">{{ v.version }}</option>
              </select>
              <template v-if="selectedVersionObj">
                <span class="mono fs-12 text-3">{{ selectedVersionObj.metadata?.mc_version }}</span>
                <span class="mono fs-12 text-3">{{ selectedVersionObj.metadata?.loader }}</span>
              </template>
            </div>
          </div>

          <!-- Changenotes + mod diff -->
          <div v-if="selectedVersionObj" class="card">
            <div class="card-header"><div class="kicker">Changenotes</div></div>
            <div class="card-body">
              <div v-if="selectedVersionObj.metadata?.changenotes" class="fs-13 text-1" style="white-space:pre-wrap;margin-bottom:12px">{{ selectedVersionObj.metadata.changenotes }}</div>
              <div v-else class="fs-13 text-3">No changenotes for this version.</div>
              <div v-if="modDiff.added.length || modDiff.removed.length" style="margin-top:12px;display:flex;gap:24px">
                <div v-if="modDiff.added.length">
                  <div class="fs-12 text-3 mb-4">Added</div>
                  <div v-for="f in modDiff.added" :key="f" class="mono fs-12 text-ok">+ {{ f }}</div>
                </div>
                <div v-if="modDiff.removed.length">
                  <div class="fs-12 text-3 mb-4">Removed</div>
                  <div v-for="f in modDiff.removed" :key="f" class="mono fs-12 text-err">− {{ f }}</div>
                </div>
              </div>
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
                      <span :class="['pill', mod.side === 'client' ? 'pill-blue' : mod.side === 'server' ? 'pill-green' : 'pill-gray']" style="font-size:11px">{{ mod.side }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Install section -->
          <div class="card">
            <div class="card-header"><div class="kicker">Install</div></div>
            <div class="card-body" style="display:flex;flex-direction:column;gap:14px">

              <!-- Mode toggle -->
              <div style="display:flex;gap:8px">
                <button :class="['btn btn-sm', installMode === 'new' ? 'btn-primary' : 'btn-ghost']" @click="installMode = 'new'">Create new instance</button>
                <button :class="['btn btn-sm', installMode === 'existing' ? 'btn-primary' : 'btn-ghost']" @click="installMode = 'existing'">Install to existing</button>
              </div>

              <!-- New instance name -->
              <div v-if="installMode === 'new'" style="display:flex;gap-8px;align-items:center;gap:8px">
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

              <!-- Conflict warning -->
              <div v-if="showConflictWarning" style="background:var(--bg-0);border:1px solid var(--warn);border-radius:8px;padding:12px 16px">
                <div class="fw-500 text-0 fs-13 mb-8">⚠ Conflicting files ({{ conflictFiles.length }})</div>
                <div v-for="f in conflictFiles.slice(0,10)" :key="f" class="mono fs-12 text-2">{{ f }}</div>
                <div v-if="conflictFiles.length > 10" class="fs-12 text-3">…and {{ conflictFiles.length - 10 }} more</div>
                <div style="display:flex;gap:8px;margin-top:12px">
                  <button class="btn btn-ghost btn-sm" @click="showConflictWarning = false">Cancel</button>
                  <button class="btn btn-primary btn-sm" @click="() => { showConflictWarning = false; installPack() }">Proceed anyway</button>
                </div>
              </div>

              <button v-if="!showConflictWarning" class="btn btn-primary btn-sm" :disabled="installing" @click="checkAndInstall">
                <span v-html="icon('download', 13)" style="margin-right:6px"></span>
                {{ installing ? 'Installing…' : 'Install' }}
              </button>
            </div>
          </div>

          <!-- Progress panel -->
          <div v-if="installing || installSummary" class="card">
            <div class="card-body" style="background:var(--bg-0);border-radius:8px;padding:10px 8px">
              <div class="kicker" style="padding:0 8px 6px">Progress</div>
              <div v-for="(s, i) in installSteps" :key="i" class="progress-step">
                <span class="progress-step-icon" :class="s.state">
                  <span v-if="s.state==='done'" v-html="icon('check',11)"></span>
                  <span v-else-if="s.state==='run'" class="spin" v-html="icon('spin',11)"></span>
                  <span v-else-if="s.state==='err'" v-html="icon('x',11)"></span>
                </span>
                <span class="fill fs-12 text-0">{{ s.label }}</span>
                <span class="mono fs-11 text-3">{{ s.detail }}</span>
              </div>
              <div v-if="installSummary" style="border-top:1px solid var(--line);margin:6px 8px 0;padding-top:8px;font-size:12px"
                :style="installSummary.tone==='ok' ? 'color:var(--ok)' : 'color:var(--err)'">
                {{ installSummary.text }}
              </div>
            </div>
          </div>

        </div>
      </template>
    </div>
  </template>
</template>
```

- [ ] **Step 6: Add `allInstances` to `setup()` and load on mount**

```javascript
const allInstances = ref([])

// In the load() function or onMounted, add:
const instanceData = await window.pywebview.api.get_all_instances()
allInstances.value = instanceData.map(i => i.name)
```

Add `allInstances` to the returned object.

- [ ] **Step 7: Commit**

```
git add frontend/pages/pack_registry.js
git commit -m "feat: rewrite Browse tab with pack list, version detail, mod diff, conflict detection, track checkbox"
```

---

## Task 9: Integration test + hotpatch

**Files:**
- No code changes

- [ ] **Step 1: Run full test suite**

```
venv\Scripts\python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 2: Launch app from repo**

```
start "" "venv\Scripts\pythonw.exe" main.py
```

- [ ] **Step 3: Manual smoke test — Publish**

1. Go to Pack Registry → Repos tab, confirm existing repo loads
2. Go to Publish tab, select an instance (e.g. "Create Combined")
3. Confirm pack name pre-fills with instance name
4. Fill version (e.g. `2.0.0`), changenotes, check Mods category
5. Confirm mod tags table appears with all JARs defaulted to `required`
6. Change one mod to `client`, publish
7. Confirm 3 progress steps complete and summary shows `Published Create Combined v2.0.0`

- [ ] **Step 4: Manual smoke test — Browse**

1. Go to Browse tab, select repo
2. Confirm pack list appears in left column
3. Click a pack, confirm version dropdown loads
4. Select a version, confirm changenotes and mod list appear
5. Test "Create new instance" — fill name, click Install, confirm progress steps
6. Test "Install to existing" — select instance, click Install, confirm conflict check runs

- [ ] **Step 5: Manual smoke test — Update prompt**

1. In state.json, manually add a tracked_packs entry with `installed_version` set to an older version
2. Run: `venv\Scripts\python main.py --startup "Create Combined"`
3. Confirm update prompt window opens with pack name, version diff, changenotes, countdown
4. Confirm Skip closes window and proceeds
5. Confirm Update installs and closes window

- [ ] **Step 6: Hotpatch installed app**

```
cp frontend/pages/pack_registry.js "%LOCALAPPDATA%\MCAddonCompanion\_internal\frontend\pages\"
cp frontend/pages/update_prompt.js "%LOCALAPPDATA%\MCAddonCompanion\_internal\frontend\pages\"
cp frontend/app.js "%LOCALAPPDATA%\MCAddonCompanion\_internal\frontend\"
```

- [ ] **Step 7: Final commit**

```
git add .
git commit -m "feat: pack registry v2 complete — named packs, versioning, mod tags, tracked instances"
```
