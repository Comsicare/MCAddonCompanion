import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.gitlab import GitLabClient, GitLabError


class TestGitLabClient(unittest.TestCase):
    def _client(self):
        return GitLabClient(
            base_url="https://gitlab.example.com",
            project_id="42",
            upload_token="upload-tok",
            read_token="read-tok",
        )

    def _mock_resp(self, data):
        fake = MagicMock()
        fake.read.return_value = json.dumps(data).encode()
        fake.__enter__ = lambda s: s
        fake.__exit__ = MagicMock(return_value=False)
        return fake

    def test_list_packages_returns_list(self):
        client = self._client()
        with patch("urllib.request.urlopen", return_value=self._mock_resp([
            {"name": "mypack", "version": "20260510-120000"},
            {"name": "mypack", "version": "20260509-090000"},
        ])):
            result = client.list_packages("mypack")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["version"], "20260510-120000")

    def test_list_packages_empty(self):
        client = self._client()
        with patch("urllib.request.urlopen", return_value=self._mock_resp([])):
            result = client.list_packages("nonexistent")
        self.assertEqual(result, [])

    def test_get_latest_version_returns_first(self):
        client = self._client()
        with patch("urllib.request.urlopen", return_value=self._mock_resp([
            {"name": "mypack", "version": "20260510-120000"},
        ])):
            v = client.get_latest_version("mypack")
        self.assertEqual(v, "20260510-120000")

    def test_get_latest_version_none_when_empty(self):
        client = self._client()
        with patch("urllib.request.urlopen", return_value=self._mock_resp([])):
            v = client.get_latest_version("nonexistent")
        self.assertIsNone(v)

    def test_build_download_url(self):
        client = self._client()
        url = client.build_download_url("mypack", "20260510-120000", "mypack-20260510-120000.zip")
        self.assertIn("/packages/generic/mypack/20260510-120000/", url)
        self.assertIn("mypack-20260510-120000.zip", url)

    def test_list_packages_raises_on_http_error(self):
        import urllib.error
        client = self._client()
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            None, 401, "Unauthorized", {}, None
        )):
            with self.assertRaises(GitLabError):
                client.list_packages("mypack")

    def test_list_all_packages_deduplicates(self):
        client = self._client()
        with patch("urllib.request.urlopen", return_value=self._mock_resp([
            {"name": "pack-a", "version": "20260510-120000"},
            {"name": "pack-a", "version": "20260509-090000"},
            {"name": "pack-b", "version": "20260510-100000"},
        ])):
            result = client.list_all_packages()
        self.assertEqual(len(result), 2)
        self.assertEqual({p["name"] for p in result}, {"pack-a", "pack-b"})

    def test_get_metadata_happy_path(self):
        client = self._client()
        meta = {"description": "A test pack", "author": "tester"}
        with patch("urllib.request.urlopen", return_value=self._mock_resp(meta)):
            result = client.get_metadata("mypack", "20260510-120000")
        self.assertEqual(result, meta)

    def test_get_metadata_returns_empty_dict_on_error(self):
        import urllib.error
        client = self._client()
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            None, 404, "Not Found", {}, None
        )):
            result = client.get_metadata("mypack", "bad-version")
        self.assertEqual(result, {})

    def test_upload_file_happy_path(self):
        client = self._client()
        fake_resp = MagicMock()
        fake_resp.status = 201
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=fake_resp):
            client.upload_file("mypack", "20260510-120000", "mypack.zip", b"data")

    def test_upload_file_raises_without_token(self):
        client = GitLabClient(
            base_url="https://gitlab.example.com",
            project_id="42",
            upload_token=None,
            read_token="read-tok",
        )
        with self.assertRaises(GitLabError):
            client.upload_file("mypack", "20260510-120000", "mypack.zip", b"data")

    def test_download_file_writes_to_dest(self):
        import tempfile
        client = self._client()
        fake_resp = MagicMock()
        fake_resp.headers.get.return_value = "11"  # Content-Length
        fake_resp.read.side_effect = [b"hello world", b""]  # two reads: data then EOF
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=fake_resp):
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "out.zip"
                client.download_file("https://example.com/file.zip", dest)
                self.assertTrue(dest.exists())
                self.assertEqual(dest.read_bytes(), b"hello world")

    def test_get_versions_with_metadata(self):
        client = self._client()
        versions_resp = [
            {"name": "create-combined", "version": "2.0.0"},
            {"name": "create-combined", "version": "1.0.0"},
        ]
        meta_20 = {"pack_name": "Create Combined", "version": "2.0.0", "changenotes": "New stuff", "mods": [], "removed_mods": []}
        meta_10 = {"pack_name": "Create Combined", "version": "1.0.0", "changenotes": "Initial", "mods": [], "removed_mods": []}

        call_count = [0]
        def fake_urlopen(req, timeout=15):
            url = req.full_url
            call_count[0] += 1
            if "packages?" in url:
                return self._mock_resp(versions_resp)
            elif "2.0.0/metadata.json" in url:
                return self._mock_resp(meta_20)
            else:
                return self._mock_resp(meta_10)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.get_versions_with_metadata("create-combined")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["version"], "2.0.0")
        self.assertEqual(result[0]["metadata"]["changenotes"], "New stuff")
        self.assertEqual(result[1]["version"], "1.0.0")
        self.assertEqual(result[1]["metadata"]["changenotes"], "Initial")


if __name__ == "__main__":
    unittest.main()
