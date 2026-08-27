"""Read-only diagnostics for vendor Acquisition objects."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from zhoutomo_server.api.dependencies import get_microscope_wiring
from zhoutomo_server.wiring import MicroscopeWiring

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


def _public_names(obj: Any) -> list[str]:
    try:
        return [name for name in dir(obj) if not name.startswith("_")]
    except Exception:
        return []


@router.get("/acquisition/detectors")
async def diagnostics_acquisition_detectors(
    wiring: MicroscopeWiring = Depends(get_microscope_wiring),
):
    try:
        microscope = wiring.get_microscope()
        result: dict[str, Any] = {"detectors": []}
        instrument = getattr(microscope, "instrument", None) if microscope else None
        acquisition = getattr(instrument, "Acquisition", None) if instrument else None
        if acquisition is None:
            return result

        for detector in getattr(acquisition, "Detectors", None) or []:
            info = getattr(detector, "Info", None)
            item: dict[str, Any] = {"name": getattr(info, "Name", None)}
            for key in ("Brightness", "Contrast", "Binnings"):
                try:
                    item[key] = getattr(info, key)
                except Exception:
                    pass
            result["detectors"].append(item)
        return result
    except Exception as exc:
        logger.error("Diagnostics acquisition detectors failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/acquisition/attributes")
async def diagnostics_acquisition_attributes(
    deep: int = 1,
    wiring: MicroscopeWiring = Depends(get_microscope_wiring),
):
    try:
        microscope = wiring.get_microscope()
        result: dict[str, Any] = {
            "microscope_type": type(microscope).__name__ if microscope else None,
            "instrument_present": False,
            "acquisition_present": False,
            "acquisition_attrs": [],
            "acq_params_candidates": {},
            "detector_info_candidates": {},
            "notes": [
                "该端点仅做浅层属性枚举，尽量避免触发硬件操作",
                "候选名基于常见差异：StemAcqParams/STEMAcqParams, AcqImageSize/ImageSize 等",
            ],
        }

        instrument = getattr(microscope, "instrument", None) if microscope else None
        if instrument is None:
            return result
        result["instrument_present"] = True

        acquisition = None
        if "Acquisition" in _public_names(instrument):
            try:
                acquisition = getattr(instrument, "Acquisition")
            except Exception:
                acquisition = None
        if acquisition is None:
            return result

        result["acquisition_present"] = True
        result["acquisition_attrs"] = _public_names(acquisition)

        if deep >= 1:
            for name in ("StemAcqParams", "STEMAcqParams", "AcqParams", "STEMScanParams"):
                present = name in result["acquisition_attrs"]
                attrs: list[str] = []
                if present:
                    try:
                        attrs = _public_names(getattr(acquisition, name))
                    except Exception:
                        pass
                result["acq_params_candidates"][name] = {"present": present, "attrs": attrs}

            for name in ("STEMDetectorInfo", "DetectorInfo", "StemDetectorInfo"):
                present = name in result["acquisition_attrs"]
                attrs: list[str] = []
                if present:
                    try:
                        attrs = _public_names(getattr(acquisition, name))
                    except Exception:
                        pass
                result["detector_info_candidates"][name] = {"present": present, "attrs": attrs}

        return result
    except Exception as exc:
        logger.error("Diagnostics acquisition attributes failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
