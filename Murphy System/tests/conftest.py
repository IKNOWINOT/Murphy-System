"""
Test configuration for Murphy System.

sys.path is configured via pyproject.toml [tool.pytest.ini_options] pythonpath,
which adds both the project root (".") and "src/" so that both
``from src.xxx import xxx`` and ``from xxx import xxx`` work without
manual sys.path manipulation in individual test files.
"""
