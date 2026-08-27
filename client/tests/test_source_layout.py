"""Guard the client src-layout and temporary migration aliases."""

from pathlib import Path
import sys

import zhoutomo_client


def test_client_src_contains_only_package_namespace():
    src_dir = Path(__file__).resolve().parents[1] / "src"
    entries = {path.name for path in src_dir.iterdir() if path.name != "__pycache__"}
    assert entries == {"zhoutomo_client"}


def test_legacy_import_names_are_aliases_not_top_level_packages():
    expected = {
        "agent_client": "zhoutomo_client.api.client",
        "config": "zhoutomo_client.config",
        "model": "zhoutomo_client.models",
        "resources": "zhoutomo_client.resources",
        "src": "zhoutomo_client.processing.legacy",
        "strategy": "zhoutomo_client.strategies",
        "view": "zhoutomo_client.ui",
        "autofocus": "zhoutomo_client.workflows.autofocus",
        "autotilt": "zhoutomo_client.workflows.autotilt",
    }
    for legacy_name, canonical_name in expected.items():
        assert sys.modules[legacy_name].__name__ == canonical_name

    assert zhoutomo_client.AgentClient.__module__ == "zhoutomo_client.api.client"
