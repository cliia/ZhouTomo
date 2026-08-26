"""Desktop UI facade.

The implementation still lives in the legacy ``view`` package during the
incremental migration. New code should import through this namespace.
"""

from view.main_window import MainWindow
from view.splash_screen import SplashScreen

__all__ = ["MainWindow", "SplashScreen"]
