"""Operating-system layer. Windows is the real target; the stub lets the core run anywhere."""
import sys


def load():
    if sys.platform == "win32":
        from .windows import WindowsPlatform

        return WindowsPlatform()
    from .stub import StubPlatform

    return StubPlatform()
