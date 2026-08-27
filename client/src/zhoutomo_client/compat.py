"""Temporary import aliases for pre-package ZhouTomo client modules.

The physical modules now live under :mod:`zhoutomo_client`.  These aliases keep
legacy absolute imports working while the Qt/workflow implementation is cleaned
up incrementally.  New code must use the ``zhoutomo_client.*`` namespaces.
"""

from __future__ import annotations

import importlib
import sys


_LEGACY_ALIASES = {
    "domain": "zhoutomo_protocol",
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


def install_legacy_aliases() -> None:
    """Register old import names without restoring top-level source packages."""

    for legacy_name, target_name in _LEGACY_ALIASES.items():
        if legacy_name in sys.modules:
            continue
        sys.modules[legacy_name] = importlib.import_module(target_name)
