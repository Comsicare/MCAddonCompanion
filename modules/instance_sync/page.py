from __future__ import annotations
import logging
import customtkinter as ctk
from core.config import INSTANCES_DIR
from core.ui import COLORS, FONTS, SPACING, R_CARD, R_BTN, card_frame, primary_button, ghost_button, icon_button, kicker_label, text_input
from core.state import load_state, save_state, get_instance_sync_config, save_instance_sync_config, get_instance_effective_settings

log = logging.getLogger(__name__)


class InstanceSyncModule:
    def build(self, parent: ctk.CTkFrame, app) -> None:
        for w in parent.winfo_children():
            w.destroy()

        state = load_state()
        inst_sync = state.get("instance_sync", {})

        # Check if wizard is needed (not configured)
        from core.state import is_instance_sync_configured
        if not is_instance_sync_configured():
            self._build_not_configured(parent, app)
            return

        defaults = inst_sync.get("defaults", {"exit_sync": True, "startup_sync": False})
        sync_path = inst_sync.get("sync_path", "")
        instances_cfg = inst_sync.get("instances", {})

        heading = ctk.CTkFrame(parent, fg_color="transparent")
        heading.pack(fill="x", padx=SPACING["pad_page_x"], pady=(SPACING["pad_page_y"], 0))
        kicker_label(heading, "Instance Sync").pack(anchor="w")
        hdr_row = ctk.CTkFrame(heading, fg_color="transparent")
        hdr_row.pack(fill="x")
        ctk.CTkLabel(hdr_row, text="Instance Sync", font=FONTS["h1"], text_color=COLORS["text_0"]).pack(side="left")
        enabled_count = sum(1 for v in instances_cfg.values() if v.get("enabled", True))
        ctk.CTkLabel(hdr_row, text=f"{len(instances_cfg)} instances · {enabled_count} enabled",
            font=FONTS["secondary"], text_color=COLORS["text_3"]).pack(side="right")

        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=SPACING["pad_page_x"], pady=SPACING["gap_section"])
        self._build_defaults_card(body, defaults, sync_path)
        self._build_instance_table(body, instances_cfg, defaults)

    def _build_not_configured(self, parent, app):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True)
        ctk.CTkLabel(frame, text="Instance Sync not configured", font=FONTS["h1"], text_color=COLORS["text_0"]).pack(pady=(0, 8))
        ctk.CTkLabel(frame, text="Run the setup wizard to get started.", font=FONTS["body"], text_color=COLORS["text_2"]).pack(pady=(0, 16))
        primary_button(frame, "Run Setup Wizard", command=lambda: None).pack()

    def _build_defaults_card(self, parent, defaults: dict, sync_path: str):
        card = card_frame(parent)
        card.pack(fill="x", pady=(0, SPACING["gap_card"]))
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=SPACING["pad_card"], pady=(SPACING["pad_card"], 4))
        kicker_label(hdr, "Defaults").pack(side="left")
        ctk.CTkLabel(hdr, text="Global Defaults", font=FONTS["card_title"], text_color=COLORS["text_0"]).pack(side="left", padx=(6, 0))
        ctk.CTkLabel(hdr, text="Applied to new instances", font=FONTS["secondary"], text_color=COLORS["text_3"]).pack(side="right")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=SPACING["pad_card"], pady=(4, SPACING["pad_card"]))

        exit_var = ctk.BooleanVar(value=defaults.get("exit_sync", True))
        exit_col = ctk.CTkFrame(row, fg_color="transparent")
        exit_col.pack(side="left", padx=(0, SPACING["gap_card"]))
        kicker_label(exit_col, "Exit Sync Default").pack(anchor="w")
        ctk.CTkSwitch(exit_col, text="", variable=exit_var, button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hi"],
            command=lambda: self._save_default("exit_sync", exit_var.get())).pack(anchor="w")

        startup_var = ctk.BooleanVar(value=defaults.get("startup_sync", False))
        startup_col = ctk.CTkFrame(row, fg_color="transparent")
        startup_col.pack(side="left", padx=(0, SPACING["gap_card"]))
        kicker_label(startup_col, "Startup Sync Default").pack(anchor="w")
        ctk.CTkSwitch(startup_col, text="", variable=startup_var, button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hi"],
            command=lambda: self._save_default("startup_sync", startup_var.get())).pack(anchor="w")

        path_col = ctk.CTkFrame(row, fg_color="transparent")
        path_col.pack(side="left", fill="x", expand=True)
        kicker_label(path_col, "Sync Path").pack(anchor="w")
        ctk.CTkLabel(path_col, text=sync_path or "Not configured", font=FONTS["mono"], text_color=COLORS["text_2"]).pack(anchor="w")

    def _save_default(self, key: str, value: bool):
        s = load_state()
        s.setdefault("instance_sync", {}).setdefault("defaults", {})[key] = value
        save_state(s)

    def _build_instance_table(self, parent, instances_cfg: dict, defaults: dict):
        card = card_frame(parent)
        card.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=SPACING["pad_card"], pady=(SPACING["pad_card"], 0))
        kicker_label(hdr, "Instances").pack(side="left")
        ctk.CTkLabel(hdr, text=f"Instance Sync · {len(instances_cfg)}", font=FONTS["card_title"], text_color=COLORS["text_0"]).pack(side="left", padx=(6, 0))

        sep = ctk.CTkFrame(card, height=1, fg_color=COLORS["line"], corner_radius=0)
        sep.pack(fill="x", padx=SPACING["pad_card"], pady=8)

        col_hdr = ctk.CTkFrame(card, fg_color="transparent")
        col_hdr.pack(fill="x", padx=SPACING["pad_card"])
        for col, width in [("INSTANCE", 220), ("EXIT SYNC", 90), ("STARTUP SYNC", 110), ("", 80)]:
            ctk.CTkLabel(col_hdr, text=col, font=FONTS["kicker"], text_color=COLORS["text_3"], width=width, anchor="w").pack(side="left", padx=2)

        sep2 = ctk.CTkFrame(card, height=1, fg_color=COLORS["line"], corner_radius=0)
        sep2.pack(fill="x", padx=SPACING["pad_card"], pady=(4, 0))

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        all_instances = sorted(d.name for d in INSTANCES_DIR.iterdir() if d.is_dir() and not d.name.endswith(".tmp")) if INSTANCES_DIR.exists() else []

        for inst_name in all_instances:
            inst_cfg = instances_cfg.get(inst_name, {})
            exit_on = inst_cfg.get("exit_sync") if inst_cfg.get("exit_sync") is not None else defaults.get("exit_sync", True)
            startup_on = inst_cfg.get("startup_sync") if inst_cfg.get("startup_sync") is not None else defaults.get("startup_sync", False)

            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)

            name_col = ctk.CTkFrame(row, fg_color="transparent", width=220)
            name_col.pack(side="left", padx=2)
            name_col.pack_propagate(False)
            initials = "".join(w[0].upper() for w in inst_name.split()[:2])
            avatar = ctk.CTkFrame(name_col, width=32, height=32, fg_color=COLORS["bg_3"], corner_radius=6)
            avatar.pack(side="left", padx=(0, 8))
            avatar.pack_propagate(False)
            ctk.CTkLabel(avatar, text=initials, font=FONTS["mono_sm"], text_color=COLORS["text_2"]).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(name_col, text=inst_name, font=FONTS["body"], text_color=COLORS["text_0"]).pack(side="left", anchor="w")

            exit_var = ctk.BooleanVar(value=bool(exit_on))
            ctk.CTkSwitch(row, text="", variable=exit_var, width=90,
                button_color=COLORS["accent"], button_hover_color=COLORS["accent_hi"],
                command=lambda n=inst_name, v=exit_var: self._save_instance_override(n, "exit_sync", v.get())).pack(side="left", padx=2)

            startup_var = ctk.BooleanVar(value=bool(startup_on))
            ctk.CTkSwitch(row, text="", variable=startup_var, width=110,
                button_color=COLORS["accent"], button_hover_color=COLORS["accent_hi"],
                command=lambda n=inst_name, v=startup_var: self._save_instance_override(n, "startup_sync", v.get())).pack(side="left", padx=2)

            icon_button(row, "refresh_cw", 14).pack(side="right", padx=2)

    def _save_instance_override(self, inst_name: str, key: str, value: bool):
        s = load_state()
        s.setdefault("instance_sync", {}).setdefault("instances", {}).setdefault(inst_name, {})[key] = value
        save_state(s)

    def on_exit_sync(self, instance_name: str) -> dict:
        # Actual exit sync is dispatched from main.py run_autosync()
        return {"errors": []}

    def on_startup_sync(self, instance_name: str) -> dict:
        # Actual startup sync is dispatched from main.py
        return {"errors": []}
