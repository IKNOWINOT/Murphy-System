#!/usr/bin/env python3
"""
Security Audit Script for Murphy System Runtime
Analyzes Python source code for potential security vulnerabilities
"""

import os
import re
import ast
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
import json

class SecurityAuditor:
    """Comprehensive security auditor for Python codebase"""
    
    def __init__(self, src_dir: str):
        self.src_dir = Path(src_dir)
        self.issues = []
        self.stats = {
            'files_analyzed': 0,
            'total_lines': 0,
            'issues_found': 0,
            'by_severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        }
        
    def audit(self) -> Dict:
        """Run comprehensive security audit"""
        print(f"Starting security audit of {self.src_dir}...")
        
        # Analyze all Python files
        for py_file in self.src_dir.rglob("*.py"):
            self._audit_file(py_file)
            
        # Generate report
        report = {
            'summary': self.stats,
            'issues': self.issues,
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _audit_file(self, file_path: Path):
        """Audit a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.stats['files_analyzed'] += 1
            self.stats['total_lines'] += len(content.splitlines())
            
            # Parse AST
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError:
                self._add_issue(
                    file_path,
                    'syntax_error',
                    'Syntax error in file - may indicate code corruption',
                    'high'
                )
                return
            
            # Run various security checks
            self._check_imports(tree, file_path)
            self._check_function_calls(tree, file_path, content)
            self._check_string_operations(tree, file_path, content)
            self._check_hardcoded_secrets(file_path, content)
            self._check_input_validation(tree, file_path)
            self._check_error_handling(tree, file_path)
            self._check_logging(tree, file_path)
            self._check_sql_injection(tree, file_path, content)
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
    
    def _add_issue(self, file_path: Path, issue_type: str, description: str, 
                   severity: str, line_num: int = None):
        """Add a security issue to the report"""
        issue = {
            'file': str(file_path.relative_to(self.src_dir)),
            'type': issue_type,
            'severity': severity,
            'description': description,
            'line': line_num
        }
        self.issues.append(issue)
        self.stats['issues_found'] += 1
        self.stats['by_severity'][severity] += 1
    
    def _check_imports(self, tree: ast.AST, file_path: Path):
        """Check for potentially dangerous imports"""
        dangerous_imports = {
            'pickle': 'Uses pickle which can execute arbitrary code when deserializing untrusted data',
            'marshal': 'Uses marshal which can execute arbitrary code',
            'eval': 'Direct import of eval function',
            'exec': 'Direct import of exec function',
            'subprocess': 'Uses subprocess - ensure input is properly sanitized',
            'os.system': 'Uses os.system - ensure input is properly sanitized',
            'input': 'Uses input() - ensure proper validation and sanitization'
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in dangerous_imports:
                        self._add_issue(
                            file_path,
                            'dangerous_import',
                            f"{dangerous_imports[alias.name]}",
                            'medium',
                            node.lineno
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module in dangerous_imports:
                    self._add_issue(
                        file_path,
                        'dangerous_import',
                        f"{dangerous_imports[node.module]}",
                        'medium',
                        node.lineno
                    )
    
    def _check_function_calls(self, tree: ast.AST, file_path: Path, content: str):
        """Check for dangerous function calls"""
        dangerous_calls = {
            'eval': 'Direct use of eval() - can execute arbitrary code',
            'exec': 'Direct use of exec() - can execute arbitrary code',
            'compile': 'Direct use of compile() - can execute arbitrary code',
            '__import__': 'Direct use of __import__() - can import arbitrary modules'
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node)
                if func_name in dangerous_calls:
                    self._add_issue(
                        file_path,
                        'dangerous_function_call',
                        dangerous_calls[func_name],
                        'critical',
                        node.lineno
                    )
    
    def _get_function_name(self, node: ast.Call) -> str:
        """Extract function name from Call node"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""
    
    def _check_string_operations(self, tree: ast.AST, file_path: Path, content: str):
        """Check for string concatenation in potentially dangerous contexts"""
        # Check for string concatenation with user input
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                if isinstance(node.op, ast.Add):
                    self._add_issue(
                        file_path,
                        'string_concatenation',
                        'String concatenation detected - consider using f-strings or format()',
                        'low',
                        node.lineno
                    )
    
    def _check_hardcoded_secrets(self, file_path: Path, content: str):
        """Check for hardcoded secrets, passwords, API keys"""
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password found'),
            (r'api_key\s*=\s*["\'][^"\']+["\']', 'Hardcoded API key found'),
            (r'secret\s*=\s*["\'][^"\']+["\']', 'Hardcoded secret found'),
            (r'token\s*=\s*["\'][^"\']+["\']', 'Hardcoded token found'),
            (r'["\'][A-Za-z0-9]{32,}["\']', 'Possible hardcoded secret (32+ characters)'),
        ]
        
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            for pattern, description in secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self._add_issue(
                        file_path,
                        'hardcoded_secret',
                        description,
                        'high',
                        i
                    )
                    break
    
    def _check_input_validation(self, tree: ast.AST, file_path: Path):
        """Check for missing input validation"""
        # Look for functions that take parameters but don't validate them
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                has_params = len(node.args.args) > 0
                has_validation = False
                
                # Check if function has validation logic
                for child in ast.walk(node):
                    if isinstance(child, ast.Raise):
                        has_validation = True
                        break
                
                if has_params and not has_validation and len(node.body) > 5:
                    # Function with parameters but no validation
                    self._add_issue(
                        file_path,
                        'missing_input_validation',
                        f'Function {node.name} has parameters but may lack validation',
                        'low',
                        node.lineno
                    )
    
    def _check_error_handling(self, tree: ast.AST, file_path: Path):
        """Check for poor error handling patterns"""
        # Check for bare except clauses
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    self._add_issue(
                        file_path,
                        'bare_except',
                        'Bare except clause - should specify exception type',
                        'medium',
                        node.lineno
                    )
                elif isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                    # Check if it's a broad exception handler
                    self._add_issue(
                        file_path,
                        'broad_exception_handler',
                        'Broad exception handler (Exception) - consider specific exceptions',
                        'low',
                        node.lineno
                    )
    
    def _check_logging(self, tree: ast.AST, file_path: Path):
        """Check for logging security issues"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node)
                if func_name in ['print', 'log', 'debug', 'info', 'warning', 'error']:
                    # Check if logging sensitive data
                    if isinstance(node.func, ast.Attribute):
                        self._add_issue(
                            file_path,
                            'potentially_sensitive_logging',
                            f'{func_name}() call - ensure no sensitive data is logged',
                            'low',
                            node.lineno
                        )
    
    def _check_sql_injection(self, tree: ast.AST, file_path: Path, content: str):
        """Check for potential SQL injection vulnerabilities"""
        # Check for string formatting in SQL queries
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE']
        lines = content.splitlines()
        
        for i, line in enumerate(lines, 1):
            # Check for SQL keywords with string formatting
            if any(keyword in line.upper() for keyword in sql_keywords):
                if '%' in line or '.format(' in line or '{' in line:
                    self._add_issue(
                        file_path,
                        'potential_sql_injection',
                        'Potential SQL injection - use parameterized queries',
                        'high',
                        i
                    )
    
    def _generate_recommendations(self) -> List[str]:
        """Generate security recommendations based on findings"""
        recommendations = []
        
        if self.stats['by_severity']['critical'] > 0:
            recommendations.append("CRITICAL: Immediately address all critical security issues")
        
        if self.stats['by_severity']['high'] > 0:
            recommendations.append("HIGH: Address high-severity issues as soon as possible")
        
        recommendations.extend([
            "Implement input validation for all user-facing functions",
            "Use parameterized queries for all database operations",
            "Remove any hardcoded secrets and use environment variables",
            "Implement proper error handling with specific exception types",
            "Add security logging for authentication and authorization events",
            "Regularly update dependencies to patch known vulnerabilities",
            "Consider using security linters like bandit in CI/CD pipeline"
        ])
        
        return recommendations


def main():
    """Main entry point"""
    src_dir = "/workspace/src"
    
    auditor = SecurityAuditor(src_dir)
    report = auditor.audit()
    
    # Print summary
    print("\n" + "="*80)
    print("SECURITY AUDIT SUMMARY")
    print("="*80)
    print(f"Files Analyzed: {report['summary']['files_analyzed']}")
    print(f"Total Lines: {report['summary']['total_lines']}")
    print(f"Issues Found: {report['summary']['issues_found']}")
    print(f"\nBy Severity:")
    for severity, count in report['summary']['by_severity'].items():
        print(f"  {severity.upper()}: {count}")
    
    # Print critical and high issues
    critical_issues = [i for i in report['issues'] if i['severity'] in ['critical', 'high']]
    if critical_issues:
        print("\n" + "="*80)
        print("CRITICAL & HIGH PRIORITY ISSUES")
        print("="*80)
        for issue in critical_issues[:20]:  # Show first 20
            print(f"\n[{issue['severity'].upper()}] {issue['file']}:{issue['line']}")
            print(f"  Type: {issue['type']}")
            print(f"  Description: {issue['description']}")
    
    # Save full report
    output_file = "/workspace/SECURITY_AUDIT_REPORT.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nFull report saved to: {output_file}")
    
    # Print recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    for rec in report['recommendations']:
        print(f"• {rec}")
    
    return report


if __name__ == "__main__":
    main()