"""Compatibility module for legacy server imports.

New server code should import from ``zhoutomo_server.domain`` and
``zhoutomo_protocol`` directly.
"""

from zhoutomo_protocol import *
from zhoutomo_server.domain import MicroscopeAggregate, MicroscopeInterface, validate_params
