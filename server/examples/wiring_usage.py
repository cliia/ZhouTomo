"""Examples for the ZhouTomo server composition root."""

import logging

from zhoutomo_protocol import CameraParams, StageParams
from zhoutomo_server.wiring import (
    create_local_wiring,
    create_microscope_wiring,
    create_null_wiring,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def example_local_microscope():
    wiring = create_local_wiring()
    print("mode:", wiring.mode)
    print("info:", wiring.get_info())
    if wiring.connect():
        print("snapshot:", wiring.get_snapshot())
        wiring.disconnect()
    else:
        print("temscript is unavailable or the microscope could not be connected")


def example_null_microscope():
    wiring = create_null_wiring()
    assert wiring.connect()
    print("info:", wiring.get_info())
    print("snapshot:", wiring.get_snapshot())


def example_error_handling():
    try:
        create_microscope_wiring("invalid_mode")
    except Exception as exc:
        print("expected error:", type(exc).__name__, exc)


if __name__ == "__main__":
    example_null_microscope()
    example_error_handling()
