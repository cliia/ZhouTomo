#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass


@dataclass
class AutofocusSettings:
    ofrs_step_nm: float = 20.0
    frs_step_nm: float = 10.0
    max_iterations: int = 20

    @classmethod
    def from_dict(cls, d: dict) -> "AutofocusSettings":
        if not isinstance(d, dict):
            return cls()
        return cls(
            ofrs_step_nm=float(d.get("ofrs_step_nm", 20.0)),
            frs_step_nm=float(d.get("frs_step_nm", 10.0)),
            max_iterations=int(d.get("max_iterations", 20)),
        )


