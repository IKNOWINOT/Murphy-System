"""
Setup script for Murphy System Runtime

Copyright 2024 Corey Post InonI LLC
Contact: corey.gfc@gmail.com
License: BSL 1.1
"""

from setuptools import setup, find_packages

with open("README_INSTALL.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mfgc-ai",
    version="0.1.0",
    author="Inoni LLC",
    author_email="corey.gfc@gmail.com",
    description="Murphy-Free Generative Control AI - Autonomous AI with Provable Safety Guarantees",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/inoni-llc/mfgc-ai",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=[
        "transformers>=4.30.0",
        "torch>=2.0.0",
        "sentencepiece>=0.1.99",
        "numpy>=1.24.0",
        "networkx>=3.1",
        "cryptography>=41.0.0",
        "rich>=13.0.0",
        "pyfiglet>=1.0.0",
        "prompt-toolkit>=3.0.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "mfgc-ai=mfgc_ai.scenarios.demo:main",
        ],
    },
)