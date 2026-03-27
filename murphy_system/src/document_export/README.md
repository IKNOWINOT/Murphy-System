# Document Export

The `document_export` package renders Murphy reports and documents into
PDF, DOCX, HTML, and other export formats with branded templates.

## Key Modules

| Module | Purpose |
|--------|---------|
| `export_pipeline.py` | `ExportPipeline` — orchestrates render → format → deliver |
| `pdf_renderer.py` | Converts HTML/CSS templates to PDF via headless rendering |
| `brand_registry.py` | Per-organisation brand settings (colours, logos, fonts) |
| `api.py` | FastAPI router: `POST /api/export` with format selection |
