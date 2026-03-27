# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
setup.py for the murphy-confidence standalone library.
Install with:  pip install .
"""

from setuptools import setup, find_packages

setup(
    name="murphy-confidence",
    version="0.1.0",
    description=(
        "Zero-dependency Multi-Factor Generative-Deterministic (MFGC) "
        "confidence-scoring engine with dynamic safety gate compilation."
    ),
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Corey Post",
    author_email="contact@inoni.com",
    url="https://github.com/inoni/murphy-confidence",
    license="Apache-2.0",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Security",
    ],
    keywords="ai safety confidence scoring gates murphy mfgc",
)
