# Contributing to Murphy System Runtime

## Overview

Thank you for your interest in contributing to the Murphy System Runtime! This guide provides comprehensive information on how to contribute effectively to the project.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Code Style Guidelines](#code-style-guidelines)
4. [Testing](#testing)
5. [Documentation](#documentation)
6. [Pull Request Process](#pull-request-process)
7. [Community Guidelines](#community-guidelines)

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Virtual environment (recommended)
- Text editor or IDE (VS Code, PyCharm, etc.)

### Fork and Clone

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/your-username/murphy-system-runtime.git
cd murphy-system-runtime

# Add upstream remote
git remote add upstream https://github.com/corey-post-inoni/murphy-system-runtime.git
```

### Create Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

---

## Development Setup

### Project Structure

```
murphy-system-runtime/
├── src/                    # Source code
│   ├── system_integrator.py
│   ├── confidence_engine/
│   ├── telemetry/
│   └── ...
├── tests/                  # Test files
│   ├── test_unit/
│   ├── test_integration/
│   └── test_performance/
├── documentation/          # Documentation
├── scripts/                # Utility scripts
├── requirements/           # Dependencies
└── setup.py               # Package setup
```

### Environment Variables

Create a `.env` file for development:

```bash
# Development Settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Database
DATABASE_URL=sqlite:///./data/dev.db

# API Settings
API_HOST=localhost
API_PORT=8000

# Feature Flags
ENABLE_EXPERIMENTAL_FEATURES=true
```

---

## Code Style Guidelines

### Python Code Style

Follow PEP 8 style guidelines:

```python
# Good
class SystemIntegrator:
    """Main system integration point."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the integrator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.adapters = {}
    
    def initialize_adapter(self, adapter_name: str) -> None:
        """Initialize a specific adapter.
        
        Args:
            adapter_name: Name of the adapter to initialize
            
        Raises:
            AdapterError: If adapter cannot be initialized
        """
        try:
            adapter = self._create_adapter(adapter_name)
            self.adapters[adapter_name] = adapter
        except Exception as e:
            raise AdapterError(f"Failed to initialize {adapter_name}: {e}")
```

### Type Hints

Always use type hints for function signatures:

```python
from typing import Dict, List, Optional, Union

def process_data(
    data: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Process input data.
    
    Args:
        data: Input data dictionary
        options: Optional processing options
        
    Returns:
        List of processed data items
    """
    options = options or {}
    # Implementation
    return []
```

### Docstrings

Use Google-style docstrings:

```python
def calculate_confidence(
    self,
    context: str,
    query: str,
    evidence: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Calculate confidence score for a query.
    
    Args:
        context: The context for confidence calculation
        query: The query to evaluate
        evidence: Optional supporting evidence
        
    Returns:
        Dictionary containing:
            - score: Confidence score (0.0 to 1.0)
            - level: Confidence level (low, medium, high)
            - reasoning: Explanation of the score
            
    Raises:
        ValueError: If query is empty or invalid
        
    Examples:
        >>> result = calculate_confidence(
        ...     context="query_evaluation",
        ...     query="What is the system architecture?"
        ... )
        >>> print(result['score'])
        0.95
    """
    if not query:
        raise ValueError("Query cannot be empty")
    
    # Implementation
    return {
        "score": 0.95,
        "level": "high",
        "reasoning": "Query is well-formed and matches known patterns"
    }
```

### Error Handling

Use specific exception types:

```python
# Good
try:
    result = self._process_data(data)
except ValueError as e:
    logger.error(f"Invalid data format: {e}")
    raise InvalidDataError(f"Data format error: {e}")
except DatabaseError as e:
    logger.error(f"Database error: {e}")
    raise ProcessingError(f"Failed to process data: {e}")

# Avoid
try:
    result = self._process_data(data)
except Exception as e:
    logger.error(f"Error: {e}")
    raise  # Too generic
```

### Logging

Use structured logging:

```python
import logging

logger = logging.getLogger(__name__)

def process_request(request):
    """Process a request with logging."""
    logger.info("Processing request", extra={
        "request_id": request.id,
        "user_id": request.user_id,
        "endpoint": request.endpoint
    })
    
    try:
        result = self._process(request)
        logger.info("Request processed successfully", extra={
            "request_id": request.id,
            "processing_time": result.duration
        })
        return result
    except Exception as e:
        logger.error("Request processing failed", extra={
            "request_id": request.id,
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        raise
```

---

## Testing

### Writing Tests

Create comprehensive tests for all new features:

```python
import pytest
from src.system_integrator import SystemIntegrator

class TestSystemIntegrator:
    """Test cases for SystemIntegrator."""
    
    @pytest.fixture
    def integrator(self):
        """Create a test integrator instance."""
        return SystemIntegrator(config={"test_mode": True})
    
    def test_initialization(self, integrator):
        """Test that integrator initializes correctly."""
        assert integrator is not None
        assert integrator.config["test_mode"] is True
    
    def test_confidence_calculation(self, integrator):
        """Test confidence calculation."""
        result = integrator.confidence.calculate_confidence(
            context="test",
            query="test query"
        )
        
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0
        assert "level" in result
    
    def test_confidence_with_invalid_query(self, integrator):
        """Test that invalid queries raise appropriate errors."""
        with pytest.raises(ValueError):
            integrator.confidence.calculate_confidence(
                context="test",
                query=""  # Empty query
            )
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_system_integrator.py

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_system_integrator.py::TestSystemIntegrator::test_initialization

# Run tests with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "confidence"
```

### Test Coverage

Maintain high test coverage:

```bash
# Generate coverage report
pytest --cov=src --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html

# Check coverage threshold
pytest --cov=src --cov-fail-under=80
```

### Performance Testing

Use the performance testing suite:

```bash
# Run performance tests
python scripts/run_performance_tests.py

# Run load tests
python scripts/run_load_tests.py

# Run stress tests
python scripts/run_stress_tests.py
```

---

## Documentation

### Writing Documentation

1. **Code Documentation**: Include docstrings for all public APIs
2. **User Documentation**: Update user guides for new features
3. **API Documentation**: Update API reference for changes
4. **Examples**: Provide usage examples for new features

### Documentation Format

Use Markdown for documentation:

```markdown
# Feature Title

## Overview

Brief description of the feature.

## Usage

```python
# Code example
result = some_function()
```

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| param1 | str | Description of param1 |
| param2 | int | Description of param2 |

## Examples

See [API Examples](api/API_EXAMPLES.md) for more examples.
```

### Updating Documentation

```bash
# Build documentation
cd documentation
make build

# Serve documentation locally
make serve

# Check for broken links
make linkcheck
```

---

## Pull Request Process

### Branch Naming

Use descriptive branch names:

```bash
# Good
feature/add-ml-capabilities
fix/telemetry-bug
docs/update-api-reference
perf/optimize-memory-usage

# Avoid
my-branch
fix-stuff
new-feature
```

### Commit Messages

Follow conventional commit format:

```
feat: add machine learning capabilities

Add support for ML-based confidence scoring and
pattern recognition in telemetry data.

Closes #123
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Test changes
- `chore`: Build process or auxiliary tool changes

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed
- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new warnings
- [ ] All tests passing

## Related Issues
Closes #123
```

### Pull Request Review Process

1. **Automated Checks**: CI/CD pipeline runs tests and checks
2. **Code Review**: Maintainer reviews code for quality and consistency
3. **Feedback**: Address review comments and make necessary changes
4. **Approval**: After approval, PR is merged to main branch

---

## Community Guidelines

### Code of Conduct

Be respectful and inclusive:
- Respect differing viewpoints and experiences
- Accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

### Communication

- Be clear and concise in communications
- Use appropriate channels for discussions
- Be patient with responses
- Acknowledge and appreciate contributions

### Reporting Issues

When reporting issues, provide:
1. Clear description of the problem
2. Steps to reproduce
3. Expected behavior
4. Actual behavior
5. Environment details (OS, Python version, etc.)
6. Logs and error messages

### Feature Requests

When suggesting features:
1. Clearly describe the feature
2. Explain the use case
3. Provide examples of how it would work
4. Consider implementation complexity
5. Discuss potential alternatives

---

## Getting Help

### Resources

- **Documentation**: Check the documentation first
- **Issues**: Search existing issues
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact corey.gfc@gmail.com for direct support

### Asking Questions

When asking questions:
1. Be specific about what you're trying to do
2. Provide context and background
3. Share what you've already tried
4. Include code examples or error messages
5. Be patient waiting for responses

---

## Recognition

Contributors are recognized for their contributions:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Featured in project updates

---

## License

By contributing to the Murphy System Runtime, you agree that your contributions will be licensed under the BSL 1.1 (converts to Apache 2.0 after four years).

---

**Thank you for contributing!** 🎉

**Document Owner**: Corey Post InonI LLC
**Contact**: corey.gfc@gmail.com
**License**: BSL 1.1 (converts to Apache 2.0 after 4 years)