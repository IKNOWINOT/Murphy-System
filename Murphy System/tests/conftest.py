"""
Murphy System Test Configuration
Provides shared fixtures and test utilities for pytest.
"""

import sys
import os
import pytest

# Add murphy_integrated to the path so modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'murphy_integrated'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'murphy_integrated', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def sample_task():
    """Provides a sample task description for testing."""
    return {
        "description": "Automate lead intake for a small business",
        "task_type": "business_automation",
        "parameters": {
            "domain": "sales",
            "priority": "high"
        }
    }


@pytest.fixture
def sample_document_data():
    """Provides sample data for LivingDocument testing."""
    return {
        "title": "Test Document",
        "content": "Test content for document validation",
        "doc_type": "plan",
        "domain": "test"
    }
