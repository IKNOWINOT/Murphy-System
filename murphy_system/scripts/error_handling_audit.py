#!/usr/bin/env python3
"""
Error Handling Audit Script for Murphy System Runtime
Analyzes code for error handling patterns and suggests improvements
"""

import os
import ast
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
import json
from collections import defaultdict

class ErrorHandlingAuditor:
    """Comprehensive error handling auditor for Python codebase"""
    
    def __init__(self, src_dir: str):
        self.src_dir = Path(src_dir)
        self.issues = []
        self.stats = {
            'files_analyzed': 0,
            'total_lines': 0,
            'issues_found': 0,
            'by_severity': defaultdict(int)
        }
        
    def audit(self) -> Dict:
        """Run comprehensive error handling audit"""
        print(f"Starting error handling audit of {self.src_dir}...")
        
        # Analyze all Python files
        for py_file in self.src_dir.rglob("*.py"):
            self._audit_file(py_file)
            
        # Generate report
        report = {
            'summary': dict(self.stats),
            'issues': self.issues,
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _audit_file(self, file_path: Path):
        """Audit a single Python file for error handling issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.stats['files_analyzed'] += 1
            self.stats['total_lines'] += len(content.splitlines())
            
            # Parse AST
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError:
                return
            
            # Run various error handling checks
            self._check_exception_handling(tree, file_path)
            self._check_error_messages(tree, file_path)
            self._check_resource_cleanup(tree, file_path)
            self._check_validation(tree, file_path)
            self._check_logging(tree, file_path)
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
    
    def _add_issue(self, file_path: Path, issue_type: str, description: str, 
                   severity: str, line_num: int = None):
        """Add an error handling issue to the report"""
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
    
    def _check_exception_handling(self, tree: ast.AST, file_path: Path):
        """Check for exception handling issues"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check for bare except clauses
                if node.type is None:
                    self._add_issue(
                        file_path,
                        'bare_except',
                        'Bare except clause - should specify exception type',
                        'high',
                        node.lineno
                    )
                
                # Check for broad exception handlers
                elif isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                    # Check if it has proper handling
                    has_logging = self._has_logging_in_handler(node)
                    if not has_logging:
                        self._add_issue(
                            file_path,
                            'broad_exception_no_logging',
                            'Broad exception handler (Exception) without logging',
                            'medium',
                            node.lineno
                        )
                
                # Check for silent exception handlers
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    self._add_issue(
                        file_path,
                        'silent_exception_handler',
                        'Silent exception handler (pass) - should at least log',
                        'high',
                        node.lineno
                    )
    
    def _has_logging_in_handler(self, handler: ast.ExceptHandler) -> bool:
        """Check if exception handler has logging"""
        for node in ast.walk(handler):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node)
                if func_name in ['log', 'debug', 'info', 'warning', 'error', 'exception']:
                    return True
        return False
    
    def _check_error_messages(self, tree: ast.AST, file_path: Path):
        """Check for error message quality"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                if isinstance(node.exc, ast.Call):
                    # Check if exception has message
                    if len(node.exc.args) == 0:
                        self._add_issue(
                            file_path,
                            'exception_without_message',
                            'Exception raised without descriptive message',
                            'medium',
                            node.lineno
                    )
                    elif len(node.exc.args) == 1:
                        arg = node.exc.args[0]
                        if isinstance(arg, ast.Str) and len(arg.s) < 10:
                            self._add_issue(
                                file_path,
                                'exception_with_short_message',
                                'Exception raised with very short message',
                                'low',
                                node.lineno
                            )
    
    def _check_resource_cleanup(self, tree: ast.AST, file_path: Path):
        """Check for proper resource cleanup"""
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                # Good - using context manager
                continue
            
            if isinstance(node, ast.FunctionDef):
                # Check for file operations without context manager
                has_open = False
                has_with = False
                
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func_name = self._get_function_name(child)
                        if func_name == 'open':
                            has_open = True
                
                # Check if function uses with statement
                for child in node.body:
                    if isinstance(child, ast.With):
                        has_with = True
                        break
                
                if has_open and not has_with:
                    self._add_issue(
                        file_path,
                        'file_without_context_manager',
                        f'Function {node.name} uses open() but not with statement',
                        'high',
                        node.lineno
                    )
    
    def _check_validation(self, tree: ast.AST, file_path: Path):
        """Check for input validation"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function has parameters
                has_params = len(node.args.args) > 0
                
                if has_params:
                    # Check if function has validation logic
                    has_validation = False
                    
                    # Look for type checks, value checks, etc.
                    for child in ast.walk(node):
                        if isinstance(child, ast.If):
                            # Check if it's a validation if statement
                            for grandchild in ast.walk(child):
                                if isinstance(grandchild, ast.Raise):
                                    has_validation = True
                                    break
                                if isinstance(grandchild, ast.Call):
                                    func_name = self._get_function_name(grandchild)
                                    if func_name in ['assert', 'validate', 'check']:
                                        has_validation = True
                                        break
                    
                    if not has_validation and len(node.body) > 10:
                        self._add_issue(
                            file_path,
                            'missing_validation',
                            f'Function {node.name} has parameters but may lack validation',
                            'low',
                            node.lineno
                        )
    
    def _check_logging(self, tree: ast.AST, file_path: Path):
        """Check for logging practices"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node)
                
                # Check for print statements (should use logging)
                if func_name == 'print':
                    self._add_issue(
                        file_path,
                        'print_statement',
                        'Use logging module instead of print()',
                        'low',
                        node.lineno
                    )
                
                # Check for logging without exception info
                if func_name in ['error', 'exception', 'warning']:
                    # Check if it's in an except handler
                    parent = self._find_parent_exception_handler(node, tree)
                    if parent and not self._has_exc_info(node):
                        self._add_issue(
                            file_path,
                            'logging_without_exc_info',
                            'Logging in exception handler without exc_info parameter',
                            'medium',
                            node.lineno
                        )
    
    def _find_parent_exception_handler(self, node: ast.AST, tree: ast.AST) -> bool:
        """Check if node is in an exception handler"""
        # Simplified implementation
        for handler in ast.walk(tree):
            if isinstance(handler, ast.ExceptHandler):
                for child in ast.walk(handler):
                    if child == node:
                        return True
        return False
    
    def _has_exc_info(self, node: ast.Call) -> bool:
        """Check if logging call has exc_info parameter"""
        for keyword in node.keywords:
            if keyword.arg == 'exc_info':
                return True
        return False
    
    def _get_function_name(self, node: ast.Call) -> str:
        """Extract function name from Call node"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""
    
    def _generate_recommendations(self) -> List[str]:
        """Generate error handling recommendations"""
        recommendations = []
        
        if self.stats['by_severity']['high'] > 0:
            recommendations.append("URGENT: Address high-severity error handling issues")
        
        recommendations.extend([
            "Always specify exception types in except clauses",
            "Add logging to all exception handlers",
            "Provide descriptive error messages in exceptions",
            "Use context managers (with statements) for resource management",
            "Add input validation to all user-facing functions",
            "Replace print() statements with logging",
            "Use exc_info=True when logging exceptions",
            "Implement graceful degradation where appropriate",
            "Add recovery mechanisms for transient failures",
            "Document expected exceptions in docstrings",
            "Use custom exception classes for domain-specific errors",
            "Implement retry logic for network operations",
            "Add timeout handling for long-running operations",
            "Validate all external inputs and data",
            "Implement proper error propagation"
        ])
        
        return recommendations


def main():
    """Main entry point"""
    import argparse

    # Determine default paths relative to this script's location
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    default_src_dir = repo_root / "src"
    default_output_file = repo_root / "ERROR_HANDLING_AUDIT_REPORT.json"

    parser = argparse.ArgumentParser(
        description="Audit error handling patterns in Python codebase"
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=default_src_dir,
        help=f"Source directory to audit (default: {default_src_dir})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output_file,
        help=f"Output JSON report file (default: {default_output_file})",
    )
    args = parser.parse_args()

    src_dir = args.src_dir
    output_file = args.output

    auditor = ErrorHandlingAuditor(str(src_dir))
    report = auditor.audit()
    
    # Print summary
    print("\n" + "="*80)
    print("ERROR HANDLING AUDIT SUMMARY")
    print("="*80)
    print(f"Files Analyzed: {report['summary']['files_analyzed']}")
    print(f"Total Lines: {report['summary']['total_lines']}")
    print(f"Issues Found: {report['summary']['issues_found']}")
    print(f"\nBy Severity:")
    for severity, count in sorted(report['summary']['by_severity'].items()):
        print(f"  {severity.upper()}: {count}")
    
    # Print high severity issues
    high_severity = [i for i in report['issues'] if i['severity'] == 'high']
    if high_severity:
        print("\n" + "="*80)
        print("HIGH SEVERITY ISSUES")
        print("="*80)
        for issue in high_severity[:20]:  # Show first 20
            print(f"\n[{issue['file']}:{issue['line']}]")
            print(f"  Type: {issue['type']}")
            print(f"  Description: {issue['description']}")
    
    # Save full report
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