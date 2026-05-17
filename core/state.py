import json
import logging
import core.config

log = logging.getLogger(__name__)


class StateError(Exception):
    pass


def load_state() -> dict:
    if core.config.STATEFILE.exists():
        try:
            raw = json.loads(core.config.STATEFILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.error("state.json is corrupt and could not be loaded (%s): %s",
                      core.config.STATEFILE, e)
            raw = {}
    else:
        raw = {}
    return _migrate(raw)


def save_state(state: dict) -> None:
    core.config.STATEFILE.parent.mkdir(parents=True, exist_ok=True)
    core.config.STATEFILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _migrate(raw: dict) -> dict:
    # Old format: {"autosync_instances": [...]}
    # New format: {"schematic_sync": {"autosync_instances": [...]}, "instance_sync": {}}
    if "autosync_instances" in raw and "schematic_sync" not in raw:
        migrated = {
            "schematic_sync": {"autosync_instances": raw["autosync_instances"]},
            "instance_sync": {},
        }
        save_state(migrated)
        return migrated
    changed = False
    if "schematic_sync" not in raw:
        raw["schematic_sync"] = {"autosync_instances": []}
        changed = True
    if "instance_sync" not in raw:
        raw["instance_sync"] = {}
        changed = True
    if changed:
        save_state(raw)
    return raw


# ---------------------------------------------------------------------------
# instance_sync helpers
# ---------------------------------------------------------------------------

def get_instance_sync_config() -> dict:
    """
    Return the instance_sync section of state, with defaults filled in.
    Shape:
      {
        "instances_path": str | None,
        "sync_path": str | None,
        "defaults": {"startup_sync": bool, "exit_sync": bool},
        "instances": {name: {"enabled": bool, "startup_sync": bool|None, "exit_sync": bool|None}}
      }
    """
    state = load_state()
    cfg = state.get("instance_sync", {})
    cfg.setdefault("instances_path", None)
    cfg.setdefault("sync_path", None)
    cfg.setdefault("defaults", {"startup_sync": True, "exit_sync": True})
    cfg.setdefault("instances", {})
    return cfg


def save_instance_sync_config(cfg: dict) -> None:
    state = load_state()
    state["instance_sync"] = cfg
    save_state(state)


def is_instance_sync_configured() -> bool:
    """Return True if setup wizard has been completed."""
    cfg = get_instance_sync_config()
    return bool(cfg.get("instances_path") and cfg.get("sync_path"))


def get_instance_effective_settings(cfg: dict, instance_name: str) -> dict:
    """
    Return effective startup_sync and exit_sync for an instance,
    falling back to defaults when per-instance value is None.
    """
    defaults = cfg.get("defaults", {"startup_sync": True, "exit_sync": True})
    inst = cfg.get("instances", {}).get(instance_name, {})
    return {
        "enabled": inst.get("enabled", False),
        "startup_sync": inst.get("startup_sync") if inst.get("startup_sync") is not None else defaults["startup_sync"],
        "exit_sync": inst.get("exit_sync") if inst.get("exit_sync") is not None else defaults["exit_sync"],
    }


# ---------------------------------------------------------------------------
# pack_registry helpers
# ---------------------------------------------------------------------------

import os as _os


def make_repo_id() -> str:
    return _os.urandom(4).hex()


def get_pack_registry_repos() -> list[dict]:
    state = load_state()
    return state.get("pack_registry", {}).get("repos", [])


def save_pack_registry_repos(repos: list[dict]) -> None:
    state = load_state()
    state.setdefault("pack_registry", {})["repos"] = repos
    save_state(state)


def get_repo_by_id(repo_id: str) -> dict | None:
    for repo in get_pack_registry_repos():
        if repo.get("id") == repo_id:
            return repo
    return None


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


# ---------------------------------------------------------------------------
# installed_instances helpers
# ---------------------------------------------------------------------------

def get_installed_instances() -> list[dict]:
    state = load_state()
    return state.get("installed_instances", [])


def save_installed_instance(entry: dict) -> None:
    """Upsert by instance_name."""
    state = load_state()
    instances = state.get("installed_instances", [])
    instances = [i for i in instances if i.get("instance_name") != entry["instance_name"]]
    instances.append(entry)
    state["installed_instances"] = instances
    save_state(state)


# ---------------------------------------------------------------------------
# update_stream helpers
# ---------------------------------------------------------------------------

VALID_STREAMS = ("dev", "alpha", "beta", "prerelease", "release")


def get_update_stream() -> str:
    """Return the configured update stream. Defaults to 'release'."""
    state = load_state()
    stream = state.get("update_stream", "release")
    return stream if stream in VALID_STREAMS else "release"


def set_update_stream(stream: str) -> None:
    """Persist the update stream preference."""
    if stream not in VALID_STREAMS:
        raise ValueError(f"Invalid stream: {stream!r}. Must be one of {VALID_STREAMS}")
    state = load_state()
    state["update_stream"] = stream
    save_state(state)


def get_gitlab_pat() -> str | None:
    """Return the GitLab PAT stored for dev stream updates, or None."""
    state = load_state()
    return state.get("gitlab_pat") or None


def set_gitlab_pat(pat: str) -> None:
    """Store a GitLab PAT for dev stream artifact downloads."""
    state = load_state()
    state["gitlab_pat"] = pat
    save_state(state)
