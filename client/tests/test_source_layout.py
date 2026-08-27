"""Guard the canonical client src-layout."""

from pathlib import Path

import zhoutomo_client


def test_client_src_contains_only_package_namespace():
    src_dir = Path(__file__).resolve().parents[1] / "src"
    entries = {
        path.name
        for path in src_dir.iterdir()
        if path.name != "__pycache__" and not path.name.endswith(".egg-info")
    }
    assert entries == {"zhoutomo_client"}


def test_migration_compatibility_modules_are_gone():
    package_dir = Path(zhoutomo_client.__file__).resolve().parent
    assert not (package_dir / "compat.py").exists()
    assert not (package_dir / "workflows" / "autofocus.py").exists()
    assert not (package_dir / "workflows" / "autotilt.py").exists()
    assert zhoutomo_client.AgentClient.__module__ == "zhoutomo_client.api.client"
