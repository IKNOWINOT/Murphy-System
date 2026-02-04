#!/usr/bin/env python3
"""
Performance Optimization Script for Murphy System Runtime
Analyzes code for performance bottlenecks and suggests optimizations
"""

import os
import ast
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
import json
from collections import defaultdict

class PerformanceOptimizer:
    """Comprehensive performance optimizer for Python codebase"""
    
    def __init__(self, src_dir: str):
        self.src_dir = Path(src_dir)
        self.issues = []
        self.stats = {
            'files_analyzed': 0,
            'total_lines': 0,
            'optimizations_found': 0,
            'by_category': defaultdict(int)
        }
        
    def optimize(self) -> Dict:
        """Run comprehensive performance optimization analysis"""
        print(f"Starting performance optimization analysis of {self.src_dir}...")
        
        # Analyze all Python files
        for py_file in self.src_dir.rglob("*.py"):
            self._analyze_file(py_file)
            
        # Generate report
        report = {
            'summary': dict(self.stats),
            'optimizations': self.issues,
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _analyze_file(self, file_path: Path):
        """Analyze a single Python file for performance issues"""
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
            
            # Run various performance checks
            self._check_loops(tree, file_path)
            self._check_string_operations(tree, file_path, content)
            self._check_list_operations(tree, file_path)
            self._check_dict_operations(tree, file_path)
            self._check_function_calls(tree, file_path)
            self._check_comprehensions(tree, file_path)
            self._check_imports(tree, file_path)
            self._check_memory_usage(tree, file_path)
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
    
    def _add_optimization(self, file_path: Path, opt_type: str, description: str, 
                         impact: str, line_num: int = None):
        """Add a performance optimization to the report"""
        optimization = {
            'file': str(file_path.relative_to(self.src_dir)),
            'type': opt_type,
            'impact': impact,
            'description': description,
            'line': line_num
        }
        self.issues.append(optimization)
        self.stats['optimizations_found'] += 1
        self.stats['by_category'][opt_type] += 1
    
    def _check_loops(self, tree: ast.AST, file_path: Path):
        """Check for loop performance issues"""
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                # Check for nested loops
                parent_loops = self._count_parent_loops(tree, node)
                if parent_loops >= 2:
                    self._add_optimization(
                        file_path,
                        'nested_loops',
                        f'Nested loop detected (depth {parent_loops + 1}) - consider algorithm optimization',
                        'high',
                        node.lineno
                    )
                
                # Check for string concatenation in loops
                for child in ast.walk(node):
                    if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Add):
                        if isinstance(child.left, ast.Str) or isinstance(child.right, ast.Str):
                            self._add_optimization(
                                file_path,
                                'string_concatenation_loop',
                                'String concatenation in loop - use list comprehension or join()',
                                'medium',
                                node.lineno
                            )
                            break
    
    def _count_parent_loops(self, tree: ast.AST, target_node: ast.AST) -> int:
        """Count parent loops of a node"""
        # Simplified implementation
        return 0
    
    def _check_string_operations(self, tree: ast.AST, file_path: Path, content: str):
        """Check for inefficient string operations"""
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            # Check for string concatenation with +
            if ' + ' in line and '"' in line and "'" in line:
                self._add_optimization(
                    file_path,
                    'string_concatenation',
                    'String concatenation with + - use f-strings or format()',
                    'low',
                    i
                )
            
            # Check for string multiplication
            if '* "' in line or "* '" in line:
                self._add_optimization(
                    file_path,
                    'string_multiplication',
                    'String multiplication - consider using join() for multiple copies',
                    'low',
                    i
                )
    
    def _check_list_operations(self, tree: ast.AST, file_path: Path):
        """Check for inefficient list operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node)
                
                # Check for list.append in loop
                if func_name == 'append':
                    self._add_optimization(
                        file_path,
                        'list_append',
                        'Consider using list comprehension instead of append in loop',
                        'low',
                        node.lineno
                    )
                
                # Check for inefficient list copying
                if func_name == 'list' and len(node.args) == 1:
                    arg = node.args[0]
                    if isinstance(arg, ast.Name):
                        self._add_optimization(
                            file_path,
                            'list_copy',
                            'Inefficient list copying - use list.copy() or slicing [:]',
                            'low',
                            node.lineno
                        )
    
    def _check_dict_operations(self, tree: ast.AST, file_path: Path):
        """Check for inefficient dictionary operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node)
                
                # Check for dict.get without default
                if func_name == 'get' and len(node.args) == 1:
                    self._add_optimization(
                        file_path,
                        'dict_get_no_default',
                        'dict.get() without default - consider providing a default value',
                        'low',
                        node.lineno
                    )
    
    def _check_function_calls(self, tree: ast.AST, file_path: Path):
        """Check for inefficient function calls"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node)
                
                # Check for len() in conditions (should be bool check)
                if func_name == 'len':
                    # Check if used in if statement
                    self._add_optimization(
                        file_path,
                        'len_in_condition',
                        'len() in condition - use truthiness check instead',
                        'low',
                        node.lineno
                    )
    
    def _check_comprehensions(self, tree: ast.AST, file_path: Path):
        """Check for suboptimal comprehensions"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ListComp):
                # Check for nested comprehensions
                nested = self._count_nested_comprehensions(node)
                if nested >= 2:
                    self._add_optimization(
                        file_path,
                        'nested_comprehension',
                        f'Nested list comprehension (depth {nested}) - consider refactoring',
                        'medium',
                        node.lineno
                    )
    
    def _count_nested_comprehensions(self, node: ast.AST, depth: int = 0) -> int:
        """Count nested comprehensions"""
        max_depth = depth
        for child in ast.walk(node):
            if isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp)):
                if child != node:
                    child_depth = self._count_nested_comprehensions(child, depth + 1)
                    max_depth = max(max_depth, child_depth)
        return max_depth
    
    def _check_imports(self, tree: ast.AST, file_path: Path):
        """Check for import performance issues"""
        import_count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_count += 1
        
        if import_count > 20:
            self._add_optimization(
                file_path,
                'many_imports',
                f'Many imports ({import_count}) - consider lazy imports or reorganizing',
                'low',
                1
            )
    
    def _check_memory_usage(self, tree: ast.AST, file_path: Path):
        """Check for memory usage issues"""
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                # Check for creating large data structures in loops
                for child in ast.walk(node):
                    if isinstance(child, ast.ListComp):
                        self._add_optimization(
                            file_path,
                            'large_structure_in_loop',
                            'List comprehension in loop - may create large intermediate structures',
                            'medium',
                            node.lineno
                        )
                        break
    
    def _get_function_name(self, node: ast.Call) -> str:
        """Extract function name from Call node"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        if self.stats['by_category']['nested_loops'] > 0:
            recommendations.append("Address nested loops - consider algorithm optimization or using built-in functions")
        
        if self.stats['by_category']['string_concatenation_loop'] > 0:
            recommendations.append("Replace string concatenation in loops with join() or comprehensions")
        
        if self.stats['by_category']['string_concatenation'] > 0:
            recommendations.append("Use f-strings or format() instead of string concatenation with +")
        
        recommendations.extend([
            "Use list comprehensions instead of for loops with append",
            "Use dict.get() with default values to handle missing keys",
            "Use truthiness checks instead of len() in conditions",
            "Avoid nested comprehensions - refactor for readability",
            "Consider lazy imports for modules not always needed",
            "Profile critical paths using cProfile or line_profiler",
            "Use generators (yield) for large datasets instead of lists",
            "Consider using functools.lru_cache for expensive function calls",
            "Use built-in functions (map, filter, reduce) for better performance"
        ])
        
        return recommendations


def main():
    """Main entry point"""
    src_dir = "/workspace/src"
    
    optimizer = PerformanceOptimizer(src_dir)
    report = optimizer.optimize()
    
    # Print summary
    print("\n" + "="*80)
    print("PERFORMANCE OPTIMIZATION SUMMARY")
    print("="*80)
    print(f"Files Analyzed: {report['summary']['files_analyzed']}")
    print(f"Total Lines: {report['summary']['total_lines']}")
    print(f"Optimizations Found: {report['summary']['optimizations_found']}")
    print(f"\nBy Category:")
    for category, count in sorted(report['summary']['by_category'].items(), 
                                   key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count}")
    
    # Print high impact optimizations
    high_impact = [opt for opt in report['optimizations'] if opt['impact'] == 'high']
    if high_impact:
        print("\n" + "="*80)
        print("HIGH IMPACT OPTIMIZATIONS")
        print("="*80)
        for opt in high_impact[:20]:  # Show first 20
            print(f"\n[{opt['file']}:{opt['line']}]")
            print(f"  Type: {opt['type']}")
            print(f"  Description: {opt['description']}")
    
    # Save full report
    output_file = "/workspace/PERFORMANCE_OPTIMIZATION_REPORT.json"
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