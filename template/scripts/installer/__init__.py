"""AWR interactive installer package.

This package is run with its own directory on ``PYTHONPATH`` (see
``template/install.sh``), so its modules import each other as top-level names
(``import precheck``, ``from subprocess_runner import run_capturing``) and the
vendored substrate as ``import _substrate.render``. The ``__init__`` exists so
the directory can also be imported as a package by the test suite if needed; it
intentionally pulls in nothing at import time to keep startup cheap and
dependency-free.
"""
