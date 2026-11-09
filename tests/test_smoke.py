"""Smoke tests: headless import, optional real Tk instantiation, version info."""
import tkinter as tk

import pytest


def test_module_imports_headless():
    import wb_quantifier_advanced  # noqa: F401
    assert hasattr(wb_quantifier_advanced, 'WesternBlotQuantifier')


def _tk_available():
    try:
        root = tk.Tk()
        root.destroy()
        return True
    except tk.TclError:
        return False


TK_OK = _tk_available()


@pytest.mark.skipif(not TK_OK, reason="Tk cannot create a root window (no display)")
def test_tk_instantiation():
    import wb_quantifier_advanced as wba
    root = tk.Tk()
    try:
        app = wba.WesternBlotQuantifier(root)
        assert app.original_image is None
        assert app.lanes == []
    finally:
        root.destroy()


def test_version_strings_nonempty():
    import version
    assert isinstance(version.__version__, str) and version.__version__
    assert isinstance(version.TOOL_NAME, str) and version.TOOL_NAME
    assert isinstance(version.get_git_commit(), str) and version.get_git_commit()
    assert isinstance(version.get_version_string(), str) and version.get_version_string()
