# Murphy Nautilus File-Manager Plugin

> © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1

Right-click **"Process with Murphy"** context-menu extension for GNOME Files (Nautilus).

## Supported File Types

| Extension | Murphy API Endpoint |
|-----------|-------------------|
| `.pdf` | `/api/document/process` |
| `.csv`, `.tsv` | `/api/data-pipeline/process` |
| `.py` | `/api/code-repair/process` |
| `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp` | `/api/vision/process` |
| All other files | `/api/forge/process` |

## Installation

```bash
cp murphy-nautilus.py ~/.local/share/nautilus-python/extensions/
nautilus -q   # restart Nautilus
```

## Configuration

Set `MURPHY_API_URL` environment variable to override the default `http://localhost:8000`.

If the REST API is unreachable, the plugin falls back to D-Bus (`org.murphy.Forge.Build`).
