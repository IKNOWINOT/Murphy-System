# Workflows

GitHub Actions only reads workflows from the **root** `.github/workflows/` directory.

The authoritative workflow files live at:

```
.github/workflows/ci.yml
.github/workflows/hetzner-deploy.yml
.github/workflows/deploy.yml
```

Do **not** add workflow files here — GitHub will silently ignore them.
