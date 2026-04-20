"""Murphy System 1.0 - Runtime Package (INC-13 / H-04 / L-02)"""
import logging as _logging

try:
    from src.runtime.app import create_app, main
except (ImportError, RuntimeError) as _e:
    _logging.getLogger(__name__).warning(
        "FastAPI dependencies not available; create_app and main will be disabled. (%s)", _e
    )
    create_app = None
    main = None
from src.runtime.living_document import LivingDocument
from src.runtime.murphy_system_core import MurphySystem

__all__ = ["MurphySystem", "LivingDocument", "create_app", "main"]
