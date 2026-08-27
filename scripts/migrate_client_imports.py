"""One-time mechanical migration of legacy ZhouTomo client imports.

This script is intentionally narrow: it only rewrites import paths and does not
change application behaviour. It is removed after the migration commit lands.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "client" / "src" / "zhoutomo_client"

REPLACEMENTS = {
    "from agent_client import ": "from zhoutomo_client.api import ",
    "from domain import ": "from zhoutomo_protocol import ",
    "from config.colors import ": "from zhoutomo_client.config.colors import ",
    "from resources.resource_manager import ": "from zhoutomo_client.resources.resource_manager import ",
    "from view.agent_manager import ": "from zhoutomo_client.ui.agent_manager import ",
    "from view.widgets import ": "from zhoutomo_client.ui.widgets import ",
    "from view.dialogs import ": "from zhoutomo_client.ui.dialogs import ",
    "from view.toolbar import ": "from zhoutomo_client.ui.toolbar import ",
    "from view.image_canvas import ": "from zhoutomo_client.ui.image_canvas import ",
    "from view.panels.": "from zhoutomo_client.ui.panels.",
    "from model.targets import ": "from zhoutomo_client.models.targets import ",
    "from model.ztImage import ": "from zhoutomo_client.models.ztImage import ",
    "from model.ztMicroscope import ": "from zhoutomo_client.models.ztMicroscope import ",
    "from model.ztObject import ": "from zhoutomo_client.models.ztObject import ",
    "from autofocus.config import ": "from zhoutomo_client.workflows.autofocus.config import ",
    "from autofocus.microscope_api import ": "from zhoutomo_client.workflows.autofocus.microscope_api import ",
    "from autofocus.controller import ": "from zhoutomo_client.workflows.autofocus.controller import ",
    "from autofocus.controller_advanced import ": "from zhoutomo_client.workflows.autofocus.controller_advanced import ",
    "from autotilt.controller import ": "from zhoutomo_client.workflows.autotilt.controller import ",
    "from strategy.": "from zhoutomo_client.strategies.",
    "from src import utils": "from zhoutomo_client.processing.legacy import utils",
    "from src.BM3D_Main import ": "from zhoutomo_client.processing.legacy.BM3D_Main import ",
    "from src.ROI import ": "from zhoutomo_client.processing.legacy.ROI import ",
    "from src.create_loose_mask import ": "from zhoutomo_client.processing.legacy.create_loose_mask import ",
    "from src.imgaussfilt import ": "from zhoutomo_client.processing.legacy.imgaussfilt import ",
    "from src.normxcorr2 import ": "from zhoutomo_client.processing.legacy.normxcorr2 import ",
    "from src.subject_tracker import ": "from zhoutomo_client.processing.legacy.subject_tracker import ",
    "from src.utils import ": "from zhoutomo_client.processing.legacy.utils import ",
}


def main() -> None:
    changed = []
    for path in sorted(PACKAGE.rglob("*.py")):
        original = path.read_text(encoding="utf-8")
        updated = original
        for old, new in REPLACEMENTS.items():
            updated = updated.replace(old, new)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed.append(path.relative_to(ROOT).as_posix())

    print(f"Updated {len(changed)} files")
    for path in changed:
        print(path)


if __name__ == "__main__":
    main()
