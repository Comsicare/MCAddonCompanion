from __future__ import annotations
import filecmp
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
import customtkinter as ctk
from core.config import INSTANCES_DIR, ARCHIVE_DIRS, EXTENSIONS, EXT_LABELS, SCHEMA_SUBS
from core.ui import COLORS, FONTS, SPACING, R_CARD, R_BTN, card_frame, primary_button, ghost_button, icon_button, kicker_label
from core.state import load_state, save_state
from core.prism import get_minecraft_dir
from core.progress import ProgressPanel

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


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

class SchematicSyncModule:
    """Module interface for the main menu hub."""

    def build(self, parent: ctk.CTkFrame, app) -> None:
        for w in parent.winfo_children():
            w.destroy()
        state = load_state()
        autosync_instances = state.get("schematic_sync", {}).get("autosync_instances", [])
        instances = self._get_instances()

        heading = ctk.CTkFrame(parent, fg_color="transparent")
        heading.pack(fill="x", padx=SPACING["pad_page_x"], pady=(SPACING["pad_page_y"], 0))
        kicker_label(heading, "Schematic Sync").pack(anchor="w")
        ctk.CTkLabel(heading, text="Schematic Sync", font=FONTS["h1"], text_color=COLORS["text_0"]).pack(anchor="w")

        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=SPACING["pad_page_x"], pady=SPACING["gap_section"])

        left = ctk.CTkFrame(body, fg_color="transparent", width=260)
        left.pack(side="left", fill="y", padx=(0, SPACING["gap_card"]))
        left.pack_propagate(False)

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        self._build_instance_list(left, instances, autosync_instances, right, app)

    def _build_instance_list(self, parent, instances, autosync_instances, detail_parent, app):
        list_card = card_frame(parent)
        list_card.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(list_card, fg_color="transparent")
        hdr.pack(fill="x", padx=SPACING["pad_card"], pady=(SPACING["pad_card"], 6))
        kicker_label(hdr, "Instances").pack(side="left")
        ctk.CTkLabel(hdr, text=f"Configured · {len(instances)}", font=FONTS["card_title"], text_color=COLORS["text_0"]).pack(side="left", padx=(6, 0))

        scroll = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4)
        self._row_buttons: dict[str, ctk.CTkButton] = {}

        def select(name):
            self._selected = [name]
            for n, btn in self._row_buttons.items():
                btn.configure(fg_color=COLORS["bg_2"] if n == name else "transparent")
            self._build_detail(detail_parent, name, autosync_instances, app)

        for inst in instances:
            row = ctk.CTkButton(scroll, text=inst, font=FONTS["body"], fg_color="transparent",
                hover_color=COLORS["bg_2"], text_color=COLORS["text_0"], anchor="w",
                corner_radius=R_BTN, command=lambda n=inst: select(n))
            row.pack(fill="x", pady=1)
            self._row_buttons[inst] = row

        btns = ctk.CTkFrame(list_card, fg_color="transparent")
        btns.pack(fill="x", padx=SPACING["pad_card"], pady=SPACING["pad_card"])
        primary_button(btns, "↻ Sync all", small=True, command=lambda: None).pack(side="right")

        if instances:
            select(instances[0])

    def _build_detail(self, parent, instance_name: str, autosync_instances: list, app):
        for w in parent.winfo_children():
            w.destroy()
        state = load_state()
        is_auto = instance_name in autosync_instances

        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, SPACING["gap_card"]))
        kicker_label(hdr, "Instance").pack(anchor="w")
        title_row = ctk.CTkFrame(hdr, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(title_row, text=instance_name, font=FONTS["card_title"], text_color=COLORS["text_0"]).pack(side="left")

        auto_var = ctk.BooleanVar(value=is_auto)

        def _toggle_auto():
            s = load_state()
            insts = s.setdefault("schematic_sync", {}).setdefault("autosync_instances", [])
            if auto_var.get():
                if instance_name not in insts:
                    insts.append(instance_name)
            else:
                insts[:] = [i for i in insts if i != instance_name]
            save_state(s)

        ctk.CTkSwitch(title_row, text="Autosync on exit", variable=auto_var, font=FONTS["secondary"],
            text_color=COLORS["text_1"], button_color=COLORS["accent"], button_hover_color=COLORS["accent_hi"],
            command=_toggle_auto).pack(side="right")

        mc_dir = get_minecraft_dir(INSTANCES_DIR, instance_name)
        counts = {ext: 0 for ext in EXTENSIONS}
        if mc_dir:
            for ext in EXTENSIONS:
                for sub in SCHEMA_SUBS:
                    schema_dir = (INSTANCES_DIR / instance_name) / sub
                    if schema_dir.exists():
                        counts[ext] += len([f for f in schema_dir.iterdir() if f.suffix == ext])

        stats_card = card_frame(parent)
        stats_card.pack(fill="x", pady=(0, SPACING["gap_card"]))
        stats_row = ctk.CTkFrame(stats_card, fg_color="transparent")
        stats_row.pack(fill="x", padx=SPACING["pad_card"], pady=SPACING["pad_card"])
        for ext in EXTENSIONS:
            col = ctk.CTkFrame(stats_row, fg_color="transparent")
            col.pack(side="left", expand=True)
            kicker_label(col, f"{ext.lstrip('.').upper()} FILES").pack(anchor="w")
            ctk.CTkLabel(col, text=str(counts[ext]), font=FONTS["stat_val"], text_color=COLORS["text_0"]).pack(anchor="w")

        bottom = ctk.CTkFrame(parent, fg_color="transparent")
        bottom.pack(fill="both", expand=True, pady=(0, SPACING["gap_card"]))

        progress_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        progress_frame.pack(side="left", fill="both", expand=True, padx=(0, SPACING["gap_card"]))
        self._progress = ProgressPanel(progress_frame, SYNC_STEPS)

        action_card = card_frame(bottom)
        action_card.pack(side="left", fill="y")
        kicker_label(action_card, "Actions").pack(anchor="w", padx=SPACING["pad_card"], pady=(SPACING["pad_card"], 4))
        primary_button(action_card, "↻ Sync now", small=True,
            command=lambda: self._run_sync(instance_name, parent)).pack(padx=SPACING["pad_card"], pady=SPACING["pad_card"])

    def _run_sync(self, instance_name: str, parent):
        self._progress.reset()
        self._progress.set_step(0, "running")

        def _worker():
            try:
                # Step 0: scan
                inst_files = get_instance_files(instance_name)
                parent.after(0, lambda: self._progress.set_step(0, "ok", f"{len(inst_files)} files"))

                # Step 1: diff
                parent.after(0, lambda: self._progress.set_step(1, "running"))
                unsynced = [f for f in inst_files if not f["synced"]]
                parent.after(0, lambda u=len(unsynced): self._progress.set_step(1, "ok", f"{u} new"))

                # Steps 2-4: copy per extension
                errors = []
                for i, ext in enumerate(EXTENSIONS, start=2):
                    parent.after(0, lambda idx=i: self._progress.set_step(idx, "running"))
                    ext_files = [f for f in unsynced if f["ext"] == ext]
                    for f in ext_files:
                        try:
                            sync_to_archive(f)
                        except Exception as e:
                            errors.append(str(e))
                    # Also push archive to instance
                    for af in get_archive_file_list():
                        if af["ext"] == ext:
                            push_to_instances(af, [instance_name])
                    parent.after(0, lambda idx=i, c=len(ext_files): self._progress.set_step(idx, "ok", f"{c} files"))

                if errors:
                    parent.after(0, lambda: self._progress.set_summary(f"{len(errors)} error(s).", "err"))
                else:
                    parent.after(0, lambda: self._progress.set_summary("Sync complete.", "ok"))
            except Exception as e:
                err = str(e)
                parent.after(0, lambda m=err: self._progress.set_summary(f"Error: {m}", "err"))

        threading.Thread(target=_worker, daemon=True).start()

    def on_exit_sync(self, instance_name: str) -> dict:
        """Headless sync path used by --autosync CLI."""
        state = load_state()
        enabled = state.get("schematic_sync", {}).get("autosync_instances", [])
        if instance_name not in enabled:
            return {"pulled": 0, "pushed": 0, "skipped": 0, "errors": []}
        return run_autosync([instance_name])

    def _get_instances(self) -> list[str]:
        if not INSTANCES_DIR.exists():
            return []
        return sorted(d.name for d in INSTANCES_DIR.iterdir() if d.is_dir() and not d.name.endswith(".tmp"))
