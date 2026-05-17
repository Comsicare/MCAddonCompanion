from __future__ import annotations

import json
import logging
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk

from core.config import INSTANCES_DIR
from core.gitlab import GitLabClient, GitLabError
from core.prism import get_minecraft_dir as _get_minecraft_dir
from core.state import get_pack_registry_repos, save_pack_registry_repos, make_repo_id
from core.ui import COLORS, FONTS, SPACING, R_CARD, R_BTN, card_frame, primary_button, ghost_button, icon_button, kicker_label, text_input, status_pill
from core.progress import ProgressPanel
from core.sharing import CATEGORY_LABELS, EXPORT_CATEGORY_DEFAULTS, build_export_zip, get_export_file_list

log = logging.getLogger(__name__)


def _client_from_repo(repo: dict) -> GitLabClient:
    return GitLabClient(
        base_url=repo["base_url"],
        project_id=repo["project_id"],
        upload_token=repo.get("upload_token") or None,
        read_token=repo.get("read_token") or None,
    )


class PackRegistryModule:
    def build(self, parent: ctk.CTkFrame, app) -> None:
        for w in parent.winfo_children():
            w.destroy()

        heading = ctk.CTkFrame(parent, fg_color="transparent")
        heading.pack(fill="x", padx=SPACING["pad_page_x"], pady=(SPACING["pad_page_y"], 0))

        heading_row = ctk.CTkFrame(heading, fg_color="transparent")
        heading_row.pack(fill="x")
        ctk.CTkLabel(heading_row, text="Pack Registry", font=FONTS["h1"], text_color=COLORS["text_0"]).pack(side="left")

        # Sub-tab bar
        tab_bar = ctk.CTkFrame(heading_row, fg_color=COLORS["bg_1"], border_color=COLORS["line"], border_width=1, corner_radius=6)
        tab_bar.pack(side="right")

        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=SPACING["pad_page_x"], pady=SPACING["gap_section"])

        repos_frame   = ctk.CTkFrame(content, fg_color="transparent")
        publish_frame = ctk.CTkFrame(content, fg_color="transparent")
        browse_frame  = ctk.CTkFrame(content, fg_color="transparent")

        tab_btns: dict[str, ctk.CTkButton] = {}

        def show(frame, key):
            for f in (repos_frame, publish_frame, browse_frame):
                f.pack_forget()
            frame.pack(fill="both", expand=True)
            for k, b in tab_btns.items():
                b.configure(
                    fg_color=COLORS["bg_2"] if k == key else "transparent",
                    text_color=COLORS["text_0"] if k == key else COLORS["text_2"],
                )

        for label, frame, key in [("Repos", repos_frame, "repos"), ("Publish", publish_frame, "publish"), ("Browse & Install", browse_frame, "browse")]:
            b = ctk.CTkButton(tab_bar, text=label, font=FONTS["body"], fg_color="transparent",
                hover_color=COLORS["bg_1"], text_color=COLORS["text_2"], corner_radius=R_BTN,
                width=0, command=lambda f=frame, k=key: show(f, k))
            b.pack(side="left", padx=3, pady=3)
            tab_btns[key] = b

        self._build_repos(repos_frame)
        self._build_publish(publish_frame)
        self._build_browse(browse_frame)
        show(repos_frame, "repos")

    # ------------------------------------------------------------------
    # Repos tab
    # ------------------------------------------------------------------

    def _build_repos(self, parent: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.pack(fill="both", expand=True)

        left = card_frame(body)
        left.pack(side="left", fill="y", padx=(0, SPACING["gap_card"]))
        left.configure(width=260)
        left.pack_propagate(False)

        kicker_label(left, "Repos").pack(anchor="w", padx=SPACING["pad_card"], pady=(SPACING["pad_card"], 4))

        list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=4)

        btns_row = ctk.CTkFrame(left, fg_color="transparent")
        btns_row.pack(fill="x", padx=SPACING["pad_card"], pady=SPACING["pad_card"])

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)
        form_card = card_frame(right)
        form_card.pack(fill="both", expand=True)

        kicker_label(form_card, "Repository").pack(anchor="w", padx=SPACING["pad_card"], pady=(SPACING["pad_card"], 0))

        entries: dict[str, ctk.CTkEntry] = {}
        for kicker_txt, key, secret, placeholder in [
            ("NAME", "name", False, "My Repo"),
            ("GITLAB PROJECT URL", "url", False, "https://gitlab.example.com/group/project"),
            ("PAT TOKEN", "pat_token", True, ""),
            ("PACKAGE NAME", "package_name", False, "mc-packs"),
        ]:
            frow = ctk.CTkFrame(form_card, fg_color="transparent")
            frow.pack(fill="x", padx=SPACING["pad_card"], pady=4)
            kicker_label(frow, kicker_txt).pack(anchor="w")
            e = text_input(frow, placeholder_text=placeholder, show="*" if secret else "", width=400)
            e.pack(fill="x", pady=(2, 0))
            entries[key] = e

        ctk.CTkLabel(form_card, text="Project ID resolves automatically from the URL",
            font=FONTS["secondary"], text_color=COLORS["text_3"]).pack(anchor="w", padx=SPACING["pad_card"])

        status_var = ctk.StringVar(value="")
        status_lbl = ctk.CTkLabel(form_card, textvariable=status_var, font=FONTS["secondary"], text_color=COLORS["text_3"])
        status_lbl.pack(anchor="w", padx=SPACING["pad_card"], pady=4)

        self._editing_repo_id: list[str | None] = [None]

        def _load_repo_into_form(repo: dict):
            self._editing_repo_id[0] = repo["id"]
            for key, entry in entries.items():
                entry.delete(0, "end")
                val = repo.get(key) or repo.get("read_token" if key == "pat_token" else key, "")
                if val:
                    entry.insert(0, str(val))
            status_var.set("")

        def _refresh_list():
            for w in list_frame.winfo_children():
                w.destroy()
            for repo in get_pack_registry_repos():
                btn = ctk.CTkButton(list_frame, text=repo["name"], font=FONTS["body"],
                    fg_color="transparent", hover_color=COLORS["bg_2"],
                    text_color=COLORS["text_0"], anchor="w", corner_radius=R_BTN,
                    command=lambda r=repo: _load_repo_into_form(r))
                btn.pack(fill="x", pady=1)

        def _save_repo():
            name = entries["name"].get().strip()
            url = entries["url"].get().strip()
            pat = entries["pat_token"].get().strip()
            pkg = entries["package_name"].get().strip() or "mc-packs"
            if not name or not url or not pat:
                status_var.set("Name, URL, and PAT are required.")
                return
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            project_path = parsed.path.strip("/")
            status_var.set("Resolving project ID…")
            parent_widget = list_frame

            def _resolve():
                try:
                    import urllib.request, json as _json
                    encoded = project_path.replace("/", "%2F")
                    req = urllib.request.Request(
                        f"{base_url}/api/v4/projects/{encoded}",
                        headers={"PRIVATE-TOKEN": pat},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = _json.loads(resp.read().decode())
                    project_id = str(data["id"])
                    repos = get_pack_registry_repos()
                    rid = self._editing_repo_id[0]
                    repo_obj = {
                        "id": rid or make_repo_id(),
                        "name": name,
                        "base_url": base_url,
                        "project_id": project_id,
                        "upload_token": pat,
                        "read_token": pat,
                        "package_name": pkg,
                    }
                    if rid:
                        repos = [repo_obj if r["id"] == rid else r for r in repos]
                    else:
                        repos.append(repo_obj)
                    save_pack_registry_repos(repos)
                    parent_widget.after(0, lambda: (status_var.set(f"Saved. Project ID: {project_id}"), _refresh_list()))
                except Exception as e:
                    err = str(e)
                    parent_widget.after(0, lambda m=err: status_var.set(f"Error: {m}"))

            threading.Thread(target=_resolve, daemon=True).start()

        def _new_repo():
            self._editing_repo_id[0] = None
            for e in entries.values():
                e.delete(0, "end")
            status_var.set("")

        def _delete_repo():
            rid = self._editing_repo_id[0]
            if not rid:
                return
            repos = [r for r in get_pack_registry_repos() if r["id"] != rid]
            save_pack_registry_repos(repos)
            self._editing_repo_id[0] = None
            for e in entries.values():
                e.delete(0, "end")
            status_var.set("Deleted.")
            _refresh_list()

        ghost_button(btns_row, "+ New", small=True, command=_new_repo).pack(side="left")
        ghost_button(btns_row, "✕ Delete", small=True, command=_delete_repo).pack(side="left", padx=(4, 0))

        form_btns = ctk.CTkFrame(form_card, fg_color="transparent")
        form_btns.pack(anchor="w", padx=SPACING["pad_card"], pady=SPACING["pad_card"])
        ghost_button(form_btns, "Cancel", small=True, command=_new_repo).pack(side="left")
        primary_button(form_btns, "✓ Save", small=True, command=_save_repo).pack(side="left", padx=(4, 0))

        _refresh_list()

    # ------------------------------------------------------------------
    # Publish tab
    # ------------------------------------------------------------------

    def _build_publish(self, parent: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.pack(fill="both", expand=True)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(0, SPACING["gap_card"]))
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        form_card = card_frame(left)
        form_card.pack(fill="both", expand=True)
        kicker_label(form_card, "Publish").pack(anchor="w", padx=SPACING["pad_card"], pady=(SPACING["pad_card"], 2))
        ctk.CTkLabel(form_card, text="Build & upload pack", font=FONTS["card_title"], text_color=COLORS["text_0"]).pack(anchor="w", padx=SPACING["pad_card"], pady=(0, SPACING["pad_card"]))

        def _labeled_combo(par, kicker_txt, values, width=300):
            f = ctk.CTkFrame(par, fg_color="transparent")
            f.pack(fill="x", padx=SPACING["pad_card"], pady=4)
            kicker_label(f, kicker_txt).pack(anchor="w")
            combo = ctk.CTkComboBox(f, values=values, width=width,
                fg_color=COLORS["bg_0"], border_color=COLORS["line"],
                button_color=COLORS["bg_2"], text_color=COLORS["text_0"], font=FONTS["body"])
            combo.pack(fill="x", pady=(2, 0))
            return combo

        repos = get_pack_registry_repos()
        repo_combo = _labeled_combo(form_card, "Repository", [r["name"] for r in repos])
        instances = self._get_instances()
        inst_combo = _labeled_combo(form_card, "Instance", instances)

        kicker_label(form_card, "Include").pack(anchor="w", padx=SPACING["pad_card"], pady=(8, 2))
        cat_frame = ctk.CTkFrame(form_card, fg_color="transparent")
        cat_frame.pack(anchor="w", padx=SPACING["pad_card"] + 8)
        cat_vars: dict[str, ctk.BooleanVar] = {}
        for key, label in CATEGORY_LABELS.items():
            v = ctk.BooleanVar(value=EXPORT_CATEGORY_DEFAULTS.get(key, False))
            cat_vars[key] = v
            ctk.CTkCheckBox(cat_frame, text=label, variable=v, font=FONTS["body"],
                text_color=COLORS["text_1"], fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hi"], checkmark_color="#ffffff").pack(anchor="w", pady=1)

        meta_fields: dict[str, ctk.CTkEntry] = {}
        for kicker_txt, key, placeholder in [("Description", "description", ""), ("MC Version", "mc_version", ""), ("Loader", "loader", "")]:
            f = ctk.CTkFrame(form_card, fg_color="transparent")
            f.pack(fill="x", padx=SPACING["pad_card"], pady=4)
            kicker_label(f, kicker_txt).pack(anchor="w")
            e = text_input(f, placeholder_text=placeholder, width=300)
            e.pack(fill="x", pady=(2, 0))
            meta_fields[key] = e

        progress = ProgressPanel(right, ["Build zip", "Upload pack", "Upload metadata"])

        def _on_inst_select(choice):
            mc_ver, loader = self._read_instance_meta(choice)
            if mc_ver:
                meta_fields["mc_version"].delete(0, "end")
                meta_fields["mc_version"].insert(0, mc_ver)
            if loader:
                meta_fields["loader"].delete(0, "end")
                meta_fields["loader"].insert(0, loader)

        inst_combo.configure(command=_on_inst_select)
        if instances:
            inst_combo.set(instances[0])
            _on_inst_select(instances[0])

        publish_btn = primary_button(form_card, "↑ Publish", small=True)
        publish_btn.pack(anchor="w", padx=SPACING["pad_card"], pady=SPACING["pad_card"])

        def _do_publish():
            repos_list = get_pack_registry_repos()
            repo = next((r for r in repos_list if r["name"] == repo_combo.get()), None)
            if not repo:
                progress.set_summary("Select a repository first (add one in the Repos tab).", "err")
                return
            inst = inst_combo.get()
            if not inst:
                progress.set_summary("Select an instance.", "err")
                return
            mc_dir = _get_minecraft_dir(INSTANCES_DIR, inst)
            if mc_dir is None:
                progress.set_summary(f"Cannot find .minecraft folder for '{inst}'.", "err")
                return
            categories = {k: v.get() for k, v in cat_vars.items()}
            file_list = get_export_file_list(mc_dir, categories, [])
            if not file_list:
                progress.set_summary("No files matched the selected categories.", "err")
                return
            instance_dir = INSTANCES_DIR / inst
            version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            package_name = repo.get("package_name", "mc-packs")
            zip_filename = f"{package_name}-{version}.zip"
            metadata = {
                "instance_name": inst,
                "version": version,
                "mc_version": meta_fields["mc_version"].get().strip(),
                "loader": meta_fields["loader"].get().strip(),
                "description": meta_fields["description"].get().strip(),
                "categories": [k for k, v in categories.items() if v],
            }

            progress.reset()
            publish_btn.configure(state="disabled")

            def _run():
                try:
                    parent.after(0, lambda: progress.set_step(0, "running"))
                    with tempfile.TemporaryDirectory() as tmp:
                        zip_path = Path(tmp) / zip_filename
                        build_export_zip(inst, mc_dir, instance_dir, file_list, zip_path)
                        size_mb = zip_path.stat().st_size / 1_048_576
                        parent.after(0, lambda s=size_mb: progress.set_step(0, "ok", f"{s:.1f} MB"))

                        client = _client_from_repo(repo)
                        parent.after(0, lambda: progress.set_step(1, "running"))
                        client.upload_file_path(package_name, version, zip_filename, zip_path)
                        parent.after(0, lambda: progress.set_step(1, "ok"))

                        parent.after(0, lambda: progress.set_step(2, "running"))
                        meta_bytes = json.dumps(metadata, indent=2).encode("utf-8")
                        client.upload_file(package_name, version, "metadata.json", meta_bytes, content_type="application/json")
                        parent.after(0, lambda: progress.set_step(2, "ok"))

                    pn, v = package_name, version
                    parent.after(0, lambda: (progress.set_summary(f"Published {pn} v{v}.", "ok"), publish_btn.configure(state="normal")))
                except (GitLabError, Exception) as e:
                    msg = str(e)
                    parent.after(0, lambda m=msg: (progress.set_summary(f"Error: {m}", "err"), publish_btn.configure(state="normal")))

            threading.Thread(target=_run, daemon=True).start()

        publish_btn.configure(command=_do_publish)

    # ------------------------------------------------------------------
    # Browse & Install tab
    # ------------------------------------------------------------------

    def _build_browse(self, parent: ctk.CTkFrame) -> None:
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", pady=(0, SPACING["gap_card"]))
        kicker_label(top, "Repository").pack(side="left")
        repos = get_pack_registry_repos()
        repo_combo = ctk.CTkComboBox(top, values=[r["name"] for r in repos], width=240,
            fg_color=COLORS["bg_0"], border_color=COLORS["line"],
            button_color=COLORS["bg_2"], text_color=COLORS["text_0"], font=FONTS["body"])
        repo_combo.pack(side="left", padx=(8, 0))

        pane = ctk.CTkFrame(parent, fg_color="transparent")
        pane.pack(fill="both", expand=True)

        left = card_frame(pane)
        left.pack(side="left", fill="y", padx=(0, SPACING["gap_card"]), ipadx=4)
        left.configure(width=260)
        left.pack_propagate(False)
        kicker_label(left, "Packs").pack(anchor="w", padx=SPACING["pad_card"], pady=(SPACING["pad_card"], 4))
        pack_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        pack_list.pack(fill="both", expand=True, padx=4)

        right = card_frame(pane)
        right.pack(side="left", fill="both", expand=True)
        kicker_label(right, "Versions").pack(anchor="w", padx=SPACING["pad_card"], pady=(SPACING["pad_card"], 4))
        ver_list = ctk.CTkScrollableFrame(right, fg_color="transparent")
        ver_list.pack(fill="both", expand=True, padx=4)

        install_frame = ctk.CTkFrame(right, fg_color="transparent")
        install_frame.pack(fill="x", padx=SPACING["pad_card"], pady=SPACING["pad_card"])
        instances = self._get_instances()
        inst_combo = ctk.CTkComboBox(install_frame, values=instances, width=200,
            fg_color=COLORS["bg_0"], border_color=COLORS["line"],
            button_color=COLORS["bg_2"], text_color=COLORS["text_0"], font=FONTS["body"])
        inst_combo.pack(side="left")

        selected_pack: list[str | None] = [None]
        selected_ver: list[str | None] = [None]
        ver_radio_var = ctk.StringVar(value="")

        _packs: list[dict] = []
        _versions_cache: dict[str, list] = {}

        status_var = ctk.StringVar(value="")
        status_lbl = ctk.CTkLabel(right, textvariable=status_var, font=FONTS["secondary"], text_color=COLORS["text_3"])
        status_lbl.pack(anchor="w", padx=SPACING["pad_card"], pady=(0, 4))

        def _get_client() -> GitLabClient | None:
            repos_list = get_pack_registry_repos()
            repo = next((r for r in repos_list if r["name"] == repo_combo.get()), None)
            if not repo:
                return None
            return _client_from_repo(repo)

        def _load_versions(pack_name: str):
            for w in ver_list.winfo_children():
                w.destroy()
            selected_ver[0] = None
            ver_radio_var.set("")
            client = _get_client()
            if not client:
                return

            def _fetch():
                try:
                    versions = client.list_packages(pack_name)
                    _versions_cache[pack_name] = versions

                    def _render():
                        for ver_item in sorted(versions, key=lambda v: v["version"] if isinstance(v, dict) else v, reverse=True):
                            ver = ver_item["version"] if isinstance(ver_item, dict) else ver_item
                            row = ctk.CTkFrame(ver_list, fg_color="transparent")
                            row.pack(fill="x", pady=1)
                            rb = ctk.CTkRadioButton(row, text=ver, variable=ver_radio_var, value=ver,
                                font=FONTS["body"], text_color=COLORS["text_0"],
                                fg_color=COLORS["accent"], hover_color=COLORS["accent_hi"],
                                command=lambda v=ver: selected_ver.__setitem__(0, v))
                            rb.pack(anchor="w")

                    ver_list.after(0, _render)
                except Exception as e:
                    ver_list.after(0, lambda m=str(e): ctk.CTkLabel(ver_list, text=f"Error: {m}", font=FONTS["secondary"], text_color=COLORS["err"]).pack())

            threading.Thread(target=_fetch, daemon=True).start()

        def _load_packs(repo_name: str):
            for w in pack_list.winfo_children():
                w.destroy()
            _packs.clear()
            client = _get_client()
            if not client:
                return

            def _fetch():
                try:
                    packs = client.list_all_packages()
                    _packs.extend(packs)

                    def _render():
                        pack_names = sorted(set(
                            p["name"] if isinstance(p, dict) else p for p in packs
                        ))
                        for pack in pack_names:
                            btn = ctk.CTkButton(pack_list, text=pack, font=FONTS["body"],
                                fg_color="transparent", hover_color=COLORS["bg_2"],
                                text_color=COLORS["text_0"], anchor="w", corner_radius=R_BTN,
                                command=lambda p=pack: (_load_versions(p), selected_pack.__setitem__(0, p)))
                            btn.pack(fill="x", pady=1)

                    pack_list.after(0, _render)
                except Exception as e:
                    pack_list.after(0, lambda m=str(e): ctk.CTkLabel(pack_list, text=f"Error: {m}", font=FONTS["secondary"], text_color=COLORS["err"]).pack())

            threading.Thread(target=_fetch, daemon=True).start()

        repo_combo.configure(command=_load_packs)
        if repos:
            repo_combo.set(repos[0]["name"])
            _load_packs(repos[0]["name"])

        install_btn = primary_button(install_frame, "↓ Install", small=True,
            command=lambda: self._do_install(selected_pack[0], selected_ver[0], inst_combo.get(), status_var, status_lbl))
        install_btn.pack(side="left", padx=(8, 0))

    def _do_install(self, pack_name, version, instance_name, status_var=None, status_lbl=None):
        if not pack_name or not version or not instance_name:
            messagebox.showwarning("Select required", "Select a pack, version, and instance first.")
            return

        repos = get_pack_registry_repos()
        if not repos:
            messagebox.showerror("Error", "No repos configured.")
            return
        repo = repos[0]
        client = _client_from_repo(repo)

        dest_dir = INSTANCES_DIR / instance_name
        package_name = repo.get("package_name", "mc-packs")
        zip_filename = f"{package_name}-{version}.zip"
        url = client.build_download_url(package_name, version, zip_filename)

        def _set_status(msg, color=COLORS["text_3"]):
            if status_var:
                status_var.set(msg)
            if status_lbl:
                status_lbl.configure(text_color=color)

        def _run():
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    zip_path = Path(tmp) / zip_filename
                    _set_status("Downloading…")
                    client.download_file(
                        url, zip_path,
                        on_progress=lambda d, t: _set_status(
                            f"Downloading… {d/1_048_576:.1f}"
                            + (f" / {t/1_048_576:.1f} MB" if t else " MB")
                        ),
                    )
                    _set_status("Installing…")
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    mc_dir = dest_dir / ".minecraft"
                    mc_dir.mkdir(exist_ok=True)
                    import zipfile
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        for name_in_zip in zf.namelist():
                            if name_in_zip in ("instance.cfg", "mmc-pack.json"):
                                zf.extract(name_in_zip, dest_dir)
                            elif (name_in_zip.startswith(".minecraft/") and not name_in_zip.endswith("/")):
                                rel = name_in_zip.removeprefix(".minecraft/")
                                out = mc_dir / rel
                                out.parent.mkdir(parents=True, exist_ok=True)
                                with zf.open(name_in_zip) as src, open(out, "wb") as dst:
                                    shutil.copyfileobj(src, dst)
                n = instance_name
                _set_status(f"Installed as '{n}'. Restart Prism to see it.", COLORS["ok"])
            except GitLabError as e:
                _set_status(f"Download error: {e}", COLORS["err"])
            except Exception as e:
                _set_status(f"Install error: {e}", COLORS["err"])

        threading.Thread(target=_run, daemon=True).start()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _read_instance_meta(self, instance_name: str) -> tuple[str, str]:
        """Return (mc_version, loader) read from mmc-pack.json, or ('', '') if unavailable."""
        mmc = INSTANCES_DIR / instance_name / "mmc-pack.json"
        if not mmc.exists():
            return "", ""
        try:
            data = json.loads(mmc.read_text(encoding="utf-8"))
            components = data.get("components", [])
            mc_version = ""
            loader = ""
            for c in components:
                uid = c.get("uid", "")
                if uid == "net.minecraft":
                    mc_version = c.get("version", "")
                elif uid == "net.fabricmc.fabric-loader":
                    loader = "fabric"
                elif uid == "net.neoforged":
                    loader = "neoforge"
                elif uid == "net.minecraftforge":
                    loader = "forge"
                elif uid == "org.quiltmc.quilt-loader":
                    loader = "quilt"
            return mc_version, loader
        except Exception:
            return "", ""

    def _get_instances(self) -> list[str]:
        if not INSTANCES_DIR.exists():
            return []
        return sorted(
            d.name for d in INSTANCES_DIR.iterdir()
            if d.is_dir() and not d.name.endswith(".tmp")
        )
