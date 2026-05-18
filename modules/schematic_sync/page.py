from __future__ import annotations
import filecmp
import logging
import shutil
from datetime import datetime
from pathlib import Path
from core.config import INSTANCES_DIR, ARCHIVE_DIRS, EXTENSIONS, EXT_LABELS, SCHEMA_SUBS
from core.state import load_state, save_state
from core.prism import get_minecraft_dir

log = logging.getLogger(__name__)

SYNC_STEPS = ["Scan instance folder", "Diff against archive", "Copy .nbt files", "Copy .litematic files", "Copy .schematic files"]


# ---------------------------------------------------------------------------
# Data layer (preserved from original)
# ---------------------------------------------------------------------------

def get_archive_files():
    archived = {}
    for ext, folder in ARCHIVE_DIRS.items():
        folder.mkdir(parents=True, exist_ok=True)
        archived[ext] = {f.name: f for f in folder.iterdir() if f.suffix == ext}
    return archived


def _is_synced(src_path, filename, instance, ext, archived_ext):
    stem = Path(filename).stem
    suffixed = f"{stem}_{instance}{ext}"
    if filename in archived_ext and filecmp.cmp(str(src_path), str(archived_ext[filename]), shallow=False):
        return True
    if suffixed in archived_ext and filecmp.cmp(str(src_path), str(archived_ext[suffixed]), shallow=False):
        return True
    return False


def get_instance_files(instance_name):
    archived = get_archive_files()
    results = []
    instance_dir = INSTANCES_DIR / instance_name
    for sub in SCHEMA_SUBS:
        schema_dir = instance_dir / sub
        if not schema_dir.exists():
            continue
        for f in schema_dir.iterdir():
            if f.suffix in EXTENSIONS:
                synced = _is_synced(f, f.name, instance_name, f.suffix, archived[f.suffix])
                results.append({
                    "instance": instance_name,
                    "path": f,
                    "filename": f.name,
                    "ext": f.suffix,
                    "synced": synced,
                })
    return results


def get_archive_file_list():
    result = []
    for ext, folder in ARCHIVE_DIRS.items():
        folder.mkdir(parents=True, exist_ok=True)
        for f in sorted(folder.iterdir()):
            if f.suffix == ext:
                result.append({"filename": f.name, "ext": ext, "path": f})
    return result


def _get_or_create_schema_dir(inst_name):
    inst_dir = INSTANCES_DIR / inst_name
    for sub in SCHEMA_SUBS:
        candidate = inst_dir / sub
        if candidate.exists():
            return candidate
    dest = inst_dir / ".minecraft" / "schematics"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def sync_to_archive(file_info):
    src = file_info["path"]
    ext = file_info["ext"]
    dest_dir = ARCHIVE_DIRS[ext]
    dest = dest_dir / file_info["filename"]

    if not dest.exists():
        shutil.copy2(str(src), str(dest))
        return "synced"

    if filecmp.cmp(str(src), str(dest), shallow=False):
        return "skipped_identical"

    stem = Path(file_info["filename"]).stem
    instance = file_info["instance"]
    suffixed_name = f"{stem}_{instance}{ext}"
    suffixed_dest = dest_dir / suffixed_name

    result = "synced_suffixed"
    if suffixed_dest.exists() and not filecmp.cmp(str(src), str(suffixed_dest), shallow=False):
        backup_dir = dest_dir / "backup"
        backup_dir.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.move(str(suffixed_dest), str(backup_dir / f"{stem}_{instance}_{date_str}{ext}"))
        result = "backed_up+synced_suffixed"

    shutil.copy2(str(src), str(suffixed_dest))
    return result


def push_to_instances(archive_file, target_instances):
    copied = skipped = 0
    errors = []
    src = archive_file["path"]

    for inst_name in target_instances:
        try:
            dest_sub = _get_or_create_schema_dir(inst_name)
        except Exception as e:
            errors.append(f"{inst_name}: cannot create folder: {e}")
            continue

        dest = dest_sub / archive_file["filename"]
        try:
            if dest.exists() and filecmp.cmp(str(src), str(dest), shallow=False):
                skipped += 1
            else:
                shutil.copy2(str(src), str(dest))
                copied += 1
        except Exception as e:
            errors.append(f"{inst_name}/{archive_file['filename']}: {e}")

    return copied, skipped, errors


def run_autosync(instance_names, log=None):
    if log is None:
        log = lambda _: None

    total_pulled = total_pushed = total_skipped = 0
    all_errors = []

    for inst_name in instance_names:
        log(f"[{inst_name}] Pulling instance → archive...")
        inst_files = get_instance_files(inst_name)
        for f in inst_files:
            if not f["synced"]:
                try:
                    sync_to_archive(f)
                    total_pulled += 1
                except Exception as e:
                    all_errors.append(f"{inst_name}/{f['filename']} pull: {e}")

        log(f"[{inst_name}] Pushing archive → instance...")
        archive_files = get_archive_file_list()
        for af in archive_files:
            copied, skipped, errors = push_to_instances(af, [inst_name])
            total_pushed += copied
            total_skipped += skipped
            all_errors.extend(errors)

        log(f"[{inst_name}] Done.")

    return {
        "pulled": total_pulled,
        "pushed": total_pushed,
        "skipped": total_skipped,
        "errors": all_errors,
    }


