# SwissKiss Loader Test — OpenClaw (formerly Clawdbot)

**Date:** 2026-02-10

## Repository
- **URL:** https://github.com/openclaw/openclaw
- **Loader:** `bots/swisskiss_loader.py` (run from a temp working directory)
- **Status:** ✅ Clone + analysis succeeded

## Extracted Metadata
- **License detected:** MIT
- **Requirements files:**
  - `package.json` (size: 9,734 bytes)
- **Language counts (by file extension):**
  - TypeScript: 3359
  - Swift: 463
  - Kotlin: 63
  - Shell: 48
  - Go: 14
  - JavaScript: 12
  - Python: 11

## Dependency Summary (extracted)

- **Python dependencies:** None detected (no `requirements.txt` or `pyproject.toml`)
- **Node dependencies:** 70+ packages listed in `package.json`
  - Examples: `@agentclientprotocol/sdk`, `@aws-sdk/client-bedrock`, `express`, `playwright-core`, `typescript`, `vitest`, `zod`

## README Preview (first lines)
```
# 🦞 OpenClaw — Personal AI Assistant

<p align="center">
    <picture>
        <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/openclaw-logo-text-dark.png">
        <img src="https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/openclaw-logo-text.png" alt="OpenClaw" width="500">
    </picture>
</p>
```

## Risk Scan Summary
- **Total findings:** 25
- **Patterns flagged:**
  - `rm -rf` usage in shell packaging scripts
  - `subprocess.run` usage in a Python analysis script
  - `socket.` usage in E2E docker scripts

## Notes
- The clone and analysis ran successfully in a temporary directory to avoid altering repository state.
- The dependency extractor now captures Python/Node requirements from dependency files for downstream install planning.
- The risk scan indicates standard packaging/build operations but should be reviewed before any automated execution.
