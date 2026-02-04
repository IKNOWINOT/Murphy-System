# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - LLM Response Validator
Ensures responses meet quality and safety standards
"""

import re
import logging
from typing import Dict, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Validation result types"""
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class ResponseValidator:
    """Validates LLM responses"""
    
    def __init__(self):
        """Initialize validator"""
        self.min_length = 20
        self.max_length = 10000
        self.prohibited_patterns = [
            r'<script[^>]*>.*?</script>',  # Scripts
            r'javascript:',  # JavaScript URLs
            r'data:text/html',  # Data URLs
            r'eval\s*\(',  # eval() calls
        ]
        self.required_structure_indicators = [
            r'[.!?]',  # Sentence endings
            r'\n',  # Line breaks
        ]
    
    def validate(self, content: str) -> Tuple[ValidationResult, Dict]:
        """
        Validate LLM response
        
        Args:
            content: Response content to validate
        
        Returns:
            Tuple of (result, validation_details)
        """
        validation_details = {
            'length_valid': False,
            'no_prohibited_content': False,
            'has_structure': False,
            'is_meaningful': False,
            'issues': [],
            'warnings': []
        }
        
        # Check length
        length_valid = self._check_length(content)
        validation_details['length_valid'] = length_valid
        if not length_valid:
            validation_details['issues'].append("Response too short or too long")
        
        # Check for prohibited content
        no_prohibited = self._check_prohibited_content(content)
        validation_details['no_prohibited_content'] = no_prohibited
        if not no_prohibited:
            validation_details['issues'].append("Contains prohibited content")
        
        # Check structure
        has_structure = self._check_structure(content)
        validation_details['has_structure'] = has_structure
        if not has_structure:
            validation_details['warnings'].append("Response lacks proper structure")
        
        # Check if meaningful
        is_meaningful = self._check_meaningful(content)
        validation_details['is_meaningful'] = is_meaningful
        if not is_meaningful:
            validation_details['issues'].append("Response is not meaningful")
        
        # Determine overall result
        if validation_details['issues']:
            result = ValidationResult.INVALID
        elif validation_details['warnings']:
            result = ValidationResult.WARNING
        else:
            result = ValidationResult.VALID
        
        return result, validation_details
    
    def _check_length(self, content: str) -> bool:
        """Check content length"""
        length = len(content.strip())
        return self.min_length <= length <= self.max_length
    
    def _check_prohibited_content(self, content: str) -> bool:
        """Check for prohibited content patterns"""
        for pattern in self.prohibited_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                logger.warning(f"Prohibited pattern found: {pattern}")
                return False
        return True
    
    def _check_structure(self, content: str) -> bool:
        """Check if content has proper structure"""
        for indicator in self.required_structure_indicators:
            if re.search(indicator, content):
                return True
        return False
    
    def _check_meaningful(self, content: str) -> bool:
        """Check if content is meaningful"""
        # Check for minimum word count
        words = content.strip().split()
        if len(words) < 5:
            return False
        
        # Check for repetitive content
        unique_words = set(words)
        if len(unique_words) / len(words) < 0.3:
            logger.warning("Response has too much repetition")
            return False
        
        # Check for coherent sentences
        sentences = re.split(r'[.!?]+', content)
        meaningful_sentences = [s for s in sentences if len(s.strip()) > 10]
        if len(meaningful_sentences) < 1:
            return False
        
        return True
    
    def validate_json(self, content: str) -> Tuple[bool, Dict]:
        """
        Validate JSON content
        
        Args:
            content: JSON string to validate
        
        Returns:
            Tuple of (is_valid, parsed_json_or_error)
        """
        import json
        
        try:
            parsed = json.loads(content)
            return True, parsed
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON: {str(e)}"
            logger.error(error_msg)
            return False, {'error': error_msg}
    
    def validate_code(self, content: str, language: str = None) -> Tuple[bool, str]:
        """
        Validate code content
        
        Args:
            content: Code to validate
            language: Programming language
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic checks
        if not content or len(content.strip()) < 10:
            return False, "Code is too short"
        
        # Check for common code patterns
        code_indicators = [
            r'function\s+\w+\s*\(',  # Function definition
            r'class\s+\w+',  # Class definition
            r'import\s+\w+',  # Import statement
            r'def\s+\w+\s*\(',  # Python function
            r'if\s*\(',  # If statement
            r'return\s+',  # Return statement
        ]
        
        has_code = any(re.search(pattern, content) for pattern in code_indicators)
        
        if not has_code:
            return False, "Content does not appear to be valid code"
        
        return True, ""
    
    def sanitize(self, content: str) -> str:
        """
        Sanitize content by removing or escaping dangerous elements
        
        Args:
            content: Content to sanitize
        
        Returns:
            Sanitized content
        """
        sanitized = content
        
        # Remove script tags
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Escape HTML entities
        html_entities = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;'
        }
        
        for char, entity in html_entities.items():
            sanitized = sanitized.replace(char, entity)
        
        return sanitized


# Global validator instance
validator = ResponseValidator()


def quick_validate(content: str) -> bool:
    """
    Quick validation check
    
    Args:
        content: Content to validate
    
    Returns:
        True if valid, False otherwise
    """
    result, details = validator.validate(content)
    return result == ValidationResult.VALID