import fnmatch
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from core.config import BLACKLIST_DEFAULTS

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Blacklist
# ---------------------------------------------------------------------------

def is_blacklisted(rel_path: str, extra: list[str] | None = None) -> bool:
    """Return True if rel_path (forward-slash, relative to .minecraft root) matches any blacklist pattern."""
    patterns = BLACKLIST_DEFAULTS + (extra or [])
    for pat in patterns:
        if fnmatch.fnmatch(rel_path, pat):
            return True
        # Also match if the path starts with a directory pattern like "logs/"
        if pat.endswith("/") and rel_path.startswith(pat):
            return True
    return False


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def read_manifest(sync_instance_dir: Path) -> dict:
    """Read manifest.json from sync folder. Returns {} if missing or corrupt."""
    p = sync_instance_dir / "manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("manifest.json corrupt at %s: %s", p, e)
        return {}


def write_manifest(sync_instance_dir: Path, manifest: dict) -> None:
    sync_instance_dir.mkdir(parents=True, exist_ok=True)
    (sync_instance_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def _file_stat(path: Path) -> dict:
    stat = path.stat()
    return {"mtime": stat.st_mtime, "size": stat.st_size}


def _check_deletions(
    mc_dir: Path,
    old_manifest: dict,
    extra_blacklist: list[str] | None = None,
) -> list[str]:
    """Return sorted list of rel paths present in old_manifest but deleted from mc_dir."""
    if not mc_dir.exists():
        return sorted(old_manifest.keys())
    current = {
        src.relative_to(mc_dir).as_posix()
        for src in mc_dir.rglob("*")
        if src.is_file() and not is_blacklisted(src.relative_to(mc_dir).as_posix(), extra_blacklist)
    }
    return sorted(set(old_manifest.keys()) - current)


def read_last_result(sync_instance_dir: Path) -> dict:
    """Read last_result.json from sync folder. Returns {} if missing or corrupt."""
    p = sync_instance_dir / "last_result.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("last_result.json corrupt at %s: %s", p, e)
        return {}


def write_last_result(sync_instance_dir: Path, result: dict) -> None:
    """Write last_result.json alongside manifest.json. Best-effort — never raises."""
    try:
        sync_instance_dir.mkdir(parents=True, exist_ok=True)
        (sync_instance_dir / "last_result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
    except Exception as e:
        log.warning("Could not write last_result.json at %s: %s", sync_instance_dir, e)

# ---------------------------------------------------------------------------
# Exit sync
# ---------------------------------------------------------------------------

def run_exit_sync(
    instance_name: str,
    minecraft_dir: Path,
    sync_instance_dir: Path,
    extra_blacklist: list[str] | None = None,
    on_progress=None,
    exclude_paths: list[str] | None = None,
    keep_paths: list[str] | None = None,
) -> dict:
    """
    Copy .minecraft/ tree to sync_instance_dir, skipping blacklisted files.
    Prunes sync files no longer present in .minecraft.
    Updates manifest.json. Returns stats dict.
    on_progress: optional callable(copied, total) called after each file copy.
    """
    copied = skipped = pruned = unchanged = 0
    errors = []
    old_manifest = read_manifest(sync_instance_dir)
    new_manifest = {}

    log.info("exit sync: %s → %s", instance_name, sync_instance_dir)

    # Collect files first so we can report total
    all_files = [
        (src, src.relative_to(minecraft_dir).as_posix())
        for src in minecraft_dir.rglob("*")
        if src.is_file()
    ]
    _excl = exclude_paths or []
    to_copy = [
        (src, rel) for src, rel in all_files
        if not is_blacklisted(rel, extra_blacklist)
        and not any(rel == p or rel.startswith(p.rstrip('/') + '/') for p in _excl)
    ]
    skipped = len(all_files) - len(to_copy)
    total = len(to_copy)

    for src, rel in to_copy:
        dest = sync_instance_dir / rel
        try:
            src_stat = src.stat()
            recorded = old_manifest.get(rel)
            if (recorded
                    and dest.exists()
                    and abs(src_stat.st_mtime - recorded["mtime"]) < 1.0
                    and src_stat.st_size == recorded["size"]):
                new_manifest[rel] = recorded
                unchanged += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))
            new_manifest[rel] = _file_stat(dest)
            copied += 1
        except Exception as e:
            errors.append(f"{rel}: {e}")
        if on_progress:
            on_progress(copied + unchanged, total)

    # Prune stale files from sync folder (deleted from instance since last sync)
    _keep = set(keep_paths or [])
    for stale_rel in set(old_manifest) - set(new_manifest):
        if stale_rel in _keep:
            continue
        stale = sync_instance_dir / stale_rel
        try:
            if stale.exists():
                stale.unlink()
            pruned += 1
        except Exception as e:
            errors.append(f"prune {stale_rel}: {e}")

    try:
        write_manifest(sync_instance_dir, new_manifest)
    except Exception as e:
        errors.append(f"manifest write: {e}")

    write_last_result(sync_instance_dir, {
        "mode": "exit",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "copied": copied,
        "skipped": skipped,
        "pruned": pruned,
        "unchanged": unchanged,
        "errors": errors,
    })

    return {"copied": copied, "skipped": skipped, "pruned": pruned, "unchanged": unchanged, "errors": errors}

# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------

def _append_changelog(backup_dir: Path, entry: dict) -> None:
    p = backup_dir / "changelog.json"
    try:
        existing = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except Exception as e:
        log.warning("changelog.json unreadable at %s: %s", p, e)
        existing = []
    existing.append(entry)
    p.write_text(json.dumps(existing, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Startup sync
# ---------------------------------------------------------------------------

def run_startup_sync(
    instance_name: str,
    minecraft_dir: Path,
    sync_instance_dir: Path,
    extra_blacklist: list[str] | None = None,
    on_progress=None,
) -> dict:
    """
    Compare sync folder to instance. Copy newer/missing files to instance.
    Back up overwritten files to sync_instance_dir/backup/.
    Returns stats dict.
    """
    manifest = read_manifest(sync_instance_dir)
    if not manifest:
        return {"restored": 0, "skipped": 0, "backed_up": 0, "errors": []}

    log.info("startup sync: %s ← %s", instance_name, sync_instance_dir)

    restored = skipped = backed_up = 0
    errors = []
    backup_dir = sync_instance_dir / "backup"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    total = len(manifest)

    for rel, recorded in manifest.items():
        if is_blacklisted(rel, extra_blacklist):
            skipped += 1
            continue

        sync_file = sync_instance_dir / rel
        if not sync_file.exists():
            skipped += 1
            continue

        inst_file = minecraft_dir / rel

        # If instance file exists and is identical to or newer than what was recorded, leave it
        if inst_file.exists():
            inst_stat = _file_stat(inst_file)
            if inst_stat["mtime"] >= recorded["mtime"] and inst_stat["size"] == recorded["size"]:
                skipped += 1
                continue

        # Sync file is newer or instance file is missing — restore it
        try:
            if inst_file.exists():
                # Back up existing instance file
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_name = f"{ts}_{rel.replace('/', '_')}"
                shutil.copy2(str(inst_file), str(backup_dir / backup_name))
                _append_changelog(backup_dir, {
                    "timestamp": ts,
                    "rel_path": rel,
                    "backup_name": backup_name,
                    "instance": instance_name,
                })
                backed_up += 1

            inst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(sync_file), str(inst_file))
            restored += 1
        except Exception as e:
            errors.append(f"{rel}: {e}")
        if on_progress:
            on_progress(restored + skipped, total)

    write_last_result(sync_instance_dir, {
        "mode": "startup",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "restored": restored,
        "skipped": skipped,
        "backed_up": backed_up,
        "errors": errors,
    })

    return {"restored": restored, "skipped": skipped, "backed_up": backed_up, "errors": errors}
