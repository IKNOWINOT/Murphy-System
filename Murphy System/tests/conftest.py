"""
Test configuration for Murphy System.

sys.path is configured via pyproject.toml [tool.pytest.ini_options] pythonpath,
which adds the project root ("."), "src/", and "strategic/" to sys.path.

Preferred import style in tests:
    from src.xxx import yyy          # always works (src package)
    from confidence_engine.xxx import yyy  # works (src/ in path)
    from murphy_confidence.xxx import yyy  # works (strategic/ in path)

Do NOT add ``sys.path`` hacks in test files — the pyproject.toml
pythonpath setting handles it automatically.
"""
