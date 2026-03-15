"""
Execution Package
Real-world execution engines for the Murphy System Runtime
"""

from .document_generation_engine import (
    Document,
    DocumentGenerationEngine,
    DocumentTemplate,
    DocumentType,
    create_template,
    generate_document,
)

__all__ = [
    'DocumentGenerationEngine',
    'Document',
    'DocumentTemplate',
    'DocumentType',
    'create_template',
    'generate_document'
]
