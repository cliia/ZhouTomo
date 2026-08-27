"""Import/resource smoke tests for the packaged desktop client."""

from pathlib import Path


def test_ui_and_workflow_modules_import_from_package_namespace():
    from zhoutomo_client.ui import MainWindow, SplashScreen
    from zhoutomo_client.workflows.autofocus.controller import AutofocusController
    from zhoutomo_client.workflows.autotilt.controller import AutoTiltController

    assert MainWindow.__name__ == "MainWindow"
    assert SplashScreen.__name__ == "SplashScreen"
    assert AutofocusController.__name__ == "AutofocusController"
    assert AutoTiltController.__name__ == "AutoTiltController"


def test_packaged_ui_resources_are_present():
    import zhoutomo_client.resources as resources

    resource_dir = Path(resources.__file__).resolve().parent
    assert (resource_dir / "icons" / "logo.ico").is_file()
    assert (resource_dir / "icons" / "connect_em.png").is_file()
    assert (resource_dir / "background" / "startup_background.jpg").is_file()


def test_processing_legacy_namespace_is_reachable():
    from zhoutomo_client.processing.legacy import BM3D_Main

    assert BM3D_Main is not None
