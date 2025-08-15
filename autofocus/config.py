#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass


@dataclass
class AutofocusSettings:
    ofrs_step_nm: float = 20.0
    frs_step_nm: float = 75.0
    max_iterations: int = 10

    @classmethod
    def from_dict(cls, d: dict) -> "AutofocusSettings":
        if not isinstance(d, dict):
            return cls()
        return cls(
            ofrs_step_nm=float(d.get("ofrs_step_nm", 20.0)),
            frs_step_nm=float(d.get("frs_step_nm", 75.0)),
            max_iterations=int(d.get("max_iterations", 10)),
        )


