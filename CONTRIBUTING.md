# Contributing to Murphy System

Thank you for your interest in contributing to Murphy System! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

1. **Check existing issues** — search [GitHub Issues](https://github.com/IKNOWINOT/Murphy-System/issues) first
2. **Create a new issue** with a clear title and description
3. Include steps to reproduce, expected vs. actual behavior, and your environment

### Suggesting Features

Open a [GitHub Issue](https://github.com/IKNOWINOT/Murphy-System/issues) with the `enhancement` label and describe:
- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

### Submitting Changes

1. Fork the repository
2. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make your changes following our coding standards
4. Add or update tests as needed
5. Run the test suite:
   ```bash
   cd "Murphy System"
   python -m pytest tests/ -v
   ```
6. Commit with clear messages:
   ```bash
   git commit -m "Add: brief description of change"
   ```
7. Push and open a Pull Request

## Development Setup

```bash
# Clone the repo
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System/Murphy\ System

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements_murphy_1.0.txt

# Run tests
python -m pytest tests/ -v
```

## Coding Standards

- **Python 3.11+** required
- Follow PEP 8 style guidelines
- Add docstrings to all public functions and classes
- Keep functions focused and under 50 lines where practical
- Write tests for new functionality

## Contributor License Agreement

By submitting a contribution, you agree that your contributions are licensed under the same [BSL 1.1 license](LICENSE) as the project, and you assign copyright to Inoni Limited Liability Company.

## Questions?

Open an issue or reach out to the maintainers through [GitHub Discussions](https://github.com/IKNOWINOT/Murphy-System/discussions).
