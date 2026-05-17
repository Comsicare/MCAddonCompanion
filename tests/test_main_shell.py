import sys
sys.path.insert(0, ".")

def test_no_instance_sharing_reference():
    import pathlib
    src = pathlib.Path("main.py").read_text(encoding="utf-8")
    assert "instance_sharing" not in src
    assert "InstanceSharingModule" not in src

def test_nav_tabs_correct():
    import pathlib
    src = pathlib.Path("main.py").read_text(encoding="utf-8")
    assert "Schematic Sync" in src
    assert "Instance Sync" in src
    assert "Pack Registry" in src
    assert "Instance Sharing" not in src
