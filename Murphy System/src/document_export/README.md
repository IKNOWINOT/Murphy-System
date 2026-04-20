# `src/document_export` — Document Export

Brand-aware document export pipeline that produces styled PDFs and other formats from Murphy content.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The document export package converts Murphy workdocs, reports, and generated content into polished output files with organisation-specific branding applied. The `BrandRegistry` stores `BrandProfile` objects (logo, colour palette, typography) per tenant, and the `DocumentStyleRewriter` applies the active brand to raw document content before rendering. The `ExportPipeline` orchestrates the full flow from content input through style application and PDF rendering. A FastAPI router exposes export and brand management endpoints for API consumers.

## Key Components

| Module | Purpose |
|--------|---------|
| `brand_registry.py` | `BrandRegistry` and `BrandProfile` — per-tenant brand asset management |
| `export_pipeline.py` | `ExportPipeline` and `ExportResult` — end-to-end export orchestration |
| `style_rewriter.py` | `DocumentStyleRewriter` — brand token injection into document content |
| `pdf_renderer.py` | PDF rendering engine (WeasyPrint / headless Chrome backend) |
| `api.py` | FastAPI router with `ExportRequest` and `BrandCreateRequest` models |
| `templates/` | Jinja2 document templates for supported output formats |

## Error Handling

The `ExportPipeline` uses a graceful fallback chain for PDF rendering. If the primary Rich PDF renderer (WeasyPrint) is unavailable, the pipeline logs a debug-level message and falls back to reportlab. All fallback transitions are logged to aid troubleshooting in production.

## Usage

```python
from document_export import ExportPipeline, BrandRegistry

registry = BrandRegistry()
brand = registry.get(tenant_id="acme")

pipeline = ExportPipeline(brand=brand)
result = pipeline.export(content=doc_content, format="pdf")
result.save("/tmp/report.pdf")
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
