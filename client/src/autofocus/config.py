#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass


@dataclass
class AutofocusSettings:
    ofrs_step_nm: float = 20.0
    frs_step_nm: float = 75.0
    max_iterations: int = 10
    enable_ultra_fine: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "AutofocusSettings":
        if not isinstance(d, dict):
            return cls()
        def _to_bool(val, default=True):
            try:
                if isinstance(val, bool):
                    return val
                if isinstance(val, (int, float)):
                    return bool(val)
                if isinstance(val, str):
                    return val.strip().lower() in ("1", "true", "yes", "y", "on")
            except Exception:
                pass
            return bool(default)
        return cls(
            ofrs_step_nm=float(d.get("ofrs_step_nm", 20.0)),
            frs_step_nm=float(d.get("frs_step_nm", 75.0)),
            max_iterations=int(d.get("max_iterations", 10)),
            enable_ultra_fine=_to_bool(d.get("enable_ultra_fine", True), True),
        )


