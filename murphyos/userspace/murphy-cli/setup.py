# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
setup.py — packaging for the ``murphy`` CLI command.

Install:
    pip install .            # or:  pip install -e .
    murphy --help
"""

from setuptools import setup, find_packages

setup(
    name="murphy-cli",
    version="1.0.0",
    description="Command-line interface for the Murphy runtime",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Corey Post",
    author_email="corey@inoni.dev",
    license="BSL-1.1",
    url="https://github.com/Inoni-LLC/Murphy-System",
    py_modules=["murphy_cli"],
    python_requires=">=3.9",
    install_requires=[],
    extras_require={
        "dbus": ["dbus-next>=0.2.3"],
    },
    entry_points={
        "console_scripts": [
            "murphy=murphy_cli:main",
        ],
    },
    data_files=[
        ("share/bash-completion/completions", ["murphy-completion.bash"]),
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "License :: Other/Proprietary License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Systems Administration",
    ],
)
