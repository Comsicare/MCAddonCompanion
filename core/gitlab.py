from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)


class GitLabError(Exception):
    pass


class GitLabClient:
    def __init__(
        self,
        base_url: str,
        project_id: str,
        upload_token: str | None = None,
        read_token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id
        self.upload_token = upload_token
        self.read_token = read_token

    def _pkg_base(self) -> str:
        return f"{self.base_url}/api/v4/projects/{self.project_id}/packages"

    def _api_base(self) -> str:
        return f"{self.base_url}/api/v4/projects/{self.project_id}"

    def _get(self, url: str, token: str | None = None) -> list | dict:
        log.debug("GET %s", url)
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "MCAddonCompanion")
        if token:
            req.add_header("PRIVATE-TOKEN", token)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read()
                result = json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise GitLabError(f"HTTP {e.code}: {e.reason}") from e
        except Exception as e:
            raise GitLabError(str(e)) from e
        if not isinstance(result, (list, dict)):
            log.debug("Unexpected GitLab response body (first 200): %s",
                      body[:200].decode("utf-8", errors="replace"))
            raise GitLabError(
                f"Unexpected response format from GitLab API (got {type(result).__name__})"
            )
        return result

    def list_packages(self, package_name: str) -> list[dict]:
        """All versions of package_name, newest first."""
        url = (
            f"{self._api_base()}/packages"
            f"?package_type=generic&package_name={package_name}"
            f"&order_by=version&sort=desc&per_page=100"
        )
        result = self._get(url, token=self.read_token)
        return result if isinstance(result, list) else []

    def get_latest_version(self, package_name: str) -> str | None:
        url = (
            f"{self._api_base()}/packages"
            f"?package_type=generic&package_name={package_name}"
            f"&order_by=version&sort=desc&per_page=1"
        )
        result = self._get(url, token=self.read_token)
        if isinstance(result, list) and result:
            return result[0]["version"]
        return None

    def get_versions_with_metadata(self, package_name: str) -> list[dict]:
        """All versions of package_name with their metadata.json, newest first."""
        packages = self.list_packages(package_name)
        result = []
        for p in packages:
            version = p.get("version", "")
            if not version:
                continue
            meta = self.get_metadata(package_name, version)
            result.append({"version": version, "metadata": meta})
        return result

    def list_all_packages(self) -> list[dict]:
        """One entry per unique package name (latest version only)."""
        seen: set[str] = set()
        unique = []
        page = 1
        while True:
            url = (
                f"{self._api_base()}/packages"
                f"?package_type=generic&order_by=version&sort=desc&per_page=100&page={page}"
            )
            result = self._get(url, token=self.read_token)
            if not isinstance(result, list) or not result:
                break
            for p in result:
                name = p.get("name", "")
                if name not in seen:
                    seen.add(name)
                    unique.append(p)
            if len(result) < 100:
                break
            page += 1
        return unique

    def build_download_url(self, package_name: str, version: str, filename: str) -> str:
        return f"{self._pkg_base()}/generic/{package_name}/{version}/{filename}"

    def get_metadata(self, package_name: str, version: str) -> dict:
        """Download metadata.json sidecar for a version. Returns {} on any error."""
        url = self.build_download_url(package_name, version, "metadata.json")
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "MCAddonCompanion")
        if self.read_token:
            req.add_header("PRIVATE-TOKEN", self.read_token)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.debug("get_metadata(%s, %s): %s", package_name, version, e)
            return {}

    def upload_file(
        self,
        package_name: str,
        version: str,
        filename: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        if not self.upload_token:
            raise GitLabError("No upload token configured.")
        url = f"{self._pkg_base()}/generic/{package_name}/{version}/{filename}"
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("DEPLOY-TOKEN", self.upload_token)
        req.add_header("Content-Type", content_type)
        req.add_header("User-Agent", "MCAddonCompanion")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status not in (200, 201):
                    raise GitLabError(f"Unexpected status: {resp.status}")
        except urllib.error.HTTPError as e:
            raise GitLabError(f"Upload failed — HTTP {e.code}: {e.reason}") from e
        except GitLabError:
            raise
        except Exception as e:
            raise GitLabError(str(e)) from e

    def upload_file_path(
        self,
        package_name: str,
        version: str,
        filename: str,
        path: Path,
    ) -> None:
        """Upload file from disk using a Deploy Token."""
        if not self.upload_token:
            raise GitLabError("No upload token configured.")
        url = f"{self._pkg_base()}/generic/{package_name}/{version}/{filename}"
        data = path.read_bytes()
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("DEPLOY-TOKEN", self.upload_token)
        req.add_header("Content-Type", "application/octet-stream")
        req.add_header("User-Agent", "MCAddonCompanion")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                if resp.status not in (200, 201):
                    raise GitLabError(f"Unexpected status: {resp.status}")
        except urllib.error.HTTPError as e:
            raise GitLabError(f"Upload failed — HTTP {e.code}: {e.reason}") from e
        except GitLabError:
            raise
        except Exception as e:
            raise GitLabError(str(e)) from e

    def download_file(self, url: str, dest: Path, on_progress=None) -> None:
        """Stream download to dest. on_progress(downloaded_bytes, total_bytes) per chunk."""
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "MCAddonCompanion")
        if self.read_token:
            req.add_header("PRIVATE-TOKEN", self.read_token)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress:
                            on_progress(downloaded, total)
        except urllib.error.HTTPError as e:
            raise GitLabError(f"Download failed — HTTP {e.code}: {e.reason}") from e
        except Exception as e:
            raise GitLabError(str(e)) from e
