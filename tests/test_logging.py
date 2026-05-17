import importlib
import logging
import logging.handlers
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# Determine the venv pythonw path so we can pretend we're already inside it.
_VENV_PYTHON = str(Path(__file__).parent.parent / "venv" / "Scripts" / "pythonw.exe")


def _import_main():
    """Import (or retrieve cached) main module without triggering venv bootstrap."""
    if "main" in sys.modules:
        return sys.modules["main"]
    with patch.object(sys, "executable", _VENV_PYTHON):
        import main as m
    return m


def _close_root_handlers():
    """Close and remove all handlers from the root logger."""
    root = logging.getLogger()
    for h in list(root.handlers):
        try:
            h.close()
        except Exception:
            pass
        root.removeHandler(h)


# Import once at collection time so the module is cached for all tests.
_main_module = _import_main()


class TestConfigureLogging(unittest.TestCase):
    def tearDown(self):
        _close_root_handlers()

    def test_log_file_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "MCAddonCompanion" / "mcaddoncompanion.log"
            _close_root_handlers()
            with patch.dict("os.environ", {"APPDATA": tmp}):
                _main_module._configure_logging()
                logging.getLogger("test").info("hello")
                _close_root_handlers()          # close before tmp dir is deleted
            self.assertTrue(log_path.exists())
            self.assertIn("hello", log_path.read_text(encoding="utf-8"))

    def test_stderr_handler_only_in_dev(self):
        _close_root_handlers()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"APPDATA": tmp}):
                with patch.object(sys, "frozen", False, create=True):
                    _main_module._configure_logging()
                stream_handlers = [
                    h for h in logging.getLogger().handlers
                    if isinstance(h, logging.StreamHandler)
                    and not isinstance(h, logging.handlers.RotatingFileHandler)
                ]
                self.assertGreater(len(stream_handlers), 0)
            _close_root_handlers()


class TestGetMinecraftDir(unittest.TestCase):
    def test_finds_dotminecraft(self):
        from core.prism import get_minecraft_dir
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mc = base / "MyInstance" / ".minecraft"
            mc.mkdir(parents=True)
            result = get_minecraft_dir(base, "MyInstance")
            self.assertEqual(result, mc)

    def test_finds_minecraft_without_dot(self):
        from core.prism import get_minecraft_dir
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mc = base / "MyInstance" / "minecraft"
            mc.mkdir(parents=True)
            result = get_minecraft_dir(base, "MyInstance")
            self.assertEqual(result, mc)

    def test_returns_none_when_missing(self):
        from core.prism import get_minecraft_dir
        with tempfile.TemporaryDirectory() as tmp:
            result = get_minecraft_dir(Path(tmp), "NoSuchInstance")
            self.assertIsNone(result)

    def test_dotminecraft_preferred_over_minecraft(self):
        from core.prism import get_minecraft_dir
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "Inst" / ".minecraft").mkdir(parents=True)
            (base / "Inst" / "minecraft").mkdir(parents=True)
            result = get_minecraft_dir(base, "Inst")
            self.assertEqual(result.name, ".minecraft")


class TestStateError(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / "state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _patch(self):
        import core.config as cfg
        return patch.object(cfg, "STATEFILE", self.state_path)

    def test_load_state_logs_error_on_corrupt_json(self):
        self.state_path.write_text("not valid json{{{", encoding="utf-8")
        with self._patch():
            with self.assertLogs("core.state", level="ERROR") as cm:
                from core.state import load_state
                result = load_state()
        # Should return a valid migrated state (not crash)
        self.assertIn("schematic_sync", result)
        # Should have logged an ERROR
        self.assertTrue(any("ERROR" in m for m in cm.output))


class TestGitLabGetValidation(unittest.TestCase):
    def _client(self):
        from core.gitlab import GitLabClient
        return GitLabClient("https://example.com", "1", read_token="tok")

    def test_get_raises_on_string_response(self):
        import json
        from unittest.mock import MagicMock
        from core.gitlab import GitLabError

        client = self._client()
        fake = MagicMock()
        fake.read.return_value = json.dumps("just a string").encode()
        fake.__enter__ = lambda s: s
        fake.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=fake):
            with self.assertRaises(GitLabError) as ctx:
                client._get("https://example.com/api/v4/projects/1/packages")
        self.assertIn("Unexpected response", str(ctx.exception))

    def test_get_raises_on_html_response(self):
        from unittest.mock import MagicMock
        from core.gitlab import GitLabError

        client = self._client()
        fake = MagicMock()
        fake.read.return_value = b"<html><body>Not found</body></html>"
        fake.__enter__ = lambda s: s
        fake.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=fake):
            with self.assertRaises(GitLabError):
                client._get("https://example.com/api/v4/projects/1/packages")


if __name__ == "__main__":
    unittest.main()
