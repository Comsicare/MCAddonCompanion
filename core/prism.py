import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def is_prism_running() -> bool:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq PrismLauncher.exe", "/NH"],
            stderr=subprocess.DEVNULL, text=True
        )
        return "PrismLauncher.exe" in out
    except Exception as e:
        log.warning("is_prism_running check failed: %s", e)
        return False


def patch_exit_commands(
    instance_names: list[str],
    main_script: Path,
    instances_dir: Path,
) -> tuple[int, int, list[str]]:
    """
    Write PreLaunchCommand and PostExitCommand into each instance's instance.cfg.
    - PreLaunchCommand: pythonw main.py --startup "Instance Name"
    - PostExitCommand:  pythonw main.py --autosync "Instance Name"
    Returns (patched, already_set, errors).
    """
    patched = already_set = 0
    errors = []

    for inst_name in instance_names:
        cfg_path = instances_dir / inst_name / "instance.cfg"
        if not cfg_path.exists():
            errors.append(f"{inst_name}: instance.cfg not found")
            continue
        try:
            if getattr(sys, "frozen", False):
                exe = Path(sys.executable).resolve().as_posix()
                pre_cmd  = f'\\"{exe}\\" --startup \\"{inst_name}\\"'
                post_cmd = f'\\"{exe}\\" --autosync \\"{inst_name}\\"'
            else:
                script = main_script.resolve().as_posix()
                pre_cmd  = f'pythonw \\"{script}\\" --startup \\"{inst_name}\\"'
                post_cmd = f'pythonw \\"{script}\\" --autosync \\"{inst_name}\\"'

            lines = cfg_path.read_text(encoding="utf-8").splitlines()

            already = (
                f'PreLaunchCommand={pre_cmd}' in lines
                and f'PostExitCommand={post_cmd}' in lines
                and 'OverrideCommands=true' in lines
            )
            if already:
                already_set += 1
                continue

            in_general = False
            set_override = set_pre = set_post = False
            new_lines = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("["):
                    if in_general:
                        if not set_override:
                            new_lines.append("OverrideCommands=true")
                        if not set_pre:
                            new_lines.append(f"PreLaunchCommand={pre_cmd}")
                        if not set_post:
                            new_lines.append(f"PostExitCommand={post_cmd}")
                    in_general = (stripped == "[General]")
                    new_lines.append(line)
                    continue

                if in_general:
                    if stripped.startswith("OverrideCommands="):
                        new_lines.append("OverrideCommands=true")
                        set_override = True
                    elif stripped.startswith("PreLaunchCommand="):
                        new_lines.append(f"PreLaunchCommand={pre_cmd}")
                        set_pre = True
                    elif stripped.startswith("PostExitCommand="):
                        new_lines.append(f"PostExitCommand={post_cmd}")
                        set_post = True
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            if in_general:
                if not set_override:
                    new_lines.append("OverrideCommands=true")
                if not set_pre:
                    new_lines.append(f"PreLaunchCommand={pre_cmd}")
                if not set_post:
                    new_lines.append(f"PostExitCommand={post_cmd}")

            cfg_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            patched += 1
        except Exception as e:
            errors.append(f"{inst_name}: {e}")

    return patched, already_set, errors


def clear_exit_commands(
    instance_names: list[str],
    instances_dir: Path,
) -> tuple[int, list[str]]:
    """Remove PreLaunchCommand, PostExitCommand, and OverrideCommands from instance.cfg."""
    cleared = 0
    errors = []
    for inst_name in instance_names:
        cfg_path = instances_dir / inst_name / "instance.cfg"
        if not cfg_path.exists():
            errors.append(f"{inst_name}: instance.cfg not found")
            continue
        try:
            lines = cfg_path.read_text(encoding="utf-8").splitlines()
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("PreLaunchCommand=") or stripped.startswith("PostExitCommand="):
                    continue  # remove entirely
                if stripped == "OverrideCommands=true":
                    new_lines.append("OverrideCommands=false")
                else:
                    new_lines.append(line)
            cfg_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            cleared += 1
        except Exception as e:
            errors.append(f"{inst_name}: {e}")
    return cleared, errors


def get_minecraft_dir(instances_dir: Path, instance_name: str) -> Path | None:
    """Return the .minecraft (or minecraft) subfolder for instance_name, or None if absent."""
    for sub in (".minecraft", "minecraft"):
        p = instances_dir / instance_name / sub
        if p.exists():
            return p
    return None
