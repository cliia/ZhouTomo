"""ZhouTomo desktop client package."""

from .compat import install_legacy_aliases

# The old application used several top-level package names (``view``,
# ``autofocus``, ``src`` ...).  Install temporary aliases before importing any
# UI/workflow implementation so the package can be moved without changing
# runtime behaviour in the same commit.
install_legacy_aliases()

from .api import AgentClient

__all__ = ["AgentClient"]
