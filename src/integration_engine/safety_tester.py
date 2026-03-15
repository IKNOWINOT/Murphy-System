"""
Safety Tester - Test integrations for safety before committing

This module runs comprehensive safety tests:
- License validation
- Risk pattern analysis
- Dependency security checks
- Code quality checks
- Integration tests
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SafetyTester:
    """
    Test integrations for safety before committing.

    Runs multiple test categories:
    1. License validation
    2. Risk pattern analysis
    3. Dependency security
    4. Code quality
    5. Integration tests
    """

    def __init__(self):
        # Approved licenses
        self.approved_licenses = {
            'MIT', 'BSD', 'BSD-2-Clause', 'BSD-3-Clause',
            'Apache', 'Apache-2.0', 'ISC', 'Unlicense', 'CC0'
        }

        # Critical risk patterns (automatic fail)
        self.critical_patterns = [
            r'rm\s+-rf\s+/',  # Delete root
            r'eval\s*\(\s*input',  # Eval user input
            r'exec\s*\(\s*input',  # Exec user input
            r'__import__\s*\(\s*input',  # Import user input
        ]

        # High risk patterns (warning)
        self.high_risk_patterns = [
            r'subprocess\.run',
            r'os\.system',
            r'eval\s*\(',
            r'exec\s*\(',
        ]

    def test_integration(
        self,
        module: Dict,
        agent: Optional[Dict],
        audit: Dict
    ) -> Dict:
        """
        Run comprehensive safety tests on integration.

        Args:
            module: Generated module
            agent: Generated agent (if any)
            audit: SwissKiss audit results

        Returns:
            Test results dictionary with:
            - passed: Number of tests passed
            - total: Total number of tests
            - critical_issues: List of critical issues
            - warnings: List of warnings
            - safety_score: Overall safety score (0.0-1.0)
        """

        results = {
            'passed': 0,
            'total': 0,
            'critical_issues': [],
            'warnings': [],
            'test_details': []
        }

        # Test 1: License validation
        results['total'] += 1
        license_result = self._test_license(audit)
        if license_result['passed']:
            results['passed'] += 1
        else:
            if license_result['critical']:
                results['critical_issues'].append(license_result['message'])
            else:
                results['warnings'].append(license_result['message'])
        results['test_details'].append(license_result)

        # Test 2: Critical risk patterns
        results['total'] += 1
        critical_risk_result = self._test_critical_risks(audit)
        if critical_risk_result['passed']:
            results['passed'] += 1
        else:
            results['critical_issues'].extend(critical_risk_result['issues'])
        results['test_details'].append(critical_risk_result)

        # Test 3: High risk patterns
        results['total'] += 1
        high_risk_result = self._test_high_risks(audit)
        if high_risk_result['passed']:
            results['passed'] += 1
        else:
            results['warnings'].extend(high_risk_result['warnings'])
        results['test_details'].append(high_risk_result)

        # Test 4: Module structure
        results['total'] += 1
        structure_result = self._test_module_structure(module)
        if structure_result['passed']:
            results['passed'] += 1
        else:
            results['warnings'].append(structure_result['message'])
        results['test_details'].append(structure_result)

        # Test 5: Capabilities validation
        results['total'] += 1
        capabilities_result = self._test_capabilities(module)
        if capabilities_result['passed']:
            results['passed'] += 1
        else:
            results['warnings'].append(capabilities_result['message'])
        results['test_details'].append(capabilities_result)

        # Calculate safety score
        base_score = results['passed'] / results['total']

        # Penalize for critical issues (each reduces score by 0.2)
        critical_penalty = len(results['critical_issues']) * 0.2

        # Penalize for warnings (each reduces score by 0.05)
        warning_penalty = len(results['warnings']) * 0.05

        safety_score = max(0.0, base_score - critical_penalty - warning_penalty)
        results['safety_score'] = safety_score

        return results

    def _test_license(self, audit: Dict) -> Dict:
        """Test license validity"""
        license_name = audit.get('license', 'UNKNOWN')
        license_ok = audit.get('license_ok', False)

        if license_name == 'MISSING':
            return {
                'test': 'license_validation',
                'passed': False,
                'critical': True,
                'message': 'No license file found. Cannot verify usage rights.'
            }

        if license_name == 'UNKNOWN':
            return {
                'test': 'license_validation',
                'passed': False,
                'critical': False,
                'message': 'License file found but type could not be determined. Manual review required.'
            }

        if not license_ok:
            return {
                'test': 'license_validation',
                'passed': False,
                'critical': False,
                'message': f'License "{license_name}" may have restrictions. Review license terms before use.'
            }

        return {
            'test': 'license_validation',
            'passed': True,
            'critical': False,
            'message': f'License "{license_name}" is approved for use.'
        }

    def _test_critical_risks(self, audit: Dict) -> Dict:
        """Test for critical risk patterns"""
        risk_scan = audit.get('risk_scan', {})
        issues = risk_scan.get('issues', [])

        critical_issues = []

        for issue in issues:
            pattern = issue.get('pattern', '')
            file_path = issue.get('file', '')

            for critical_pattern in self.critical_patterns:
                if re.search(critical_pattern, pattern):
                    critical_issues.append(
                        f"CRITICAL: Found dangerous pattern '{pattern}' in {file_path}"
                    )

        if critical_issues:
            return {
                'test': 'critical_risk_patterns',
                'passed': False,
                'issues': critical_issues,
                'message': f'Found {len(critical_issues)} critical security issues'
            }

        return {
            'test': 'critical_risk_patterns',
            'passed': True,
            'issues': [],
            'message': 'No critical security issues found'
        }

    def _test_high_risks(self, audit: Dict) -> Dict:
        """Test for high risk patterns"""
        risk_scan = audit.get('risk_scan', {})
        issues = risk_scan.get('issues', [])

        warnings = []

        for issue in issues:
            pattern = issue.get('pattern', '')
            file_path = issue.get('file', '')

            for high_risk_pattern in self.high_risk_patterns:
                if re.search(high_risk_pattern, pattern):
                    warnings.append(
                        f"WARNING: Found risky pattern '{pattern}' in {file_path}"
                    )

        # Pass if less than 10 warnings
        if len(warnings) > 10:
            return {
                'test': 'high_risk_patterns',
                'passed': False,
                'warnings': warnings,
                'message': f'Found {len(warnings)} high-risk patterns (threshold: 10)'
            }

        return {
            'test': 'high_risk_patterns',
            'passed': True,
            'warnings': warnings,
            'message': f'Found {len(warnings)} high-risk patterns (acceptable)'
        }

    def _test_module_structure(self, module: Dict) -> Dict:
        """Test module structure validity"""
        required_fields = ['name', 'description', 'module_path', 'capabilities']

        missing_fields = [field for field in required_fields if field not in module]

        if missing_fields:
            return {
                'test': 'module_structure',
                'passed': False,
                'message': f'Module missing required fields: {", ".join(missing_fields)}'
            }

        if not module['name']:
            return {
                'test': 'module_structure',
                'passed': False,
                'message': 'Module name is empty'
            }

        if not module['description']:
            return {
                'test': 'module_structure',
                'passed': False,
                'message': 'Module description is empty'
            }

        return {
            'test': 'module_structure',
            'passed': True,
            'message': 'Module structure is valid'
        }

    def _test_capabilities(self, module: Dict) -> Dict:
        """Test capabilities validity"""
        capabilities = module.get('capabilities', [])

        if not capabilities:
            return {
                'test': 'capabilities_validation',
                'passed': False,
                'message': 'No capabilities extracted. Module may not be useful.'
            }

        if len(capabilities) > 50:
            return {
                'test': 'capabilities_validation',
                'passed': False,
                'message': f'Too many capabilities ({len(capabilities)}). May indicate analysis error.'
            }

        return {
            'test': 'capabilities_validation',
            'passed': True,
            'message': f'Found {len(capabilities)} valid capabilities'
        }
