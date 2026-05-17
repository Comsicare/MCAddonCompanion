from __future__ import annotations

import configparser
import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


class InvalidExportError(Exception):
    pass


CATEGORY_FOLDERS: dict[str, str] = {
    "mods":          "mods",
    "config":        "config",
    "saves":         "saves",
    "resourcepacks": "resourcepacks",
    "shaderpacks":   "shaderpacks",
    "servers":       "servers.dat",
}

_FILE_CATEGORIES = {"servers"}

EXPORT_CATEGORY_DEFAULTS = {
    "mods":          True,
    "config":        True,
    "servers":       True,
    "saves":         False,
    "resourcepacks": False,
    "shaderpacks":   False,
}

CATEGORY_LABELS = {
    "mods":          "Mods",
    "config":        "Config",
    "saves":         "Saves",
    "resourcepacks": "Resource Packs",
    "shaderpacks":   "Shader Packs",
    "servers":       "Servers (servers.dat)",
}


def get_export_file_list(
    minecraft_dir: Path,
    categories: dict[str, bool],
    extra_paths: list[Path],
) -> list[Path]:
    files: set[Path] = set()
    for key, enabled in categories.items():
        if not enabled:
            continue
        subfolder = CATEGORY_FOLDERS[key]
        target = minecraft_dir / subfolder
        if key in _FILE_CATEGORIES:
            if target.exists():
                files.add(target)
        else:
            if target.is_dir():
                for f in target.rglob("*"):
                    if f.is_file():
                        files.add(f)
    for p in extra_paths:
        if p.is_file():
            files.add(p)
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    files.add(f)
    return sorted(files)


def build_export_zip(
    instance_name: str,
    minecraft_dir: Path,
    instance_dir: Path,
    file_list: list[Path],
    output_path: Path,
    on_progress=None,
) -> None:
    total = len(file_list)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for meta in ("instance.cfg", "mmc-pack.json"):
            p = instance_dir / meta
            if p.exists():
                zf.write(p, meta)
        for i, abs_path in enumerate(file_list):
            rel = abs_path.relative_to(minecraft_dir)
            zf.write(abs_path, f".minecraft/{rel.as_posix()}")
            if on_progress:
                on_progress(i + 1, total)


def read_export_zip(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
    mc_files = [n for n in names if n.startswith(".minecraft/") and not n.endswith("/")]
    if not mc_files:
        raise InvalidExportError("Not a valid MCAddonCompanion export (no .minecraft/ folder found).")
    instance_name = zip_path.stem
    if "instance.cfg" in names:
        with zipfile.ZipFile(zip_path, "r") as zf:
            try:
                cfg_text = zf.read("instance.cfg").decode("utf-8", errors="replace")
                parser = configparser.RawConfigParser()
                parser.read_string(cfg_text)
                name = parser.get("General", "name", fallback=None)
                if name:
                    instance_name = name
            except Exception as e:
                log.debug("instance.cfg parse failed in zip %s: %s", zip_path.name, e)
    categories_present: set[str] = set()
    for key, subfolder in CATEGORY_FOLDERS.items():
        prefix = f".minecraft/{subfolder}"
        if any(f.startswith(prefix) for f in mc_files):
            categories_present.add(key)
    return {
        "instance_name": instance_name,
        "categories_present": categories_present,
        "all_files": mc_files,
    }


def get_import_file_list(
    all_files: list[str],
    categories: dict[str, bool],
    extra_paths: list[str],
) -> list[str]:
    selected: set[str] = set(extra_paths)
    for key, enabled in categories.items():
        if not enabled:
            continue
        subfolder = CATEGORY_FOLDERS[key]
        prefix = f".minecraft/{subfolder}"
        for f in all_files:
            if f == prefix or f.startswith(prefix + "/"):
                selected.add(f)
    return [f for f in all_files if f in selected]


def check_conflicts(
    zip_path: Path,
    file_list: list[str],
    target_dir: Path,
) -> dict:
    existing = set()
    if target_dir.exists():
        for f in target_dir.rglob("*"):
            if f.is_file():
                existing.add(f.relative_to(target_dir).as_posix())
    if not existing:
        return {"empty": True, "additions_only": True, "conflicts": []}
    conflicts = []
    for zip_entry in file_list:
        rel = zip_entry.removeprefix(".minecraft/")
        if rel in existing:
            conflicts.append(rel)
    return {
        "empty": False,
        "additions_only": len(conflicts) == 0,
        "conflicts": conflicts,
    }


def extract_zip(
    zip_path: Path,
    file_list: list[str],
    target_dir: Path,
    backup: bool = False,
    on_progress=None,
) -> dict:
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = target_dir / f"_mcac_backup_{ts}"
    extracted = backed_up = 0
    errors: list[str] = []
    total = len(file_list)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for i, entry in enumerate(file_list):
            rel = entry.removeprefix(".minecraft/")
            dest = target_dir / Path(rel)
            try:
                if backup and dest.exists():
                    backup_dest = backup_dir / Path(rel)
                    backup_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, backup_dest)
                    backed_up += 1
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(entry) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted += 1
            except Exception as e:
                errors.append(f"{rel}: {e}")
            if on_progress:
                on_progress(i + 1, total)
    return {"extracted": extracted, "backed_up": backed_up, "errors": errors}

