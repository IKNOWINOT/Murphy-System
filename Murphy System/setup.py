"""
Setup script for Murphy System Runtime

Copyright 2024 Corey Post InonI LLC
Contact: corey.gfc@gmail.com
License: BSL 1.1
"""

from pathlib import Path

from setuptools import setup, find_packages

_here = Path(__file__).parent
_readme = _here / "README.md"
long_description = _readme.read_text(encoding="utf-8") if _readme.exists() else ""

setup(
    name="murphy-system",
    version="1.0.0",
    author="Inoni LLC",
    author_email="corey.gfc@gmail.com",
    description="Murphy System — AI-powered business automation platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/IKNOWINOT/Murphy-System",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "transformers>=4.48.0",
        "torch>=2.6.0",
        "sentencepiece>=0.2.1",
        "numpy>=1.24.0",
        "networkx>=3.1",
        "cryptography>=46.0.5",
        "rich>=13.0.0",
        "pyfiglet>=1.0.0",
        "prompt-toolkit>=3.0.0",
        "pyyaml>=6.0",
        "fastapi>=0.109.1",
        "uvicorn>=0.23.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "httpx>=0.27.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "pytest-timeout>=2.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "murphy=src.runtime.app:main",
        ],
    },
)