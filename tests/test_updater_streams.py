import sys
sys.path.insert(0, ".")


def test_is_newer():
    from core.updater import _is_newer
    assert _is_newer("0.6.1", "0.6.0") is True
    assert _is_newer("0.6.0", "0.6.0") is False
    assert _is_newer("0.5.9", "0.6.0") is False
    assert _is_newer("1.0.0", "0.9.9") is True


def test_tier_from_tag_alpha():
    from core.updater import _tier_from_tag
    assert _tier_from_tag("v0.6.0-alpha") == "alpha"


def test_tier_from_tag_beta():
    from core.updater import _tier_from_tag
    assert _tier_from_tag("v0.6.0-beta") == "beta"


def test_tier_from_tag_rc():
    from core.updater import _tier_from_tag
    assert _tier_from_tag("v0.6.0-rc") == "prerelease"
    assert _tier_from_tag("v0.6.0-rc2") == "prerelease"


def test_tier_from_tag_release():
    from core.updater import _tier_from_tag
    assert _tier_from_tag("v0.6.0") == "release"
    assert _tier_from_tag("0.6.0") == "release"


def test_release_matches_stream_exact():
    from core.updater import _release_matches_stream
    assert _release_matches_stream("alpha", "alpha", True) is True
    assert _release_matches_stream("release", "release", False) is True
    assert _release_matches_stream("release", "alpha", True) is False
    assert _release_matches_stream("beta", "beta", True) is True
    assert _release_matches_stream("beta", "alpha", True) is True
    assert _release_matches_stream("prerelease", "prerelease", True) is True
    assert _release_matches_stream("prerelease", "beta", True) is True
    assert _release_matches_stream("prerelease", "alpha", True) is True
    assert _release_matches_stream("prerelease", "release", False) is False


def test_stream_label():
    from core.updater import _stream_label
    assert _stream_label("alpha") == "Alpha build available"
    assert _stream_label("beta") == "Beta build available"
    assert _stream_label("prerelease") == "Release candidate available"
    assert _stream_label("release") == "Update available"
    assert _stream_label("dev") == "Dev build available"
