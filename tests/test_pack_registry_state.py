import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPackRegistryState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / "state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _patch(self):
        import core.config as cfg
        return patch.object(cfg, "STATEFILE", self.state_path)

    def test_get_repos_empty_by_default(self):
        from core.state import get_pack_registry_repos
        with self._patch():
            repos = get_pack_registry_repos()
        self.assertEqual(repos, [])

    def test_save_and_reload_repos(self):
        from core.state import get_pack_registry_repos, save_pack_registry_repos
        repo = {
            "id": "aabbccdd",
            "name": "Test Repo",
            "base_url": "https://git.example.com",
            "project_id": "5",
            "upload_token": "tok-upload",
            "read_token": "tok-read",
            "package_name": "mc-packs",
        }
        with self._patch():
            save_pack_registry_repos([repo])
            repos = get_pack_registry_repos()
        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0]["name"], "Test Repo")
        self.assertEqual(repos[0]["base_url"], "https://git.example.com")

    def test_make_repo_id_is_8_hex_chars(self):
        from core.state import make_repo_id
        rid = make_repo_id()
        self.assertEqual(len(rid), 8)
        int(rid, 16)  # raises ValueError if not valid hex

    def test_make_repo_id_unique(self):
        from core.state import make_repo_id
        ids = {make_repo_id() for _ in range(20)}
        self.assertGreater(len(ids), 1)

    def test_get_repo_by_id(self):
        from core.state import get_repo_by_id, save_pack_registry_repos
        repo = {"id": "deadbeef", "name": "X", "base_url": "", "project_id": "",
                "upload_token": "", "read_token": "", "package_name": "mc-packs"}
        with self._patch():
            save_pack_registry_repos([repo])
            found = get_repo_by_id("deadbeef")
            missing = get_repo_by_id("00000000")
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], "X")
        self.assertIsNone(missing)

    def test_get_tracked_packs_empty_by_default(self):
        from core.state import get_tracked_packs
        with self._patch():
            result = get_tracked_packs()
        self.assertEqual(result, [])

    def test_add_and_get_tracked_pack(self):
        from core.state import add_tracked_pack, get_tracked_packs
        entry = {
            "instance_name": "Create Combined",
            "repo_id": "abc123",
            "pack_name": "Create Combined",
            "pack_slug": "create-combined",
            "installed_version": "1.0.0",
        }
        with self._patch():
            add_tracked_pack(entry)
            result = get_tracked_packs()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pack_slug"], "create-combined")
        self.assertEqual(result[0]["installed_version"], "1.0.0")

    def test_add_tracked_pack_overwrites_existing_instance(self):
        from core.state import add_tracked_pack, get_tracked_packs
        entry1 = {"instance_name": "Create Combined", "repo_id": "abc", "pack_name": "Create Combined", "pack_slug": "create-combined", "installed_version": "1.0.0"}
        entry2 = {"instance_name": "Create Combined", "repo_id": "abc", "pack_name": "Create Combined", "pack_slug": "create-combined", "installed_version": "2.0.0"}
        with self._patch():
            add_tracked_pack(entry1)
            add_tracked_pack(entry2)
            result = get_tracked_packs()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["installed_version"], "2.0.0")

    def test_remove_tracked_pack(self):
        from core.state import add_tracked_pack, remove_tracked_pack, get_tracked_packs
        entry = {"instance_name": "Create Combined", "repo_id": "abc", "pack_name": "Create Combined", "pack_slug": "create-combined", "installed_version": "1.0.0"}
        with self._patch():
            add_tracked_pack(entry)
            remove_tracked_pack("Create Combined")
            result = get_tracked_packs()
        self.assertEqual(result, [])

    def test_remove_tracked_pack_noop_if_missing(self):
        from core.state import remove_tracked_pack, get_tracked_packs
        with self._patch():
            remove_tracked_pack("Nonexistent")  # should not raise
            result = get_tracked_packs()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
