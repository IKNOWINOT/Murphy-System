# `src/execution` — Execution Package

Real-world execution engines for the Murphy System Runtime, including document generation from templates.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The execution package provides the engines that convert Murphy plans and templates into concrete real-world outputs. The primary component is `DocumentGenerationEngine`, which renders structured documents from typed `DocumentTemplate` definitions. Templates are registered by `DocumentType` and instantiated with contextual data to produce finalised `Document` objects. This package is designed to be extended with additional execution engine modules as Murphy's actuation surface grows.

## Key Components

| Module | Purpose |
|--------|---------|
| `document_generation_engine.py` | `DocumentGenerationEngine`, `Document`, `DocumentTemplate`, `DocumentType`, template registration and rendering |

## Usage

```python
from execution import DocumentGenerationEngine, DocumentType, create_template

engine = DocumentGenerationEngine()
template = create_template(DocumentType.REPORT, layout="standard")
doc = engine.generate(template, context={"title": "Weekly Summary", "data": rows})
print(doc.content)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
