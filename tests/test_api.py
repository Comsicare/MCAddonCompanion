import sys
sys.path.insert(0, ".")
import unittest.mock as mock


def _make_api():
    """Create an Api instance with a null window ref."""
    win_ref = [None]
    # Import Api — patch webview so it doesn't need a display, and
    # patch sys.exit to suppress the venv bootstrap's sys.exit(0) call.
    with mock.patch.dict("sys.modules", {"webview": mock.MagicMock()}), \
         mock.patch("sys.exit", side_effect=lambda code=0: None):
        import importlib
        import main as m
        importlib.reload(m)
        return m.Api(win_ref)


def test_get_version():
    from core.config import VERSION
    api = _make_api()
    assert api.get_version() == VERSION


def test_get_home_data_returns_dict():
    api = _make_api()
    result = api.get_home_data()
    assert isinstance(result, dict)
    assert "instances" in result


def test_get_schematic_data_returns_dict():
    api = _make_api()
    result = api.get_schematic_data()
    assert isinstance(result, dict)
    assert "instances" in result
    assert "autosync_instances" in result


def test_get_instance_sync_data_returns_dict():
    api = _make_api()
    result = api.get_instance_sync_data()
    assert isinstance(result, dict)
    assert "is_configured" in result


def test_get_repos_returns_list():
    api = _make_api()
    result = api.get_repos()
    assert isinstance(result, list)
