"""
Setup shim for Murphy System Runtime.

This file exists only for legacy tool compatibility (e.g. ``pip install -e .``
with older pip versions).  The canonical build configuration lives in
``pyproject.toml`` — all metadata, dependencies, and entry-points are defined
there.  Do not add new configuration here; update ``pyproject.toml`` instead.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

# Delegate entirely to pyproject.toml / setuptools PEP 517 backend.
from setuptools import setup  # noqa: F401

setup()
