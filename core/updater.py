from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from core.config import GITHUB_API_URL, GITLAB_API_URL, GITLAB_BASE_URL, VERSION

log = logging.getLogger(__name__)


def _is_newer(remote: str, local: str) -> bool:
    """Compare semver strings (strips leading 'v' and any suffix like '-alpha')."""
    def _nums(v: str) -> tuple:
        v = v.lstrip("v").split("-")[0]
        return tuple(int(x) for x in v.split("."))
    try:
        return _nums(remote) > _nums(local)
    except Exception:
        return False


def _tier_from_tag(tag: str) -> str:
    """
    Derive release tier from tag name.
    vX.Y.Z-alpha  → 'alpha'
    vX.Y.Z-beta   → 'beta'
    vX.Y.Z-rc*    → 'prerelease'
    vX.Y.Z        → 'release'
    """
    tag = tag.lstrip("v").lower()
    if "-alpha" in tag:
        return "alpha"
    if "-beta" in tag:
        return "beta"
    if re.search(r"-rc\d*$", tag):
        return "prerelease"
    return "release"


_STREAM_RANK = {"release": 0, "prerelease": 1, "beta": 2, "alpha": 3, "dev": 4}


def _release_matches_stream(user_stream: str, release_tier: str, is_prerelease: bool) -> bool:
    """
    Return True if a GitHub release should be shown to a user on user_stream.
    - release stream: only stable (not prerelease)
    - prerelease stream: rc, beta, alpha (all prerelease)
    - beta stream: beta + alpha
    - alpha stream: alpha only
    """
    if user_stream == "dev":
        return False
    if user_stream == "release":
        return not is_prerelease and release_tier == "release"
    user_rank = _STREAM_RANK.get(user_stream, 0)
    tier_rank = _STREAM_RANK.get(release_tier, 0)
    return is_prerelease and tier_rank >= user_rank


def _stream_label(stream: str) -> str:
    return {
        "dev":        "Dev build available",
        "alpha":      "Alpha build available",
        "beta":       "Beta build available",
        "prerelease": "Release candidate available",
        "release":    "Update available",
    }.get(stream, "Update available")


def check_for_update() -> dict | None:
    """
    Check for an update appropriate for the user's configured stream.

    Returns dict with keys: version, download_url, label, stream, changelog
    or None if no update is available.
    """
    from core.state import get_update_stream, get_gitlab_pat
    stream = get_update_stream()

    try:
        if stream == "dev":
            return _check_gitlab_dev(get_gitlab_pat())
        else:
            return _check_github(stream)
    except Exception as e:
        log.warning("Update check failed (stream=%s): %s", stream, e)
        return None


def _check_github(stream: str) -> dict | None:
    """Check GitHub Releases for an update matching the user's stream."""
    req = urllib.request.Request(
        GITHUB_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MCAddonCompanion-updater",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        releases = json.loads(resp.read().decode())

    best = None
    changelogs = []

    for release in releases:
        if release.get("draft", False):
            continue
        tag = release["tag_name"]
        tier = _tier_from_tag(tag)
        is_prerelease = release.get("prerelease", False)

        if not _release_matches_stream(stream, tier, is_prerelease):
            continue

        version = tag.lstrip("v").split("-")[0]
        if not _is_newer(version, VERSION):
            continue

        # This release is newer than installed and matches stream
        if best is None:
            best = release  # first = latest (GitHub returns newest-first)
        changelogs.append({
            "version": tag.lstrip("v"),  # e.g. "0.3.1-alpha"
            "body":    release.get("body", "").strip(),
        })

    if best is None:
        return None

    assets = best.get("assets", [])
    if not assets:
        return None

    if sys.platform == "win32":
        asset = next(
            (a for a in assets if a["name"].endswith(".exe")),
            assets[0],
        )
    else:
        asset = next(
            (a for a in assets if "Linux" in a["name"] and a["name"].endswith(".tar.gz")),
            assets[0],
        )

    tag = best["tag_name"]
    is_pre = best.get("prerelease", False) or any(x in tag for x in ("alpha", "beta", "dev", "rc"))

    return {
        "version":      tag.lstrip("v").split("-")[0],
        "download_url": asset["browser_download_url"],
        "label":        _stream_label(stream),
        "stream":       stream,
        "changelogs":   changelogs,
        "is_prerelease": is_pre,
    }


def _check_gitlab_dev(pat: str | None) -> dict | None:
    """Check GitLab for the latest successful main build artifact."""
    if not pat:
        log.debug("Dev stream: no GitLab PAT configured — skipping update check")
        return None

    url = f"{GITLAB_API_URL}/pipelines?ref=main&status=success&per_page=1"
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": pat})
    with urllib.request.urlopen(req, timeout=10) as resp:
        pipelines = json.loads(resp.read().decode())

    if not pipelines:
        return None

    pipeline_id = pipelines[0]["id"]
    pipeline_sha = pipelines[0]["sha"]

    current_sha = _get_current_build_sha()
    if current_sha and current_sha == pipeline_sha:
        return None

    job_name = "build_windows" if sys.platform == "win32" else "build_linux"
    req2 = urllib.request.Request(
        f"{GITLAB_API_URL}/pipelines/{pipeline_id}/jobs",
        headers={"PRIVATE-TOKEN": pat},
    )
    with urllib.request.urlopen(req2, timeout=10) as resp:
        jobs = json.loads(resp.read().decode())

    job = next((j for j in jobs if j["name"] == job_name and j["status"] == "success"), None)
    if not job:
        return None

    job_id = job["id"]
    plat = "windows" if sys.platform == "win32" else "linux"
    artifact_file = "MCAddonCompanion.exe" if sys.platform == "win32" else "MCAddonCompanion"
    download_url = (
        f"{GITLAB_BASE_URL}/Comsicare/MCAddonCompanion/-/jobs/{job_id}/artifacts/raw/"
        f"dist_{plat}/{artifact_file}?inline=false"
    )

    short_sha = pipeline_sha[:8]
    return {
        "version":      f"dev-{short_sha}",
        "download_url": download_url,
        "label":        _stream_label("dev"),
        "stream":       "dev",
        "changelog":    f"Latest dev build from main (pipeline #{pipeline_id}, {short_sha})",
        "_pat":         pat,
    }


def _get_current_build_sha() -> str | None:
    try:
        from core._build_info import BUILD_SHA  # type: ignore
        return BUILD_SHA
    except ImportError:
        return None


def download_update(download_url: str, on_progress: callable, pat: str | None = None) -> Path | None:
    """
    Download installer/binary to a temp file.
    pat: optional GitLab PAT for dev stream downloads.
    Calls on_progress(downloaded_bytes, total_bytes) during download.
    Returns Path on success, None on error.
    """
    try:
        headers = {"User-Agent": "MCAddonCompanion-updater"}
        if pat:
            headers["PRIVATE-TOKEN"] = pat

        req = urllib.request.Request(download_url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            suffix = ".exe" if sys.platform == "win32" else ""
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            downloaded = 0
            chunk_size = 65536
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                tmp.write(chunk)
                downloaded += len(chunk)
                on_progress(downloaded, total)
            tmp.close()
            return Path(tmp.name)
    except Exception as e:
        log.error("Update download failed: %s", e)
        return None


def install_update(installer_path: Path) -> None:
    """
    Launch detached installer/updater process.
    Windows: runs .exe installer via cmd script with PID polling.
    Linux: replaces the current executable in-place and relaunches.
    Returns immediately. Caller must call sys.exit(0) after.
    """
    if sys.platform == "win32":
        _install_windows(installer_path)
    else:
        _install_linux(installer_path)


def _install_windows(installer_path: Path) -> None:
    install_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "MCAddonCompanion"
    exe = install_dir / "MCAddonCompanion.exe"
    pid = os.getpid()

    log_path = install_dir / "update_install.log"
    script = (
        f"@echo off\r\n"
        f"echo [%time%] Starting update script > \"{log_path}\"\r\n"
        f"echo [%time%] Waiting 6s for app to close >> \"{log_path}\"\r\n"
        f"timeout /t 6 /nobreak >nul\r\n"
        f"echo [%time%] Running installer: \"{installer_path}\" >> \"{log_path}\"\r\n"
        f"if not exist \"{installer_path}\" (\r\n"
        f"  echo [%time%] ERROR installer not found >> \"{log_path}\"\r\n"
        f"  goto :end\r\n"
        f")\r\n"
        f"start /wait \"\" \"{installer_path}\" /VERYSILENT /NORESTART /FORCECLOSEAPPLICATIONS\r\n"
        f"echo [%time%] Installer exit code: %errorlevel% >> \"{log_path}\"\r\n"
        f"timeout /t 2 /nobreak >nul\r\n"
        f"if exist \"{exe}\" (\r\n"
        f"  echo [%time%] Launching {exe} >> \"{log_path}\"\r\n"
        f"  start \"\" \"{exe}\"\r\n"
        f") else (\r\n"
        f"  echo [%time%] ERROR exe not found after install >> \"{log_path}\"\r\n"
        f")\r\n"
        f":end\r\n"
        f"del \"{installer_path}\" 2>nul\r\n"
    )
    bat = tempfile.NamedTemporaryFile(suffix=".bat", delete=False, mode="w")
    bat.write(script)
    bat.close()
    log.info("Update installer script written to %s, log will be at %s", bat.name, log_path)
    subprocess.Popen(
        ["cmd", "/c", bat.name],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def _install_linux(new_binary: Path) -> None:
    """Replace the running binary and relaunch."""
    current_exe = Path(sys.executable)
    if not getattr(sys, "frozen", False):
        log.warning("install_update called in dev mode on Linux — no-op")
        return

    pid = os.getpid()
    script = (
        f"#!/bin/sh\n"
        f"while kill -0 {pid} 2>/dev/null; do sleep 1; done\n"
        f"cp -f '{new_binary}' '{current_exe}'\n"
        f"chmod +x '{current_exe}'\n"
        f"'{current_exe}' &\n"
    )
    sh = tempfile.NamedTemporaryFile(suffix=".sh", delete=False, mode="w")
    sh.write(script)
    sh.close()
    os.chmod(sh.name, 0o755)
    subprocess.Popen([sh.name], close_fds=True, start_new_session=True)
