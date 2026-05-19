import logging
import logging.handlers
import os
import pathlib
import sys
import json
import threading
from pathlib import Path


def _configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    if sys.platform == "win32":
        log_dir = pathlib.Path(os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA", "."))) / "MCAddonCompanion" / "logs"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", str(pathlib.Path.home() / ".local/share"))
        log_dir = pathlib.Path(xdg) / "MCAddonCompanion" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.handlers.RotatingFileHandler(
        log_dir / "mcaddoncompanion.log",
        maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)

    # JS errors go to a separate file so they don't pollute the main log
    js_fh = logging.handlers.RotatingFileHandler(
        log_dir / "js_errors.log",
        maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    js_fh.setFormatter(fmt)
    js_log = logging.getLogger("js")
    js_log.addHandler(js_fh)
    js_log.propagate = False  # don't echo JS noise into main log

    if not getattr(sys, "frozen", False):
        root.addHandler(logging.StreamHandler())


_configure_logging()
log = logging.getLogger(__name__)

if not getattr(sys, "frozen", False):
    _VENV = Path(__file__).parent / "venv"
    if sys.platform == "win32":
        _VENV_PYTHON = _VENV / "Scripts" / "pythonw.exe"
    else:
        _VENV_PYTHON = _VENV / "bin" / "python"

    def _ensure_venv():
        if _VENV.exists() and sys.executable != str(_VENV_PYTHON):
            import subprocess
            subprocess.Popen([str(_VENV_PYTHON)] + sys.argv)
            sys.exit(0)

    def _create_venv():
        import venv, subprocess
        print("Creating venv...")
        venv.create(str(_VENV), with_pip=True)
        reqs = Path(__file__).parent / "requirements.txt"
        if reqs.exists() and reqs.read_text().strip():
            pip = str(_VENV / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip"))
            subprocess.check_call([pip, "install", "-r", str(reqs)])

    if not _VENV.exists():
        _create_venv()
    _ensure_venv()

import webview

from core.config import INSTANCES_DIR, VERSION
from core.prism import get_minecraft_dir, is_prism_running, patch_exit_commands, clear_exit_commands
from core.state import (
    load_state, save_state,
    get_instance_sync_config, save_instance_sync_config,
    get_instance_effective_settings, is_instance_sync_configured,
    get_pack_registry_repos, save_pack_registry_repos, make_repo_id,
    get_repo_by_id,
    get_installed_instances, save_installed_instance,
)

import re as _re

def _slugify(name: str) -> str:
    """Convert pack name to GitLab package name slug."""
    s = name.lower().strip()
    s = _re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# ---------------------------------------------------------------------------
# Sync orchestration (headless + GUI shared)
# ---------------------------------------------------------------------------

def _plan_instance(instance_name: str, mode: str) -> dict:
    state = load_state()
    plan: dict = {"schematic": False, "instance_task": None,
                  "cfg": None, "settings": None, "mc_dir": None, "sync_dir": None}
    if mode == "exit":
        plan["schematic"] = instance_name in state.get("schematic_sync", {}).get("autosync_instances", [])
    if is_instance_sync_configured():
        cfg = get_instance_sync_config()
        settings = get_instance_effective_settings(cfg, instance_name)
        if settings["enabled"]:
            instances_path = Path(cfg["instances_path"])
            sync_path = Path(cfg["sync_path"])
            mc_dir = get_minecraft_dir(instances_path, instance_name)
            sync_dir = sync_path / "instance_sync" / instance_name
            if mc_dir:
                plan.update(cfg=cfg, settings=settings, mc_dir=mc_dir, sync_dir=sync_dir)
                if mode == "exit" and settings["exit_sync"]:
                    plan["instance_task"] = "Exit Sync"
                elif mode == "startup" and settings["startup_sync"]:
                    plan["instance_task"] = "Startup Sync"
    return plan


def _execute_instance_plan(emit, inst: str, plan: dict):
    """Execute a pre-planned sync, emitting progress events via emit()."""
    from modules.schematic_sync.page import run_autosync as _ss_run_autosync
    from modules.instance_sync.sync import (
        is_blacklisted, read_manifest, write_manifest, _file_stat, _append_changelog
    )
    import shutil
    from datetime import datetime

    step = 0

    if plan["schematic"]:
        emit({"type": "step", "step": step, "state": "running", "detail": ""})
        result = _ss_run_autosync([inst])
        errors = result.get("errors", [])
        emit({"type": "step", "step": step, "state": "error" if errors else "ok",
              "detail": f"{result.get('pulled', 0) + result.get('pushed', 0)} files"})
        step += 1

    mc_dir = plan["mc_dir"]
    sync_dir = plan["sync_dir"]

    if plan["instance_task"] == "Exit Sync":
        emit({"type": "step", "step": step, "state": "running", "detail": "Scanning"})
        old_manifest = read_manifest(sync_dir)
        all_files = [(src, src.relative_to(mc_dir).as_posix())
                     for src in mc_dir.rglob("*") if src.is_file()]
        to_copy = [(src, rel) for src, rel in all_files if not is_blacklisted(rel)]
        emit({"type": "step", "step": step, "state": "ok", "detail": f"{len(to_copy)} files"})
        step += 1

        emit({"type": "step", "step": step, "state": "running", "detail": ""})
        copied, errors, new_manifest = 0, [], {}
        for src, rel in to_copy:
            dest = sync_dir / rel
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dest))
                new_manifest[rel] = _file_stat(dest)
                copied += 1
            except Exception as e:
                errors.append(f"{rel}: {e}")
        for stale_rel in set(old_manifest) - set(new_manifest):
            try:
                stale = sync_dir / stale_rel
                if stale.exists():
                    stale.unlink()
            except Exception as e:
                errors.append(f"prune {stale_rel}: {e}")
        write_manifest(sync_dir, new_manifest)
        _append_changelog(sync_dir.parent / ".changelog", {
            "instance": inst, "mode": "exit",
            "timestamp": datetime.utcnow().isoformat(),
            "copied": copied, "errors": errors,
        })
        emit({"type": "step", "step": step, "state": "error" if errors else "ok",
              "detail": f"{copied} copied"})
        step += 1

    elif plan["instance_task"] == "Startup Sync":
        from modules.instance_sync.sync import run_startup_sync
        emit({"type": "step", "step": step, "state": "running", "detail": ""})
        result = run_startup_sync(inst, plan["mc_dir"], plan["sync_dir"])
        errors = result.get("errors", [])
        emit({"type": "step", "step": step, "state": "error" if errors else "ok",
              "detail": f"{result.get('restored', 0)} files"})


def repair_hooks():
    if not is_instance_sync_configured():
        return
    cfg = get_instance_sync_config()
    enabled = [n for n, v in cfg.get("instances", {}).items() if v.get("enabled", False)]
    if enabled:
        patch_exit_commands(enabled, str(Path(__file__).resolve()), Path(cfg["instances_path"]))


# ---------------------------------------------------------------------------
# Api class — exposed to JS via pywebview
# ---------------------------------------------------------------------------

class Api:
    def __init__(self, window_ref: list):
        self._win = window_ref  # list so it's mutable before window is created
        self._update_choice = "skip"
        self._update_prompt_data = {}
        self._deletion_choice = "cancel"
        self._deletion_data = {}
        self._install_lock = threading.Lock()
        self._active_installs: set[str] = set()  # keys: "repo_id:pack_slug:version:instance_name"

    def _emit(self, event: dict) -> None:
        if self._win[0]:
            self._win[0].evaluate_js(f"window.__onProgress({json.dumps(event)})")

    def get_version(self) -> str:
        return VERSION

    # ── Home ──────────────────────────────────────────────────────────

    def get_home_data(self) -> dict:
        state = load_state()
        autosync = state.get("schematic_sync", {}).get("autosync_instances", [])
        inst_sync = state.get("instance_sync", {})
        instances_cfg = inst_sync.get("instances", {})
        defaults = inst_sync.get("defaults", {"exit_sync": True, "startup_sync": False})

        all_instances = sorted(
            d.name for d in INSTANCES_DIR.iterdir()
            if d.is_dir() and not d.name.endswith(".tmp")
        ) if INSTANCES_DIR.exists() else []

        rows = []
        for name in all_instances:
            inst_cfg = instances_cfg.get(name, {})
            eff = get_instance_effective_settings({"defaults": defaults, "instances": instances_cfg}, name) if is_instance_sync_configured() else {}
            rows.append({
                "name": name,
                "schematic_sync": name in autosync,
                "exit_sync": eff.get("exit_sync", False),
                "startup_sync": eff.get("startup_sync", False),
            })
        repos = get_pack_registry_repos()
        return {"instances": rows, "repos": repos, "instance_sync_configured": is_instance_sync_configured()}

    def sync_instance(self, name: str, mode: str) -> None:
        plan = _plan_instance(name, mode)
        def _run():
            self._emit({"type": "reset"})
            _execute_instance_plan(self._emit, name, plan)
            self._emit({"type": "summary", "text": "Sync complete.", "tone": "ok"})
        threading.Thread(target=_run, daemon=True).start()

    def sync_all(self, mode: str) -> None:
        state = load_state()
        instances = sorted(
            d.name for d in INSTANCES_DIR.iterdir()
            if d.is_dir() and not d.name.endswith(".tmp")
        ) if INSTANCES_DIR.exists() else []
        def _run():
            self._emit({"type": "reset"})
            for name in instances:
                plan = _plan_instance(name, mode)
                _execute_instance_plan(self._emit, name, plan)
            self._emit({"type": "summary", "text": "All synced.", "tone": "ok"})
        threading.Thread(target=_run, daemon=True).start()

    # ── Schematic Sync ────────────────────────────────────────────────

    def get_schematic_data(self) -> dict:
        state = load_state()
        autosync = state.get("schematic_sync", {}).get("autosync_instances", [])
        instances = sorted(
            d.name for d in INSTANCES_DIR.iterdir()
            if d.is_dir() and not d.name.endswith(".tmp")
        ) if INSTANCES_DIR.exists() else []
        return {"instances": instances, "autosync_instances": autosync}

    def set_autosync(self, name: str, enabled: bool) -> None:
        state = load_state()
        lst = state.setdefault("schematic_sync", {}).setdefault("autosync_instances", [])
        if enabled:
            if name not in lst:
                lst.append(name)
        else:
            state["schematic_sync"]["autosync_instances"] = [x for x in lst if x != name]
        save_state(state)

    def run_schematic_sync(self, name: str) -> None:
        from modules.schematic_sync.page import run_autosync
        def _run():
            self._emit({"type": "reset"})
            self._emit({"type": "step", "step": 0, "state": "running", "detail": ""})
            result = run_autosync([name])
            errors = result.get("errors", [])
            files = result.get("pulled", 0) + result.get("pushed", 0)
            self._emit({"type": "step", "step": 0,
                        "state": "error" if errors else "ok", "detail": f"{files} files"})
            tone = "error" if errors else "ok"
            self._emit({"type": "summary",
                        "text": f"Synced {files} files." if not errors else f"Errors: {errors[0]}",
                        "tone": tone})
        threading.Thread(target=_run, daemon=True).start()

    def get_schematic_counts(self, name: str) -> dict:
        from core.config import EXTENSIONS
        mc_dir = get_minecraft_dir(INSTANCES_DIR, name)
        counts = {ext: 0 for ext in EXTENSIONS}
        if mc_dir:
            for ext in EXTENSIONS:
                counts[ext] = len(list(mc_dir.rglob(f"*{ext}")))
        return counts

    # ── Instance Sync ─────────────────────────────────────────────────

    def get_instance_sync_data(self) -> dict:
        configured = is_instance_sync_configured()
        if not configured:
            cfg = get_instance_sync_config()
            return {
                "is_configured": False,
                "instances_path": cfg.get("instances_path") or "",
                "sync_path": cfg.get("sync_path") or "",
            }
        state = load_state()
        inst_sync = state.get("instance_sync", {})
        defaults = inst_sync.get("defaults", {"exit_sync": True, "startup_sync": False})
        sync_path = inst_sync.get("sync_path", "")
        instances_cfg = inst_sync.get("instances", {})
        all_instances = sorted(
            d.name for d in INSTANCES_DIR.iterdir()
            if d.is_dir() and not d.name.endswith(".tmp")
        ) if INSTANCES_DIR.exists() else []
        from modules.instance_sync.sync import read_last_result, read_manifest
        sync_path_str = inst_sync.get("sync_path", "")
        rows = []
        for name in all_instances:
            inst_cfg = instances_cfg.get(name, {})
            sync_dir = Path(sync_path_str) / "instance_sync" / name if sync_path_str else None
            last = read_last_result(sync_dir) if sync_dir else {}
            manifest = read_manifest(sync_dir) if sync_dir else {}
            synced_size = round(
                sum(v.get("size", 0) for v in manifest.values()) / 1_048_576, 1
            ) if manifest else 0.0
            rows.append({
                "name": name,
                "exit_sync": inst_cfg.get("exit_sync") if inst_cfg.get("exit_sync") is not None else defaults["exit_sync"],
                "startup_sync": inst_cfg.get("startup_sync") if inst_cfg.get("startup_sync") is not None else defaults.get("startup_sync", False),
                "enabled": inst_cfg.get("enabled", True),
                "last_exit_sync": last.get("timestamp") if last.get("mode") == "exit" else None,
                "last_startup_sync": last.get("timestamp") if last.get("mode") == "startup" else None,
                "last_errors": last.get("errors", []),
                "synced_size_mb": synced_size,
            })
        return {
            "is_configured": True,
            "defaults": defaults,
            "sync_path": sync_path,
            "instances": rows,
        }

    def setup_instance_sync(self, instances_path: str, sync_path: str) -> dict:
        """Save instances_path + sync_path and re-patch hooks for all currently enabled instances."""
        state = load_state()
        inst_sync = state.setdefault("instance_sync", {})
        inst_sync["instances_path"] = instances_path.strip()
        inst_sync["sync_path"] = sync_path.strip()
        save_state(state)
        repair_hooks()
        return {"ok": True}

    def get_archive_preflight(self, instance_name: str) -> dict:
        """Scan instance folder for size/file count and DistantHorizons LOD data."""
        from modules.instance_sync.sync import is_blacklisted
        cfg = get_instance_sync_config()
        instances_path = Path(cfg.get("instances_path") or str(INSTANCES_DIR))
        mc_dir = get_minecraft_dir(instances_path, instance_name)
        if not mc_dir or not mc_dir.exists():
            return {"folder_size_mb": 0, "file_count": 0, "dh_entries": []}

        total_size = 0
        file_count = 0
        for f in mc_dir.rglob("*"):
            if f.is_file() and not is_blacklisted(f.relative_to(mc_dir).as_posix()):
                try:
                    total_size += f.stat().st_size
                    file_count += 1
                except Exception:
                    pass

        dh_entries = []

        # Server LOD data: Distant_Horizons_server_data/<server_name>/
        dh_server_root = mc_dir / "Distant_Horizons_server_data"
        if dh_server_root.is_dir():
            for server_dir in sorted(dh_server_root.iterdir()):
                if server_dir.is_dir():
                    size = 0
                    for f in server_dir.rglob("*"):
                        if f.is_file():
                            try:
                                size += f.stat().st_size
                            except Exception:
                                pass
                    rel = "Distant_Horizons_server_data/" + server_dir.name
                    dh_entries.append({
                        "type": "server",
                        "name": server_dir.name,
                        "size_mb": round(size / 1_048_576, 1),
                        "path_rel": rel,
                    })

        # World LOD data: saves/<world_name>/data/DistantHorizons.sqlite (+ DIM variants)
        saves_root = mc_dir / "saves"
        if saves_root.is_dir():
            for world_dir in sorted(saves_root.iterdir()):
                if not world_dir.is_dir():
                    continue
                sqlite_paths = [
                    world_dir / "data" / "DistantHorizons.sqlite",
                    world_dir / "DIM-1" / "data" / "DistantHorizons.sqlite",
                    world_dir / "DIM1" / "data" / "DistantHorizons.sqlite",
                ]
                found = [p for p in sqlite_paths if p.exists()]
                if found:
                    try:
                        size = sum(p.stat().st_size for p in found)
                    except Exception:
                        size = 0
                    rel = "saves/" + world_dir.name
                    dh_entries.append({
                        "type": "world",
                        "name": world_dir.name,
                        "size_mb": round(size / 1_048_576, 1),
                        "path_rel": rel,
                    })

        return {
            "folder_size_mb": round(total_size / 1_048_576, 1),
            "file_count": file_count,
            "dh_entries": dh_entries,
        }

    def archive_instance(self, instance_name: str, dh_exclusions: dict | None = None) -> dict:
        """Kick off archive (sync + zip + delete) in a background thread. Emits archive_done progress event."""
        import threading

        def _run():
            import shutil, zipfile, time
            from modules.instance_sync.sync import is_blacklisted, write_manifest, _file_stat
            try:
                t0 = time.monotonic()
                cfg = get_instance_sync_config()
                instances_path = Path(cfg.get("instances_path") or str(INSTANCES_DIR))
                sync_path = Path(cfg.get("sync_path") or "")
                if not sync_path:
                    log.debug("[archive] emitting archive_done ok=%s", False)
                    self._emit_archive_done(False, "Sync path not configured.")
                    log.debug("[archive] emitted archive_done")
                    return
                inst_dir = instances_path / instance_name
                if not inst_dir.exists():
                    log.debug("[archive] emitting archive_done ok=%s", False)
                    self._emit_archive_done(False, f"Instance folder not found: {inst_dir}")
                    log.debug("[archive] emitted archive_done")
                    return
                mc_dir = get_minecraft_dir(instances_path, instance_name)
                sync_dir = sync_path / "instance_sync" / instance_name
                files_copied = 0
                synced_bytes = 0
                def _log(line):
                    log.debug("[archive] emitting %s prev_log=%r", {"type": "archive_log", "line": line}.get("type"), {"type": "archive_log", "line": line}.get("prev_log"))
                    self._emit_archive_event({"type": "archive_log", "line": line})
                    log.debug("[archive] emitted %s", "archive_log")
                def _secs(t): return f"{time.monotonic() - t:.1f}s"

                if mc_dir:
                    all_files = [(src, src.relative_to(mc_dir).as_posix())
                                 for src in mc_dir.rglob("*") if src.is_file()]
                    _sync_excl = (dh_exclusions or {}).get("exclude_from_sync", [])
                    to_copy = [
                        (src, rel) for src, rel in all_files
                        if not is_blacklisted(rel)
                        and not any(rel == p or rel.startswith(p.rstrip('/') + '/') for p in _sync_excl)
                    ]
                    log.debug("[archive] emitting %s prev_log=%r", "archive_step", None)
                    self._emit_archive_event({"type": "archive_step", "step": "Reading files…", "pct": 0})
                    log.debug("[archive] emitted %s", "archive_step")
                    t_read = time.monotonic()
                    total_bytes = sum(s.stat().st_size for s, _ in to_copy) or 1
                    log_read = f"Reading files...  {len(to_copy)} files  ({round(total_bytes / 1024 / 1024, 1)} MB)  [{_secs(t_read)}]"
                    log.debug("[archive] emitting archive_log")
                    self._emit_archive_event({"type": "archive_log", "line": log_read})
                    time.sleep(0.15)
                    log.debug("[archive] emitting %s prev_log=%r", "archive_step", None)
                    self._emit_archive_event({"type": "archive_step", "step": "Copying files…", "pct": 0})
                    log.debug("[archive] emitted %s", "archive_step")
                    t_copy = time.monotonic()
                    sync_dir.mkdir(parents=True, exist_ok=True)
                    new_manifest = {}
                    copied_bytes = 0
                    last_pct = 0
                    last_emit_t = 0.0
                    errors_copy = []
                    for src, rel in to_copy:
                        dest = sync_dir / rel
                        try:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(str(src), str(dest))
                            stat = _file_stat(dest)
                            new_manifest[rel] = stat
                            fsize = stat.get("size", 0)
                            synced_bytes += fsize
                            copied_bytes += fsize
                            files_copied += 1
                        except Exception as copy_err:
                            errors_copy.append(f"{rel}: {copy_err}")
                            log.warning("archive copy failed for %s: %s", rel, copy_err)
                        pct = min(99, int(copied_bytes / total_bytes * 100))
                        now = time.monotonic()
                        if pct != last_pct and (now - last_emit_t) >= 0.5:
                            log.debug("[archive] emitting %s prev_log=%r", "archive_progress", None)
                            self._emit_archive_event({"type": "archive_progress", "pct": pct})
                            log.debug("[archive] emitted %s", "archive_progress")
                            last_pct = pct
                            last_emit_t = now
                    write_manifest(sync_dir, new_manifest)
                    log_copy = f"Copying files...  {files_copied} files  ({round(synced_bytes / 1024 / 1024, 1)} MB)  [{_secs(t_copy)}]"
                else:
                    log_copy = None
                zip_name = f"{instance_name}.archive.zip"
                zip_path = instances_path / zip_name
                if log_copy:
                    log.debug("[archive] emitting archive_log")
                    self._emit_archive_event({"type": "archive_log", "line": log_copy})
                    time.sleep(0.15)
                log.debug("[archive] emitting %s prev_log=%r", "archive_step", None)
                self._emit_archive_event({"type": "archive_step", "step": "Creating zip archive…", "pct": 0})
                log.debug("[archive] emitted %s", "archive_step")
                t_zip = time.monotonic()
                _zip_excl = (dh_exclusions or {}).get("exclude_from_zip", [])
                def _zip_excluded(f: Path) -> bool:
                    if not _zip_excl or mc_dir is None:
                        return False
                    try:
                        rel = f.relative_to(mc_dir).as_posix()
                        return any(rel == p or rel.startswith(p.rstrip('/') + '/') for p in _zip_excl)
                    except ValueError:
                        log.warning("_zip_excluded: file %s is not under mc_dir %s, skipping exclusion check", f, mc_dir)
                        return False
                zip_files = [f for f in inst_dir.rglob("*") if f.is_file() and not _zip_excluded(f)]
                total_zip_bytes = sum(f.stat().st_size for f in zip_files) or 1
                zipped_bytes = 0
                last_pct = 0
                last_emit_t = 0.0
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for f in zip_files:
                        zf.write(f, f.relative_to(instances_path))
                        zipped_bytes += f.stat().st_size
                        pct = min(99, int(zipped_bytes / total_zip_bytes * 100))
                        now = time.monotonic()
                        if pct != last_pct and (now - last_emit_t) >= 0.5:
                            log.debug("[archive] emitting %s prev_log=%r", "archive_progress", None)
                            self._emit_archive_event({"type": "archive_progress", "pct": pct})
                            log.debug("[archive] emitted %s", "archive_progress")
                            last_pct = pct
                            last_emit_t = now
                zip_size_mb = round(zip_path.stat().st_size / 1024 / 1024, 1) if zip_path.exists() else 0
                log_zip = f"Creating zip archive...  {zip_size_mb} MB  [{_secs(t_zip)}]"
                log.debug("[archive] emitting archive_log")
                self._emit_archive_event({"type": "archive_log", "line": log_zip})
                time.sleep(0.15)
                log.debug("[archive] emitting %s prev_log=%r", "archive_step", None)
                self._emit_archive_event({"type": "archive_step", "step": "Removing instance folder…"})
                log.debug("[archive] emitted %s", "archive_step")
                t_rm = time.monotonic()
                shutil.rmtree(str(inst_dir))
                log.info("Archived instance %r to %s", instance_name, zip_path)
                summary_logs = [
                    f"Removing instance folder...  [{_secs(t_rm)}]",
                    f"",
                    f"Synced size: {round(synced_bytes / 1024 / 1024, 1)} MB",
                    f"Zip size:    {zip_size_mb} MB",
                    f"Destination: {sync_dir}",
                ]
                log.debug("[archive] emitting archive_done ok=%s", True)
                self._emit_archive_done(True, None, summary_logs)
                log.debug("[archive] emitted archive_done")
            except Exception as e:
                log.error("archive_instance failed for %r: %s", instance_name, e)
                log.debug("[archive] emitting archive_done ok=%s", False)
                self._emit_archive_done(False, str(e))
                log.debug("[archive] emitted archive_done")

        threading.Thread(target=_run, daemon=True).start()
        return {"ok": True, "started": True}

    def get_archived_instances(self) -> list:
        """Return archived instances — both zip-backed and move-only (sync folder only)."""
        cfg = get_instance_sync_config()
        instances_path = Path(cfg.get("instances_path") or str(INSTANCES_DIR))
        sync_path_str = cfg.get("sync_path") or ""
        results = {}
        if instances_path.exists():
            for p in instances_path.glob("*.archive.zip"):
                name = p.name.replace(".archive.zip", "")
                results[name] = {"name": name, "has_zip": True}
        if sync_path_str:
            sync_root = Path(sync_path_str) / "instance_sync"
            if sync_root.exists():
                for d in sync_root.iterdir():
                    if d.is_dir() and d.name not in results:
                        if not (instances_path / d.name).exists():
                            results[d.name] = {"name": d.name, "has_zip": False}
        return sorted(results.values(), key=lambda x: x["name"])

    def restore_instance(self, instance_name: str) -> dict:
        """Restore instance from sync folder back into Prism instances dir."""
        import shutil
        cfg = get_instance_sync_config()
        instances_path = Path(cfg.get("instances_path") or str(INSTANCES_DIR))
        sync_path_str = cfg.get("sync_path") or ""
        if not sync_path_str:
            return {"ok": False, "error": "Sync path not configured."}
        sync_dir = Path(sync_path_str) / "instance_sync" / instance_name
        if not sync_dir.exists():
            return {"ok": False, "error": f"No sync data found for {instance_name!r}"}

        inst_dir = instances_path / instance_name
        mc_dir = inst_dir / "minecraft"

        # Restore zip (instance.cfg, mmc-pack.json etc.) from archive zip if it exists
        zip_path = instances_path / f"{instance_name}.archive.zip"
        if zip_path.exists():
            import zipfile
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    # Only restore instance-level files (not minecraft/ contents)
                    rel = Path(member)
                    parts = rel.parts
                    if len(parts) >= 2 and parts[0] == instance_name:
                        inner = Path(*parts[1:])
                        if not str(inner).startswith("minecraft"):
                            dest = inst_dir / inner
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            with zf.open(member) as src, open(dest, "wb") as dst:
                                dst.write(src.read())

        # Restore minecraft/ contents from sync folder
        mc_dir.mkdir(parents=True, exist_ok=True)
        for src in sync_dir.rglob("*"):
            if src.is_file() and src.name != "manifest.json":
                rel = src.relative_to(sync_dir)
                dest = mc_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                import shutil as _shutil
                _shutil.copy2(str(src), str(dest))

        log.info("Restored instance %r from sync folder", instance_name)
        return {"ok": True, "has_zip": zip_path.exists(), "zip_path": str(zip_path)}

    def delete_archive_zip(self, instance_name: str) -> dict:
        """Delete the archive zip for an instance."""
        cfg = get_instance_sync_config()
        instances_path = Path(cfg.get("instances_path") or str(INSTANCES_DIR))
        zip_path = instances_path / f"{instance_name}.archive.zip"
        if zip_path.exists():
            zip_path.unlink()
            return {"ok": True}
        return {"ok": False, "error": "Zip not found."}

    def get_instance_detail(self, instance_name: str) -> dict:
        """Return sync detail and pack info for one instance. All reads are local — no network."""
        from modules.instance_sync.sync import read_last_result, read_manifest
        from core.state import get_tracked_packs

        cfg = get_instance_sync_config()
        sync_path = cfg.get("sync_path") or ""
        result = {
            "last_exit_sync": None,
            "last_startup_sync": None,
            "synced_file_count": 0,
            "synced_size_mb": 0.0,
            "last_exit_errors": [],
            "last_startup_errors": [],
            "instance_folder_size_mb": None,
            "pack": None,
        }

        if sync_path and is_instance_sync_configured():
            sync_dir = Path(sync_path) / "instance_sync" / instance_name
            last = read_last_result(sync_dir)
            if last.get("mode") == "exit":
                result["last_exit_sync"] = last.get("timestamp")
                result["last_exit_errors"] = last.get("errors", [])
            elif last.get("mode") == "startup":
                result["last_startup_sync"] = last.get("timestamp")
                result["last_startup_errors"] = last.get("errors", [])

            manifest = read_manifest(sync_dir)
            result["synced_file_count"] = len(manifest)
            result["synced_size_mb"] = round(
                sum(v.get("size", 0) for v in manifest.values()) / 1_048_576, 1
            )

        inst_dir = INSTANCES_DIR / instance_name
        if inst_dir.exists():
            try:
                total = sum(f.stat().st_size for f in inst_dir.rglob("*") if f.is_file())
                result["instance_folder_size_mb"] = round(total / 1_048_576, 1)
            except Exception:
                pass

        from core.state import get_installed_instances as _get_inst
        installed_map = {i["instance_name"]: i for i in _get_inst()}
        tracked_map = {t["instance_name"]: t for t in get_tracked_packs()}
        inst_record = installed_map.get(instance_name)
        if inst_record:
            tracked = tracked_map.get(instance_name)
            result["pack"] = {
                "name": inst_record.get("pack_name"),
                "installed_version": inst_record.get("installed_version"),
                "tracked": tracked is not None,
                "has_update": False,
                "latest_version": None,
            }

        return result

    def archive_instance_move_only(self, instance_name: str, dh_exclusions: dict | None = None) -> dict:
        """Kick off move-only archive (sync + delete, no zip) in a background thread. Emits archive_done event."""
        import threading

        def _run():
            import shutil, time
            from modules.instance_sync.sync import is_blacklisted, write_manifest, _file_stat
            try:
                t0 = time.monotonic()
                cfg = get_instance_sync_config()
                instances_path = Path(cfg.get("instances_path") or str(INSTANCES_DIR))
                sync_path = Path(cfg.get("sync_path") or "")
                if not sync_path:
                    log.debug("[archive] emitting archive_done ok=%s", False)
                    self._emit_archive_done(False, "Sync path not configured.")
                    log.debug("[archive] emitted archive_done")
                    return
                inst_dir = instances_path / instance_name
                if not inst_dir.exists():
                    log.debug("[archive] emitting archive_done ok=%s", False)
                    self._emit_archive_done(False, f"Instance folder not found: {inst_dir}")
                    log.debug("[archive] emitted archive_done")
                    return
                mc_dir = get_minecraft_dir(instances_path, instance_name)
                sync_dir = sync_path / "instance_sync" / instance_name
                files_copied = 0
                synced_bytes = 0
                def _log(line):
                    log.debug("[archive] emitting %s prev_log=%r", {"type": "archive_log", "line": line}.get("type"), {"type": "archive_log", "line": line}.get("prev_log"))
                    self._emit_archive_event({"type": "archive_log", "line": line})
                    log.debug("[archive] emitted %s", "archive_log")
                def _secs(t): return f"{time.monotonic() - t:.1f}s"

                if mc_dir:
                    all_files = [(src, src.relative_to(mc_dir).as_posix())
                                 for src in mc_dir.rglob("*") if src.is_file()]
                    _sync_excl = (dh_exclusions or {}).get("exclude_from_sync", [])
                    to_copy = [
                        (src, rel) for src, rel in all_files
                        if not is_blacklisted(rel)
                        and not any(rel == p or rel.startswith(p.rstrip('/') + '/') for p in _sync_excl)
                    ]
                    log.debug("[archive] emitting %s prev_log=%r", "archive_step", None)
                    self._emit_archive_event({"type": "archive_step", "step": "Reading files…", "pct": 0})
                    log.debug("[archive] emitted %s", "archive_step")
                    t_read = time.monotonic()
                    total_bytes = sum(s.stat().st_size for s, _ in to_copy) or 1
                    log_read = f"Reading files...  {len(to_copy)} files  ({round(total_bytes / 1024 / 1024, 1)} MB)  [{_secs(t_read)}]"
                    log.debug("[archive] emitting archive_log")
                    self._emit_archive_event({"type": "archive_log", "line": log_read})
                    time.sleep(0.15)
                    log.debug("[archive] emitting %s prev_log=%r", "archive_step", None)
                    self._emit_archive_event({"type": "archive_step", "step": "Moving files…", "pct": 0})
                    log.debug("[archive] emitted %s", "archive_step")
                    t_move = time.monotonic()
                    sync_dir.mkdir(parents=True, exist_ok=True)
                    new_manifest = {}
                    copied_bytes = 0
                    last_pct = 0
                    last_emit_t = 0.0
                    errors_copy = []
                    for src, rel in to_copy:
                        dest = sync_dir / rel
                        try:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(str(src), str(dest))
                            stat = _file_stat(dest)
                            new_manifest[rel] = stat
                            fsize = stat.get("size", 0)
                            synced_bytes += fsize
                            copied_bytes += fsize
                            files_copied += 1
                        except Exception as copy_err:
                            errors_copy.append(f"{rel}: {copy_err}")
                            log.warning("archive copy failed for %s: %s", rel, copy_err)
                        pct = min(99, int(copied_bytes / total_bytes * 100))
                        now = time.monotonic()
                        if pct != last_pct and (now - last_emit_t) >= 0.5:
                            log.debug("[archive] emitting %s prev_log=%r", "archive_progress", None)
                            self._emit_archive_event({"type": "archive_progress", "pct": pct})
                            log.debug("[archive] emitted %s", "archive_progress")
                            last_pct = pct
                            last_emit_t = now
                    write_manifest(sync_dir, new_manifest)
                    log_move = f"Moving files...  {files_copied} files  ({round(synced_bytes / 1024 / 1024, 1)} MB)  [{_secs(t_move)}]"
                else:
                    log_move = None
                if log_move:
                    log.debug("[archive] emitting archive_log")
                    self._emit_archive_event({"type": "archive_log", "line": log_move})
                    time.sleep(0.15)
                log.debug("[archive] emitting %s prev_log=%r", "archive_step", None)
                self._emit_archive_event({"type": "archive_step", "step": "Removing instance folder…"})
                log.debug("[archive] emitted %s", "archive_step")
                t_rm = time.monotonic()
                shutil.rmtree(str(inst_dir))
                log.info("Move-only archived instance %r (no zip)", instance_name)
                summary_logs = [
                    f"Removing instance folder...  [{_secs(t_rm)}]",
                    f"",
                    f"Synced size: {round(synced_bytes / 1024 / 1024, 1)} MB",
                    f"Destination: {sync_dir}",
                ]
                log.debug("[archive] emitting archive_done ok=%s", True)
                self._emit_archive_done(True, None, summary_logs)
                log.debug("[archive] emitted archive_done")
            except Exception as e:
                log.error("archive_instance_move_only failed for %r: %s", instance_name, e)
                log.debug("[archive] emitting archive_done ok=%s", False)
                self._emit_archive_done(False, str(e))
                log.debug("[archive] emitted archive_done")

        threading.Thread(target=_run, daemon=True).start()
        return {"ok": True, "started": True}

    def _emit_archive_event(self, payload: dict) -> None:
        self._emit(payload)

    def _emit_archive_done(self, ok: bool, error: str | None, logs: list | None = None) -> None:
        payload = {"type": "archive_done", "ok": ok}
        if error:
            payload["error"] = error
        if logs:
            payload["logs"] = logs
        self._emit_archive_event(payload)

    def get_skipped_version(self) -> str | None:
        from core.state import get_skipped_update_version
        return get_skipped_update_version()

    def skip_update_version(self, version: str) -> None:
        from core.state import set_skipped_update_version
        set_skipped_update_version(version)

    def get_update_stream_api(self) -> str:
        from core.state import get_update_stream
        return get_update_stream()

    def set_update_stream_api(self, stream: str) -> dict:
        from core.state import set_update_stream, VALID_STREAMS
        if stream not in VALID_STREAMS:
            return {"ok": False, "error": f"Invalid stream: {stream}"}
        try:
            set_update_stream(stream)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_gitlab_pat_api(self) -> str:
        from core.state import get_gitlab_pat
        return get_gitlab_pat() or ""

    def set_gitlab_pat_api(self, pat: str) -> None:
        from core.state import set_gitlab_pat
        set_gitlab_pat(pat.strip())

    def get_host_info(self) -> dict:
        import platform
        from core.config import VERSION, INSTANCES_DIR, STATEFILE
        return {
            "version": VERSION,
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "platform_version": platform.version(),
            "instances_dir": str(INSTANCES_DIR),
            "state_file": str(STATEFILE),
            "frozen": getattr(sys, "frozen", False),
        }

    def open_instances_folder(self) -> None:
        from core.config import INSTANCES_DIR
        import subprocess
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(INSTANCES_DIR)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(INSTANCES_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(INSTANCES_DIR)])
        except Exception as e:
            log.error("open_instances_folder failed: %s", e)

    def reset_module(self, module: str) -> dict:
        valid = {"schematic_sync", "instance_sync", "pack_registry"}
        if module not in valid:
            return {"ok": False, "error": f"Unknown module: {module}"}
        try:
            state = load_state()
            state.pop(module, None)
            save_state(state)
            log.info("reset_module: cleared state for %s", module)
            return {"ok": True}
        except Exception as e:
            log.error("reset_module failed for %s: %s", module, e)
            return {"ok": False, "error": str(e)}

    def get_instance_settings(self, instance_name: str) -> dict:
        from core.state import load_state
        state = load_state()

        # Instance sync toggles (dict keyed by name)
        is_cfg = state.get("instance_sync", {})
        inst = is_cfg.get("instances", {}).get(instance_name, {})

        # Schematic sync (list of name strings)
        sc_autosync = state.get("schematic_sync", {}).get("autosync_instances", [])
        schematic_sync = instance_name in sc_autosync

        # Tracked packs (list of dicts)
        tracked_packs = state.get("tracked_packs", [])
        tracked = any(t.get("instance_name") == instance_name for t in tracked_packs)

        # Installed instances (list of dicts)
        installed_instances = state.get("installed_instances", [])
        inst_installed = next((i for i in installed_instances if i.get("instance_name") == instance_name), None)
        pack_name = inst_installed.get("pack_name") if inst_installed else None

        return {
            "schematic_sync": schematic_sync,
            "exit_sync": bool(inst.get("exit_sync", False)),
            "startup_sync": bool(inst.get("startup_sync", False)),
            "hook_enabled": bool(inst.get("hook_enabled", False)),
            "tracked": tracked,
            "installed": inst_installed is not None,
            "pack_name": pack_name,
        }

    def save_instance_settings(self, instance_name: str, settings: dict) -> dict:
        from core.state import load_state, save_state
        from core.config import INSTANCES_DIR
        from core.prism import patch_exit_commands, clear_exit_commands
        try:
            state = load_state()

            # Schematic sync — list of name strings
            sc_cfg = state.setdefault("schematic_sync", {})
            sc_autosync = sc_cfg.setdefault("autosync_instances", [])
            if settings.get("schematic_sync"):
                if instance_name not in sc_autosync:
                    sc_autosync.append(instance_name)
            else:
                if instance_name in sc_autosync:
                    sc_autosync.remove(instance_name)

            # Instance sync toggles (dict keyed by name)
            is_cfg = state.setdefault("instance_sync", {})
            instances = is_cfg.setdefault("instances", {})
            inst = instances.setdefault(instance_name, {})
            inst["exit_sync"] = bool(settings.get("exit_sync", False))
            inst["startup_sync"] = bool(settings.get("startup_sync", False))

            # Hook
            hook_enabled = bool(settings.get("hook_enabled", False))
            inst["hook_enabled"] = hook_enabled
            main_script = Path(__file__).resolve()
            if hook_enabled:
                patch_exit_commands([instance_name], main_script, INSTANCES_DIR)
            else:
                clear_exit_commands([instance_name], INSTANCES_DIR)

            # Track for updates — list of dicts
            tracked_packs = state.setdefault("tracked_packs", [])
            installed_instances = state.get("installed_instances", [])
            already_tracked = next((i for i, t in enumerate(tracked_packs) if t.get("instance_name") == instance_name), None)
            if settings.get("tracked"):
                inst_info = next((i for i in installed_instances if i.get("instance_name") == instance_name), None)
                if inst_info and already_tracked is None:
                    tracked_packs.append(inst_info)
            else:
                if already_tracked is not None:
                    tracked_packs.pop(already_tracked)

            save_state(state)
            log.info("save_instance_settings: saved settings for %s", instance_name)
            return self.get_instance_settings(instance_name)
        except Exception as e:
            log.error("save_instance_settings failed for %s: %s", instance_name, e)
            return {"error": str(e)}

    def log_js_error(self, level: str, message: str) -> None:
        js_log = logging.getLogger("js")
        lvl = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }.get(str(level).lower(), logging.ERROR)
        js_log.log(lvl, message)



    def create_debug_dump(self) -> dict:
        import zipfile
        import json as _json
        from datetime import datetime

        try:
            if sys.platform == "win32":
                log_dir = pathlib.Path(os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA", "."))) / "MCAddonCompanion" / "logs"
                state_path = pathlib.Path(os.environ.get("APPDATA", ".")) / "MCAddonCompanion" / "state.json"
            else:
                xdg = os.environ.get("XDG_DATA_HOME", str(pathlib.Path.home() / ".local/share"))
                log_dir = pathlib.Path(xdg) / "MCAddonCompanion" / "logs"
                state_path = log_dir.parent / "state.json"

            # Dev mode: prefer local state.json next to main.py
            local_state = Path(__file__).parent / "state.json"
            if local_state.exists():
                state_path = local_state

            downloads = Path.home() / "Downloads"
            downloads.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            zip_name = f"mcaddoncompanion-debug-{ts}.zip"
            zip_path = downloads / zip_name

            def _redact(obj):
                if isinstance(obj, dict):
                    return {
                        k: "***" if any(s in k.lower() for s in ("pat", "token", "secret", "password"))
                        else _redact(v)
                        for k, v in obj.items()
                    }
                if isinstance(obj, list):
                    return [_redact(i) for i in obj]
                return obj

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Logs
                if log_dir.exists():
                    for f in log_dir.iterdir():
                        if f.is_file():
                            zf.write(f, f"logs/{f.name}")

                # Redacted state
                if state_path.exists():
                    try:
                        raw = _json.loads(state_path.read_text(encoding="utf-8"))
                        redacted = _redact(raw)
                        zf.writestr("state_redacted.json", _json.dumps(redacted, indent=2))
                    except Exception as e:
                        zf.writestr("state_redacted.json", _json.dumps({"error": str(e)}))

                # System info
                info = self.get_host_info()
                info["dump_timestamp"] = datetime.now().isoformat()
                zf.writestr("system_info.json", _json.dumps(info, indent=2))

            log.info("Debug dump created: %s", zip_path)

            # Open Downloads folder
            try:
                import subprocess
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", str(downloads)])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(downloads)])
                else:
                    subprocess.Popen(["xdg-open", str(downloads)])
            except Exception as e:
                log.warning("Could not open Downloads folder: %s", e)

            return {"ok": True, "filename": zip_name}

        except Exception as e:
            log.error("create_debug_dump failed: %s", e)
            return {"ok": False, "error": str(e)}

    def set_instance_default(self, key: str, value: bool) -> None:
        state = load_state()
        state.setdefault("instance_sync", {}).setdefault("defaults", {})[key] = value
        save_state(state)

    def set_instance_override(self, name: str, key: str, value: bool) -> None:
        state = load_state()
        state.setdefault("instance_sync", {}).setdefault("instances", {}).setdefault(name, {})[key] = value
        save_state(state)

    # ── Pack Registry ─────────────────────────────────────────────────

    def get_repos(self) -> list:
        return get_pack_registry_repos()

    def save_repo(self, repo: dict) -> dict:
        import urllib.request, urllib.error
        from urllib.parse import urlparse
        url = repo.get("url", "").strip()
        pat = repo.get("pat_token", "").strip()
        deploy_token = repo.get("deploy_token", "").strip()
        name = repo.get("name", "").strip()
        pkg = ""  # no longer used — packs are named individually per publish
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        project_path = parsed.path.strip("/").replace("/", "%2F")
        api_url = f"{base_url}/api/v4/projects/{project_path}"

        # Try with PAT first if provided, then fall back to unauthenticated (public projects)
        headers = {"PRIVATE-TOKEN": pat} if pat else {}
        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 401 and not pat:
                raise ValueError("This project requires a Personal Access Token (project is private or auth is required).")
            elif e.code == 401:
                raise ValueError("Authentication failed — check your Personal Access Token.")
            elif e.code == 404:
                raise ValueError(f"Project not found at: {url}\nVerify the URL is correct and the project exists.")
            raise ValueError(f"GitLab API error {e.code}: {e.reason}")

        project_id = str(data["id"])
        repos = get_pack_registry_repos()
        rid = repo.get("id") or make_repo_id()
        repo_obj = {
            "id": rid, "name": name, "base_url": base_url,
            "project_url": url,
            "project_id": project_id,
            "upload_token": deploy_token,  # deploy token — write_package_registry scope
            "read_token": pat,             # PAT — api scope for listing
        }
        existing_ids = [r["id"] for r in repos]
        if rid in existing_ids:
            repos = [repo_obj if r["id"] == rid else r for r in repos]
        else:
            repos.append(repo_obj)
        save_pack_registry_repos(repos)
        return repo_obj

    def delete_repo(self, repo_id: str) -> None:
        repos = [r for r in get_pack_registry_repos() if r["id"] != repo_id]
        save_pack_registry_repos(repos)

    def get_packs(self, repo_id: str) -> list:
        from core.gitlab import GitLabClient
        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            return []
        client = GitLabClient(repo["base_url"], repo["project_id"],
                              repo.get("upload_token"), repo.get("read_token"))
        packages = client.list_all_packages()
        return sorted(set(p["name"] for p in packages if isinstance(p, dict)))

    def get_instance_mod_files(self, inst_name: str) -> list:
        """Return sorted list of .jar filenames from the instance's mods/ folder."""
        mc_dir = get_minecraft_dir(INSTANCES_DIR, inst_name)
        if not mc_dir:
            return []
        mods_dir = mc_dir / "mods"
        if not mods_dir.exists():
            return []
        return sorted(f.name for f in mods_dir.glob("*.jar"))

    def get_versions(self, repo_id: str, pack_name: str) -> list:
        from core.gitlab import GitLabClient
        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            return []
        client = GitLabClient(repo["base_url"], repo["project_id"],
                              repo.get("upload_token"), repo.get("read_token"))
        return client.get_versions_with_metadata(pack_name)

    def check_conflicts(self, repo_id: str, pack_name: str, version: str, inst_name: str) -> list:
        """Return list of relative paths that differ between the pack and the local instance.

        Uses metadata.json to enumerate pack files, then compares only files that already
        exist locally — no zip download required.
        """
        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            return []
        from core.gitlab import GitLabClient
        client = GitLabClient(repo["base_url"], repo["project_id"],
                              repo.get("upload_token"), repo.get("read_token"))
        slug = _slugify(pack_name)
        meta = client.get_metadata(slug, version)
        # Build list of pack-relative paths from metadata categories
        pack_paths: list[str] = []
        categories = meta.get("categories", [])
        for cat in categories:
            pack_paths.append(cat + "/")  # directory prefix — files under this folder conflict
        # Mods are enumerated explicitly in metadata
        for mod in meta.get("mods", []):
            if isinstance(mod, dict):
                pack_paths.append(f"mods/{mod['file']}")

        mc_dir = get_minecraft_dir(INSTANCES_DIR, inst_name)
        if not mc_dir:
            mc_dir = INSTANCES_DIR / inst_name / "minecraft"

        conflicts = []
        for rel in pack_paths:
            if rel.endswith("/"):
                # Category directory — flag any existing files inside it
                folder = mc_dir / rel.rstrip("/")
                if folder.is_dir():
                    for f in folder.iterdir():
                        if f.is_file():
                            conflicts.append(str(Path(rel.rstrip("/")) / f.name).replace("\\", "/"))
            else:
                dest = mc_dir / Path(rel)
                if dest.exists():
                    conflicts.append(rel)
        return conflicts

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
            self._emit({"type": "summary", "flow": "publish", "text": "Pack name is required.", "tone": "error"})
            return
        if not version:
            self._emit({"type": "summary", "flow": "publish", "text": "Version is required.", "tone": "error"})
            return

        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            self._emit({"type": "summary", "flow": "publish", "text": "Repo not found.", "tone": "error"})
            return

        mc_dir = get_minecraft_dir(INST_DIR, inst_name)
        if not mc_dir:
            self._emit({"type": "summary", "flow": "publish", "text": "Instance not found.", "tone": "error"})
            return

        slug = _slugify(pack_name)

        def _run():
            try:
                self._emit({"type": "reset", "flow": "publish"})
                instance_dir = INST_DIR / inst_name
                file_list = get_export_file_list(mc_dir, categories, [])

                # Build mods list and filter excluded mods from file_list
                mods = []
                excluded_mods: set[Path] = set()
                if categories.get("mods"):
                    mods_dir = mc_dir / "mods"
                    if mods_dir.exists():
                        for jar in sorted(mods_dir.glob("*.jar")):
                            if jar.name not in mod_tags:
                                excluded_mods.add(jar)
                                continue  # excluded by user
                            side = mod_tags[jar.name]
                            mods.append({"name": jar.stem, "file": jar.name, "side": side})
                file_list = [f for f in file_list if f not in excluded_mods]

                # Compute removed_mods vs previous version
                client = GitLabClient(repo["base_url"], repo["project_id"],
                                      repo.get("upload_token"), repo.get("read_token"))
                removed_mods = []
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
                    "loader_version": params.get("loader_version", ""),
                    "description": params.get("description", ""),
                    "changenotes": changenotes,
                    "categories": [k for k, v in categories.items() if v],
                    "mods": mods,
                    "removed_mods": removed_mods,
                }

                self._emit({"type": "step", "flow": "publish", "step": 0, "state": "running", "detail": ""})
                with tempfile.TemporaryDirectory() as tmp:
                    zip_path = Path(tmp) / zip_filename
                    def _zip_progress(done, total):
                        if total:
                            pct = min(int(done * 100 / total), 99)
                            self._emit({"type": "progress", "flow": "publish", "step": 0, "pct": pct})
                    build_export_zip(inst_name, mc_dir, instance_dir, file_list, zip_path,
                                     on_progress=_zip_progress)
                    size_mb = zip_path.stat().st_size / 1_048_576
                    self._emit({"type": "step", "flow": "publish", "step": 0, "state": "ok", "detail": f"{size_mb:.1f} MB"})

                    self._emit({"type": "step", "flow": "publish", "step": 1, "state": "running", "detail": ""})
                    def _upload_progress(sent, total):
                        if total:
                            pct = min(int(sent * 100 / total), 99)
                            self._emit({"type": "progress", "flow": "publish", "step": 1, "pct": pct})
                    client.upload_file_path(slug, version, zip_filename, zip_path,
                                            on_progress=_upload_progress)
                    self._emit({"type": "step", "flow": "publish", "step": 1, "state": "ok", "detail": ""})

                    self._emit({"type": "step", "flow": "publish", "step": 2, "state": "running", "detail": ""})
                    client.upload_file(slug, version, "metadata.json",
                                       _json.dumps(metadata, indent=2).encode(),
                                       content_type="application/json")
                    self._emit({"type": "step", "flow": "publish", "step": 2, "state": "ok", "detail": ""})

                self._emit({"type": "summary", "flow": "publish",
                            "text": f"Published {pack_name} v{version}.",
                            "tone": "ok"})
            except Exception as e:
                self._emit({"type": "summary", "flow": "publish", "text": f"Error: {e}", "tone": "error"})

        threading.Thread(target=_run, daemon=True).start()

    def install_pack(self, params: dict) -> None:
        import urllib.request, urllib.error, zipfile, io, json as _json

        repo_id = params["repo_id"]
        pack_name = params["pack_name"]
        version = params["version"]
        inst_name = params["instance_name"]
        mode = params.get("mode", "new")   # "new" or "existing"
        track = params.get("track", False)
        skip_files: set = set(params.get("skip_files", []))  # rel paths to skip overwriting
        excluded_mods: set = set(params.get("excluded_mods", []))  # mod filenames to skip

        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            self._emit({"type": "summary", "flow": "install", "text": "Repo not found.", "tone": "error"})
            return

        slug = _slugify(pack_name)
        install_key = f"{repo_id}:{slug}:{version}:{inst_name}"

        with self._install_lock:
            if install_key in self._active_installs:
                self._emit({"type": "summary", "flow": "install",
                            "text": "Install already in progress for this pack.", "tone": "error"})
                return
            self._active_installs.add(install_key)

        def _run():
            try:
                self._emit({"type": "reset", "flow": "install"})
                from core.gitlab import GitLabClient
                client = GitLabClient(repo["base_url"], repo["project_id"],
                                      repo.get("upload_token"), repo.get("read_token"))

                # Step 0: Download zip
                self._emit({"type": "step", "flow": "install", "step": 0, "state": "running", "detail": ""})
                zip_filename = f"{slug}-{version}.zip"
                url = client.build_download_url(slug, version, zip_filename)
                req = urllib.request.Request(url)
                req.add_header("User-Agent", "MCAddonCompanion")
                if repo.get("read_token"):
                    req.add_header("PRIVATE-TOKEN", repo["read_token"])
                with urllib.request.urlopen(req, timeout=120) as resp:
                    total_bytes = int(resp.headers.get("Content-Length") or 0)
                    chunks = []
                    received = 0
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        received += len(chunk)
                        if total_bytes:
                            pct = min(int(received * 100 / total_bytes), 99)
                            self._emit({"type": "progress", "flow": "install", "step": 0, "pct": pct})
                    data = b"".join(chunks)

                # Validate: size must match Content-Length (if provided) and start with ZIP magic bytes
                if total_bytes and received != total_bytes:
                    raise ValueError(
                        f"Download incomplete: expected {total_bytes} bytes, got {received}. "
                        "Try again — the server may have returned a partial response."
                    )
                if not data[:2] == b"PK":
                    raise ValueError(
                        f"Downloaded file is not a valid zip (got {len(data)} bytes, "
                        f"starts with {data[:4]!r}). The server may have returned an error page."
                    )

                size_mb = len(data) / 1_048_576
                self._emit({"type": "step", "flow": "install", "step": 0, "state": "ok", "detail": f"{size_mb:.1f} MB"})

                # Fetch metadata for removed_mods and instance files
                meta = client.get_metadata(slug, version)
                removed_mods = meta.get("removed_mods", [])

                # Step 1: Extract
                self._emit({"type": "step", "flow": "install", "step": 1, "state": "running", "detail": ""})
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
                    eligible = [
                        m for m in members
                        if not m.endswith("/")
                        and (m[len(prefix):] if prefix else m) not in skip_files
                        and not (excluded_mods and (m[len(prefix):] if prefix else m).startswith("mods/")
                                 and Path((m[len(prefix):] if prefix else m)).name in excluded_mods)
                    ]
                    total_files = len(eligible)
                    count = 0
                    for member in members:
                        if member.endswith("/"):
                            continue
                        rel = member[len(prefix):] if prefix else member
                        if rel in skip_files:
                            continue
                        if excluded_mods and rel.startswith("mods/") and Path(rel).name in excluded_mods:
                            continue
                        dest = mc_dir / Path(rel)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        count += 1
                        if total_files and (count % 10 == 0 or count == total_files):
                            pct = min(int(count * 100 / total_files), 99)
                            self._emit({"type": "progress", "flow": "install", "step": 1, "pct": pct})
                self._emit({"type": "step", "flow": "install", "step": 1, "state": "ok", "detail": f"{count} files"})

                # Step 2: Write Prism instance files (only for new instances)
                self._emit({"type": "step", "flow": "install", "step": 2, "state": "running", "detail": ""})
                if mode == "new":
                    mc_ver = meta.get("mc_version", "")
                    loader = meta.get("loader", "fabric")
                    loader_version = meta.get("loader_version", "")
                    cfg_path = inst_dir / "instance.cfg"
                    if not cfg_path.exists():
                        cfg_path.write_text(
                            f"[General]\nConfigVersion=1.2\nInstanceType=OneSix\nname={inst_name}\n",
                            encoding="utf-8"
                        )
                    mmc_path = inst_dir / "mmc-pack.json"
                    if not mmc_path.exists():
                        loader_norm = loader.lower()
                        if loader_norm == "fabric":
                            uid = "net.fabricmc.fabric-loader"
                        elif loader_norm in ("neoforge", "neoforged"):
                            uid = "net.neoforged"
                        else:
                            uid = "net.minecraftforge"
                        loader_comp = {"uid": uid}
                        if loader_version:
                            loader_comp["version"] = loader_version
                        mmc_pack = {
                            "components": [
                                {"important": True, "uid": "net.minecraft", "version": mc_ver},
                                loader_comp,
                            ],
                            "formatVersion": 1,
                        }
                        mmc_path.write_text(_json.dumps(mmc_pack, indent=2), encoding="utf-8")
                self._emit({"type": "step", "flow": "install", "step": 2, "state": "ok", "detail": ""})

                # Always record install; optionally track for updates
                from core.state import add_tracked_pack
                save_installed_instance({
                    "instance_name": inst_name,
                    "repo_id": repo_id,
                    "pack_name": pack_name,
                    "pack_slug": slug,
                    "installed_version": version,
                })
                if track:
                    add_tracked_pack({
                        "instance_name": inst_name,
                        "repo_id": repo_id,
                        "pack_name": pack_name,
                        "pack_slug": slug,
                        "installed_version": version,
                    })

                self._emit({"type": "summary", "flow": "install", "text": f"Installed {pack_name} v{version}.", "tone": "ok"})
            except Exception as e:
                self._emit({"type": "summary", "flow": "install", "text": f"Error: {e}", "tone": "error"})
            finally:
                with self._install_lock:
                    self._active_installs.discard(install_key)

        threading.Thread(target=_run, daemon=True).start()

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

    def set_instance_hook(self, instance_name: str, enabled: bool) -> dict:
        """Patch or clear PreLaunchCommand/PostExitCommand for a single instance."""
        cfg = get_instance_sync_config()
        instances_path = cfg.get("instances_path")
        if not instances_path:
            instances_path = str(INSTANCES_DIR)
        inst_dir = Path(instances_path)
        if enabled:
            patched, already, errors = patch_exit_commands(
                [instance_name], Path(__file__).resolve(), inst_dir
            )
            return {"ok": not errors, "errors": errors}
        else:
            cleared, errors = clear_exit_commands([instance_name], inst_dir)
            return {"ok": not errors, "errors": errors}

    def get_hook_status(self, instance_name: str) -> bool:
        """Return True if PreLaunchCommand is set for this instance."""
        cfg = get_instance_sync_config()
        instances_path = cfg.get("instances_path") or str(INSTANCES_DIR)
        cfg_path = Path(instances_path) / instance_name / "instance.cfg"
        if not cfg_path.exists():
            return False
        text = cfg_path.read_text(encoding="utf-8")
        return "--startup" in text and "PreLaunchCommand=" in text

    def remove_installed_instance(self, instance_name: str) -> None:
        from core.state import remove_tracked_pack
        state = load_state()
        state["installed_instances"] = [
            i for i in state.get("installed_instances", [])
            if i.get("instance_name") != instance_name
        ]
        save_state(state)
        remove_tracked_pack(instance_name)

    def get_installed_instances(self) -> list:
        """Return local state immediately — no network calls. Use get_instance_update_status for update info."""
        from core.state import get_installed_instances, get_tracked_packs
        installed = get_installed_instances()
        tracked_map = {t["instance_name"]: t for t in get_tracked_packs()}
        result = []
        for entry in installed:
            repo = get_repo_by_id(entry["repo_id"])
            tracked = tracked_map.get(entry["instance_name"])
            prism_exists = (INSTANCES_DIR / entry["instance_name"]).is_dir()
            hook_enabled = self.get_hook_status(entry["instance_name"])
            result.append({
                **entry,
                "repo_name": repo["name"] if repo else None,
                "tracked": tracked is not None,
                "has_update": False,
                "latest_version": None,
                "prism_exists": prism_exists,
                "hook_enabled": hook_enabled,
            })
        return result

    def get_instance_update_status(self) -> list:
        """Check GitLab for latest versions. Called async after initial render. Returns [{instance_name, has_update, latest_version}]."""
        from core.state import get_installed_instances
        from core.gitlab import GitLabClient
        installed = get_installed_instances()
        # Deduplicate by (repo_id, pack_slug) to minimise API calls
        seen: dict[tuple, str] = {}
        for entry in installed:
            key = (entry["repo_id"], entry["pack_slug"])
            if key not in seen:
                repo = get_repo_by_id(entry["repo_id"])
                if repo:
                    try:
                        client = GitLabClient(repo["base_url"], repo["project_id"],
                                             repo.get("upload_token"), repo.get("read_token"))
                        seen[key] = client.get_latest_version(entry["pack_slug"]) or ""
                    except Exception:
                        seen[key] = ""
                else:
                    seen[key] = ""
        result = []
        for entry in installed:
            key = (entry["repo_id"], entry["pack_slug"])
            latest = seen.get(key, "")
            result.append({
                "instance_name": entry["instance_name"],
                "has_update": bool(latest and latest != entry["installed_version"]),
                "latest_version": latest or None,
            })
        return result

    def read_instance_meta(self, inst_name: str) -> dict:
        try:
            mmc = INSTANCES_DIR / inst_name / "mmc-pack.json"
            if mmc.exists():
                data = json.loads(mmc.read_text(encoding="utf-8"))
                mc_ver = next((c["version"] for c in data.get("components", [])
                               if c.get("uid") == "net.minecraft"), "")
                loader_comp = next((c for c in data.get("components", [])
                               if c.get("uid", "").startswith("net.") and "minecraft" not in c.get("uid", "")), None)
                loader = loader_comp["uid"].split(".")[-1] if loader_comp else ""
                loader_version = loader_comp.get("version") or loader_comp.get("cachedVersion", "") if loader_comp else ""
                return {"mc_version": mc_ver, "loader": loader, "loader_version": loader_version}
        except Exception:
            pass
        return {"mc_version": "", "loader": "", "loader_version": ""}

    def get_latest_pack_metadata(self, repo_id: str, pack_name: str) -> dict:
        """Return metadata.json for the latest version of pack_name, or {} if none."""
        from core.gitlab import GitLabClient
        repo = get_repo_by_id(repo_id)
        if not repo:
            return {}
        try:
            client = GitLabClient(repo["base_url"], repo["project_id"],
                                  repo.get("upload_token"), repo.get("read_token"))
            slug = _slugify(pack_name)
            latest = client.get_latest_version(slug)
            if not latest:
                return {}
            return client.get_metadata(slug, latest)
        except Exception:
            return {}

    def get_all_instances(self) -> list:
        if not INSTANCES_DIR.exists():
            return []
        return sorted(d.name for d in INSTANCES_DIR.iterdir()
                      if d.is_dir() and not d.name.endswith(".tmp"))

    # ── Updater ───────────────────────────────────────────────────────

    def check_update(self) -> dict | None:
        try:
            from core.updater import check_for_update
            return check_for_update()
        except Exception as e:
            log.warning("Update check failed: %s", e)
            return None

    def dismiss_update(self) -> None:
        pass  # future: persist dismissed version to state

    def start_app_update(self, download_url: str, pat: str | None = None) -> None:
        """Download and install app update. Emits progress events then relaunches."""
        from core.updater import download_update, install_update

        def _run():
            self._emit({"type": "app_update", "state": "downloading", "pct": 0})
            def _progress(downloaded, total):
                pct = int(downloaded * 100 / total) if total else 0
                self._emit({"type": "app_update", "state": "downloading", "pct": pct})

            path = download_update(download_url, _progress, pat=pat)
            if not path:
                self._emit({"type": "app_update", "state": "error", "pct": 0})
                return
            self._emit({"type": "app_update", "state": "installing", "pct": 100})
            install_update(path)
            self._emit({"type": "app_update", "state": "done", "pct": 100})
            import time; time.sleep(1)
            sys.exit(0)

        threading.Thread(target=_run, daemon=True).start()

    def get_update_prompt_data(self) -> dict:
        """Called by update_prompt.js on load. Returns tracked pack update info."""
        return getattr(self, "_update_prompt_data", {})

    def submit_update_choice(self, choice: str) -> None:
        """Called by update_prompt.js when user clicks Update or Skip (or countdown expires).
        choice: 'update' | 'skip'
        """
        self._update_choice = choice
        win = self._win[0] if self._win else None
        if win:
            import threading
            threading.Timer(0.1, win.destroy).start()

    def get_deletion_data(self) -> dict:
        return self._deletion_data

    def set_deletion_choice(self, choice: str) -> None:
        self._deletion_choice = choice
        win = self._win[0] if self._win else None
        if win:
            import threading
            threading.Timer(0.1, win.destroy).start()

    def pick_folder(self) -> str | None:
        import webview as _webview
        result = _webview.windows[0].create_file_dialog(_webview.FOLDER_DIALOG)
        if result:
            return result[0]
        return None

    def get_downloads_folder(self) -> str:
        return str(Path.home() / "Downloads")

    def download_server_pack(self, params: dict) -> None:
        import urllib.request, zipfile, io as _io
        from core.gitlab import GitLabClient

        repo_id = params["repo_id"]
        pack_name = params["pack_name"]
        version = params["version"]
        dest_folder = Path(params["dest_folder"])
        as_zip = params.get("as_zip", True)
        include_config = params.get("include_config", True)

        repos = get_pack_registry_repos()
        repo = next((r for r in repos if r["id"] == repo_id), None)
        if not repo:
            self._emit({"type": "server_pack", "step": 0, "state": "error", "detail": "Repo not found."})
            self._emit({"type": "server_pack_summary", "text": "Repo not found.", "tone": "error"})
            return

        slug = _slugify(pack_name)

        def _run():
            _step = [0]
            try:
                # Step 0: Download zip
                _step[0] = 0
                self._emit({"type": "server_pack", "step": 0, "state": "running", "detail": ""})
                client = GitLabClient(repo["base_url"], repo["project_id"],
                                      repo.get("upload_token"), repo.get("read_token"))
                zip_filename = f"{slug}-{version}.zip"
                url = client.build_download_url(slug, version, zip_filename)
                req = urllib.request.Request(url)
                req.add_header("User-Agent", "MCAddonCompanion")
                if repo.get("read_token"):
                    req.add_header("PRIVATE-TOKEN", repo["read_token"])
                with urllib.request.urlopen(req, timeout=120) as resp:
                    total_bytes = int(resp.headers.get("Content-Length") or 0)
                    chunks = []
                    received = 0
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        received += len(chunk)
                        if total_bytes:
                            pct = min(int(received * 100 / total_bytes), 99)
                            self._emit({"type": "server_pack_progress", "step": 0, "pct": pct})
                    data = b"".join(chunks)
                size_mb = len(data) / 1_048_576
                self._emit({"type": "server_pack", "step": 0, "state": "ok", "detail": f"{size_mb:.1f} MB"})

                # Step 1: Filter content
                _step[0] = 1
                self._emit({"type": "server_pack", "step": 1, "state": "running", "detail": ""})
                meta = client.get_metadata(slug, version)
                server_mods: set[str] = set()
                for m in meta.get("mods", []):
                    if isinstance(m, dict) and m.get("side") in ("required", "server"):
                        server_mods.add(m["file"])

                EXCLUDED_PREFIXES = ("saves/", "shaderpacks/", "resourcepacks/")

                filtered: list[tuple[str, bytes]] = []
                with zipfile.ZipFile(_io.BytesIO(data)) as zf:
                    members = zf.namelist()
                    has_mc_prefix = any(m.startswith(".minecraft/") for m in members)
                    has_plain_prefix = any(m.startswith("minecraft/") for m in members)
                    prefix = ".minecraft/" if has_mc_prefix else ("minecraft/" if has_plain_prefix else "")
                    for member in members:
                        if member.endswith("/"):
                            continue
                        bare = member[len(prefix):] if prefix else member
                        if bare in ("instance.cfg", "mmc-pack.json"):
                            continue
                        if any(bare.startswith(p) for p in EXCLUDED_PREFIXES):
                            continue
                        if bare.startswith("config/") and not include_config:
                            continue
                        if bare.startswith("mods/"):
                            mod_name = Path(bare).name
                            if mod_name not in server_mods:
                                continue
                        filtered.append((bare, zf.read(member)))

                if not filtered:
                    raise ValueError("No files passed the server filter — check metadata mods list.")

                self._emit({"type": "server_pack", "step": 1, "state": "ok",
                            "detail": f"{len(filtered)} files"})

                # Step 2: Write to destination
                _step[0] = 2
                self._emit({"type": "server_pack", "step": 2, "state": "running", "detail": ""})
                dest_folder.mkdir(parents=True, exist_ok=True)
                output_name = f"{slug}-{version}-server"

                if as_zip:
                    out_path = dest_folder / f"{output_name}.zip"
                    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
                        for rel, content in filtered:
                            out_zf.writestr(rel, content)
                    result_path = str(out_path)
                else:
                    out_dir = dest_folder / output_name
                    out_dir.mkdir(parents=True, exist_ok=True)
                    for rel, content in filtered:
                        dest_file = out_dir / Path(rel)
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        dest_file.write_bytes(content)
                    result_path = str(out_dir)

                self._emit({"type": "server_pack", "step": 2, "state": "ok", "detail": ""})
                self._emit({"type": "server_pack_summary", "text": result_path, "tone": "ok"})

            except Exception as e:
                self._emit({"type": "server_pack", "step": _step[0], "state": "error", "detail": str(e)})
                self._emit({"type": "server_pack_summary", "text": f"Error: {e}", "tone": "error"})

        threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _run_deletion_prompt(instance_name: str, deletions: list[str], mode: str = "exit") -> str:
    """Open a PyWebView window listing deleted/missing files.
    mode='exit': files deleted from instance before exit sync.
    mode='startup': files missing from instance that startup sync would restore.
    Returns 'restore' | 'delete' | 'cancel' (exit) or 'restore' | 'keep' | 'cancel' (startup).
    """
    win_ref: list = [None]
    api = Api(win_ref)
    api._deletion_data = {
        "instance": instance_name,
        "deleted": deletions,
        "timeout": 30,
        "mode": mode,
    }
    api._deletion_choice = "cancel"

    title = f"Restore files? - {instance_name}" if mode == "startup" else f"Sync deletions? - {instance_name}"
    frontend_dir = Path(__file__).parent / "frontend"
    window = webview.create_window(
        title,
        url=str(frontend_dir / "index.html") + "?mode=deletion_prompt",
        js_api=api,
        width=480,
        height=440,
        resizable=False,
    )
    win_ref[0] = window
    webview.start(debug=not getattr(sys, "frozen", False))
    return api._deletion_choice



def _headless_autosync(name: str) -> None:
    from modules.instance_sync.sync import read_manifest, _check_deletions
    instances = [d.name for d in INSTANCES_DIR.iterdir() if d.is_dir()] if INSTANCES_DIR.exists() else []
    if name not in instances:
        log.error("Instance %r not found", name)
        sys.exit(1)
    plan = _plan_instance(name, "exit")

    if plan["instance_task"] == "Exit Sync" and plan["mc_dir"] and plan["sync_dir"]:
        old_manifest = read_manifest(plan["sync_dir"])
        if old_manifest:
            deletions = _check_deletions(plan["mc_dir"], old_manifest)
            if deletions:
                log.info("Detected %d deletions for %r - opening prompt", len(deletions), name)
                choice = _run_deletion_prompt(name, deletions)
                log.info("Deletion prompt choice for %r: %s", name, choice)
                if choice == "cancel":
                    sys.exit(0)
                elif choice == "restore":
                    import shutil
                    for rel in deletions:
                        src = plan["sync_dir"] / rel
                        dest = plan["mc_dir"] / rel
                        if src.exists():
                            try:
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(str(src), str(dest))
                                log.info("Restored %s to instance", rel)
                            except Exception as e:
                                log.warning("Failed to restore %s: %s", rel, e)
                    # fall through to normal exit sync — files are back, nothing to prune
                # choice == "delete": fall through to normal exit sync (prunes deletions)

    def _noop(event): pass
    _execute_instance_plan(_noop, name, plan)
    sys.exit(0)


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
                        "removed_mods": meta.get("removed_mods", []),
                    }
                    api._update_choice = "skip"

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
                        import urllib.request, zipfile, io
                        slug = tracked["pack_slug"]
                        zip_filename = f"{slug}-{latest}.zip"
                        url_dl = client.build_download_url(slug, latest, zip_filename)
                        req = urllib.request.Request(url_dl)
                        req.add_header("User-Agent", "MCAddonCompanion")
                        if repo.get("read_token"):
                            req.add_header("PRIVATE-TOKEN", repo["read_token"])
                        try:
                            with urllib.request.urlopen(req, timeout=120) as resp:
                                data = resp.read()
                        except Exception as e:
                            log.warning("Update download failed: %s", e)
                            data = None

                        if data:
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

    # Run startup sync, prompting before restoring files missing from instance
    from modules.instance_sync.sync import read_manifest, _check_restorations
    plan = _plan_instance(name, "startup")

    if plan["instance_task"] == "Startup Sync" and plan["mc_dir"] and plan["sync_dir"]:
        manifest = read_manifest(plan["sync_dir"])
        if manifest:
            restorations = _check_restorations(plan["mc_dir"], plan["sync_dir"], manifest)
            if restorations:
                log.info("Detected %d missing files for %r - opening prompt", len(restorations), name)
                choice = _run_deletion_prompt(name, restorations, mode="startup")
                log.info("Startup prompt choice for %r: %s", name, choice)
                if choice == "cancel":
                    sys.exit(0)
                elif choice == "keep":
                    # Remove the files from the sync folder so startup sync won't restore them
                    import shutil
                    manifest = read_manifest(plan["sync_dir"])
                    for rel in restorations:
                        src = plan["sync_dir"] / rel
                        try:
                            if src.exists():
                                src.unlink()
                            manifest.pop(rel, None)
                        except Exception as e:
                            log.warning("Failed to remove %s from sync: %s", rel, e)
                    from modules.instance_sync.sync import write_manifest
                    write_manifest(plan["sync_dir"], manifest)
                # choice == "restore": fall through, startup sync restores normally

    def _noop(event): pass
    _execute_instance_plan(_noop, name, plan)
    sys.exit(0)


if __name__ == "__main__":
    if "--autosync" in sys.argv:
        idx = sys.argv.index("--autosync")
        if idx + 1 >= len(sys.argv):
            log.error("--autosync requires an instance name")
            sys.exit(1)
        _headless_autosync(sys.argv[idx + 1])
    elif "--startup" in sys.argv:
        idx = sys.argv.index("--startup")
        if idx + 1 >= len(sys.argv):
            log.error("--startup requires an instance name")
            sys.exit(1)
        _headless_startup(sys.argv[idx + 1])

    repair_hooks()

    win_ref: list = [None]
    api = Api(win_ref)

    frontend_dir = Path(__file__).parent / "frontend"
    window = webview.create_window(
        "MCAddonCompanion",
        url=str(frontend_dir / "index.html"),
        js_api=api,
        width=1100,
        height=720,
        min_size=(800, 600),
    )
    win_ref[0] = window

    webview.start(debug=not getattr(sys, "frozen", False))
