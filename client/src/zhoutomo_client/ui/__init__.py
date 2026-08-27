"""Qt desktop UI for ZhouTomo.

The implementation has moved from the legacy top-level ``view`` package into
``zhoutomo_client.ui``.  Imports are lazy so importing the client package does
not eagerly construct the Qt UI stack.
"""

__all__ = ["MainWindow", "SplashScreen"]


def __getattr__(name):
    if name == "MainWindow":
        from .main_window import MainWindow

        return MainWindow
    if name == "SplashScreen":
        from .splash_screen import SplashScreen

        return SplashScreen
    raise AttributeError(name)
