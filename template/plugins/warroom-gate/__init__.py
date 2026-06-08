"""War-room confidence gate plugin. Stdlib only, Python >=3.9.

Loaded by Hermes as a package (hermes_plugins.warroom-gate). The sys.path insert
lets the flat wg_* modules import each other identically here and in tests.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wg_gate import register  # noqa: E402  (must follow the path insert)

__all__ = ["register"]
