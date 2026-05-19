import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

INSTANCES_DIR = Path(os.environ["APPDATA"]) / "PrismLauncher" / "instances"
ARCHIVE_DIRS = {
    ".nbt":       Path.home() / "Nextcloud" / "Games" / "Minecraft" / "Create Mod schematics",
    ".litematic": Path.home() / "Nextcloud" / "Games" / "Minecraft" / "Litematica Schematics",
    ".schematic": Path.home() / "Nextcloud" / "Games" / "Minecraft" / "Schematica Schematics",
}
EXTENSIONS = list(ARCHIVE_DIRS.keys())
EXT_LABELS = {
    ".nbt":       "Create (.nbt)",
    ".litematic": "Litematica (.litematic)",
    ".schematic": "Schematica (.schematic)",
}
SCHEMA_SUBS = [".minecraft/schematics", "minecraft/schematics", "schematics"]

if getattr(sys, "frozen", False):
    STATEFILE = Path(os.environ["APPDATA"]) / "MCAddonCompanion" / "state.json"
else:
    STATEFILE = Path(__file__).parent.parent / "state.json"

COLORS = {
    "bg":       "#1e1e2e",
    "bg_dark":  "#181825",
    "bg_mid":   "#2a2a3e",
    "bg_panel": "#313244",
    "fg":       "#cdd6f4",
    "fg_dim":   "#a6adc8",
    "purple":   "#cba6f7",
    "green":    "#a6e3a1",
    "red":      "#f38ba8",
    "yellow":   "#f9e2af",
    "selected": "#45475a",
}

BLACKLIST_DEFAULTS = [
    "logs/",
    "crash-reports/",
    "*.lock",
    "*.tmp",
    ".fabric/",
    "instance.cfg",
]

VERSION = "0.3.2-alpha"
GITHUB_REPO = "Comsicare/MCAddonCompanion"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases"

GITLAB_BASE_URL = "https://gitlab.comsicare.com"
GITLAB_PROJECT_PATH = "Comsicare/MCAddonCompanion"
GITLAB_API_URL = f"{GITLAB_BASE_URL}/api/v4/projects/{GITLAB_PROJECT_PATH.replace('/', '%2F')}"

PRISM_EXE = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "PrismLauncher" / "prismlauncher.exe"
