"""
Capability Extractor - Extract capabilities from SwissKiss analysis

This module analyzes SwissKiss audit results and extracts:
- What the code can do (capabilities)
- Murphy capability mappings
- Suggested categories
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CapabilityExtractor:
    """
    Extract capabilities from SwissKiss analysis.

    Uses:
    - README content analysis
    - Language detection
    - Function/class names
    - Risk patterns (what it accesses)
    - Requirements (what libraries it uses)
    """

    def __init__(self):
        # Map common patterns to capabilities
        self.capability_patterns = {
            # Data processing
            r'pandas|dataframe|csv': 'data_processing',
            r'numpy|scipy|math': 'numerical_computation',
            r'matplotlib|seaborn|plotly': 'data_visualization',

            # Web/API
            r'requests|urllib|http': 'http_client',
            r'flask|django|fastapi': 'web_server',
            r'beautifulsoup|scrapy|selenium': 'web_scraping',

            # Database
            r'sqlalchemy|psycopg|mysql': 'database_access',
            r'mongodb|redis|elasticsearch': 'nosql_database',

            # File operations
            r'pathlib|os\.path|shutil': 'file_operations',
            r'json|yaml|toml|xml': 'data_serialization',
            r'pillow|opencv|imageio': 'image_processing',

            # ML/AI
            r'tensorflow|pytorch|keras': 'deep_learning',
            r'sklearn|scikit': 'machine_learning',
            r'transformers|huggingface': 'nlp',

            # Cloud/Infrastructure
            r'boto3|aws': 'aws_integration',
            r'google\.cloud|gcp': 'gcp_integration',
            r'azure': 'azure_integration',

            # Communication
            r'smtp|email': 'email_sending',
            r'twilio|sms': 'sms_sending',
            r'slack|discord|telegram': 'chat_integration',

            # Security
            r'cryptography|pycrypto': 'encryption',
            r'jwt|oauth': 'authentication',

            # System
            r'subprocess|os\.system': 'system_execution',
            r'socket|paramiko': 'network_access',
        }

        # Map capabilities to Murphy categories
        self.capability_to_category = {
            'data_processing': 'data-analysis',
            'numerical_computation': 'data-analysis',
            'data_visualization': 'visualization',
            'http_client': 'api-integration',
            'web_server': 'web-services',
            'web_scraping': 'data-collection',
            'database_access': 'database',
            'nosql_database': 'database',
            'file_operations': 'file-management',
            'data_serialization': 'data-processing',
            'image_processing': 'computer-vision',
            'deep_learning': 'ai-ml',
            'machine_learning': 'ai-ml',
            'nlp': 'nlp',
            'aws_integration': 'cloud-services',
            'gcp_integration': 'cloud-services',
            'azure_integration': 'cloud-services',
            'email_sending': 'communication',
            'sms_sending': 'communication',
            'chat_integration': 'communication',
            'encryption': 'security',
            'authentication': 'security',
            'system_execution': 'system-automation',
            'network_access': 'networking',
        }

    def extract_from_swisskiss(
        self,
        module_yaml: Dict,
        audit: Dict
    ) -> List[str]:
        """
        Extract capabilities from SwissKiss analysis.

        Args:
            module_yaml: The module.yaml from SwissKiss
            audit: The audit.json from SwissKiss

        Returns:
            List of capability strings
        """

        capabilities = set()

        # Extract from description/summary
        summary = audit.get('summary', '') + ' ' + module_yaml.get('description', '')
        capabilities.update(self._extract_from_text(summary))

        # Extract from languages
        languages = audit.get('languages', {})
        capabilities.update(self._extract_from_languages(languages))

        # Extract from requirements
        requirements = audit.get('requirements', [])
        capabilities.update(self._extract_from_requirements(requirements))

        # Extract from risk patterns (what it accesses)
        risk_scan = audit.get('risk_scan', {})
        capabilities.update(self._extract_from_risk_patterns(risk_scan))

        # Add category as capability
        category = module_yaml.get('category', 'general')
        if category != 'general':
            capabilities.add(category.replace('-', '_'))

        return sorted(list(capabilities))

    def _extract_from_text(self, text: str) -> set:
        """Extract capabilities from text (README, description)"""
        capabilities = set()
        text_lower = text.lower()

        for pattern, capability in self.capability_patterns.items():
            if re.search(pattern, text_lower):
                capabilities.add(capability)

        # Common keywords
        if 'api' in text_lower:
            capabilities.add('api_integration')
        if 'database' in text_lower or 'sql' in text_lower:
            capabilities.add('database_access')
        if 'web' in text_lower:
            capabilities.add('web_services')
        if 'file' in text_lower:
            capabilities.add('file_operations')
        if 'data' in text_lower:
            capabilities.add('data_processing')

        return capabilities

    def _extract_from_languages(self, languages: Dict[str, int]) -> set:
        """Extract capabilities from detected languages"""
        capabilities = set()

        if 'Python' in languages:
            capabilities.add('python_scripting')
        if 'JavaScript' in languages or 'TypeScript' in languages:
            capabilities.add('javascript_execution')
        if 'Shell' in languages:
            capabilities.add('shell_scripting')
        if 'Go' in languages:
            capabilities.add('go_execution')
        if 'Rust' in languages:
            capabilities.add('rust_execution')

        return capabilities

    def _extract_from_requirements(self, requirements: List[Dict]) -> set:
        """Extract capabilities from requirements files"""
        capabilities = set()

        for req in requirements:
            filename = req.get('file', '')

            if 'requirements.txt' in filename or 'pyproject.toml' in filename:
                # Python dependencies - would need to read file content
                # For now, just mark as having dependencies
                capabilities.add('python_dependencies')

            if 'package.json' in filename:
                capabilities.add('npm_dependencies')

        return capabilities

    def _extract_from_risk_patterns(self, risk_scan: Dict) -> set:
        """Extract capabilities from risk patterns (what it accesses)"""
        capabilities = set()

        issues = risk_scan.get('issues', [])

        for issue in issues:
            pattern = issue.get('pattern', '')

            if 'subprocess' in pattern or 'os.system' in pattern:
                capabilities.add('system_execution')
            if 'requests' in pattern:
                capabilities.add('http_client')
            if 'socket' in pattern:
                capabilities.add('network_access')
            if 'paramiko' in pattern:
                capabilities.add('ssh_access')
            if 'eval' in pattern or 'exec' in pattern:
                capabilities.add('code_execution')

        return capabilities

    def suggest_category(self, capabilities: List[str]) -> str:
        """
        Suggest Murphy category based on capabilities.

        Args:
            capabilities: List of extracted capabilities

        Returns:
            Suggested category name
        """

        # Count category votes
        category_votes = {}

        for capability in capabilities:
            category = self.capability_to_category.get(capability, 'general')
            category_votes[category] = category_votes.get(category, 0) + 1

        # Return most common category
        if category_votes:
            return max(category_votes.items(), key=lambda x: x[1])[0]

        return 'general'

    def generate_capability_description(self, capability: str) -> str:
        """Generate human-readable description for capability"""

        descriptions = {
            'data_processing': 'Process and transform data',
            'numerical_computation': 'Perform numerical computations',
            'data_visualization': 'Create data visualizations',
            'http_client': 'Make HTTP requests to APIs',
            'web_server': 'Run web servers and APIs',
            'web_scraping': 'Extract data from websites',
            'database_access': 'Access SQL databases',
            'nosql_database': 'Access NoSQL databases',
            'file_operations': 'Read and write files',
            'data_serialization': 'Serialize/deserialize data',
            'image_processing': 'Process images',
            'deep_learning': 'Run deep learning models',
            'machine_learning': 'Run machine learning models',
            'nlp': 'Process natural language',
            'aws_integration': 'Integrate with AWS services',
            'gcp_integration': 'Integrate with Google Cloud',
            'azure_integration': 'Integrate with Azure',
            'email_sending': 'Send emails',
            'sms_sending': 'Send SMS messages',
            'chat_integration': 'Integrate with chat platforms',
            'encryption': 'Encrypt/decrypt data',
            'authentication': 'Handle authentication',
            'system_execution': 'Execute system commands',
            'network_access': 'Access network resources',
            'python_scripting': 'Execute Python scripts',
            'javascript_execution': 'Execute JavaScript code',
            'shell_scripting': 'Execute shell scripts',
        }

        return descriptions.get(capability, f'Capability: {capability}')
