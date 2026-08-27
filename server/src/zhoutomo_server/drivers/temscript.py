"""Temscript hardware adapter exposed through the package namespace.

The hardware implementation is intentionally kept byte-for-byte in
``_legacy_temscript.py`` until it can be regression-tested against a real
microscope.  This module only supplies the old ``domain`` import expected by
that implementation and re-exports its public names.
"""

import sys

import zhoutomo_protocol as _protocol

# Temporary compatibility bridge for the untouched hardware implementation.
# Remove this when _legacy_temscript.py is split into proper driver modules.
sys.modules.setdefault("domain", _protocol)

from ._legacy_temscript import *  # noqa: F401,F403,E402
