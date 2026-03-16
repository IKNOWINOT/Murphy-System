#!/usr/bin/env python3
"""
Memory Optimization Script for Murphy System Runtime
Analyzes code for memory usage patterns and suggests optimizations
"""

import os
import ast
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
import json
from collections import defaultdict

class MemoryOptimizer:
    """Comprehensive memory optimizer for Python codebase"""
    
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
        """Run comprehensive memory optimization analysis"""
        print(f"Starting memory optimization analysis of {self.src_dir}...")
        
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
        """Analyze a single Python file for memory issues"""
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
            
            # Run various memory checks
            self._check_global_variables(tree, file_path)
            self._check_large_data_structures(tree, file_path)
            self._check_closures(tree, file_path)
            self._check_class_design(tree, file_path)
            self._check_generators(tree, file_path)
            self._check_caching(tree, file_path)
            self._check_object_creation(tree, file_path)
            self._check_memory_leaks(tree, file_path)
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
    
    def _add_optimization(self, file_path: Path, opt_type: str, description: str, 
                         impact: str, line_num: int = None):
        """Add a memory optimization to the report"""
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
    
    def _check_global_variables(self, tree: ast.AST, file_path: Path):
        """Check for global variables that may cause memory issues"""
        global_vars = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                global_vars.extend(node.names)
        
        if global_vars:
            self._add_optimization(
                file_path,
                'global_variables',
                f'Global variables detected: {", ".join(global_vars[:5])} - consider using class-level or module-level constants',
                'medium',
                1
            )
    
    def _check_large_data_structures(self, tree: ast.AST, file_path: Path):
        """Check for potentially large data structures"""
        for node in ast.walk(tree):
            if isinstance(node, ast.List):
                # Check for large list literals
                if len(node.elts) > 100:
                    self._add_optimization(
                        file_path,
                        'large_list_literal',
                        f'Large list literal ({len(node.elts)} items) - consider loading from file or generating on demand',
                        'high',
                        node.lineno
                    )
            
            elif isinstance(node, ast.Dict):
                # Check for large dict literals
                if len(node.keys) > 100:
                    self._add_optimization(
                        file_path,
                        'large_dict_literal',
                        f'Large dict literal ({len(node.keys)} items) - consider loading from file or using database',
                        'high',
                        node.lineno
                    )
    
    def _check_closures(self, tree: ast.AST, file_path: Path):
        """Check for memory-intensive closures"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Lambda):
                # Check for nested lambdas
                if self._is_nested_lambda(node):
                    self._add_optimization(
                        file_path,
                        'nested_lambda',
                        'Nested lambda function - consider using named functions or functools.partial',
                        'low',
                        node.lineno
                    )
    
    def _is_nested_lambda(self, node: ast.AST) -> bool:
        """Check if lambda is nested"""
        return any(isinstance(child, ast.Lambda) and child != node 
                   for child in ast.walk(node))
    
    def _check_class_design(self, tree: ast.AST, file_path: Path):
        """Check for class design memory issues"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check for large number of instance variables
                instance_attrs = []
                for child in node.body:
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Name):
                                instance_attrs.append(target.id)
                
                if len(instance_attrs) > 20:
                    self._add_optimization(
                        file_path,
                        'many_instance_variables',
                        f'Class {node.name} has many instance variables ({len(instance_attrs)}) - consider using __slots__',
                        'medium',
                        node.lineno
                    )
                
                # Check for large number of methods
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                if len(methods) > 30:
                    self._add_optimization(
                        file_path,
                        'many_methods',
                        f'Class {node.name} has many methods ({len(methods)}) - consider splitting into multiple classes',
                        'medium',
                        node.lineno
                    )
    
    def _check_generators(self, tree: ast.AST, file_path: Path):
        """Check for opportunities to use generators"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for functions that return lists
                if self._returns_list(node):
                    self._add_optimization(
                        file_path,
                        'generator_opportunity',
                        f'Function {node.name} returns list - consider using generator (yield)',
                        'medium',
                        node.lineno
                    )
    
    def _returns_list(self, node: ast.FunctionDef) -> bool:
        """Check if function returns a list"""
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value:
                if isinstance(child.value, ast.List):
                    return True
                elif isinstance(child.value, ast.Call):
                    if self._get_function_name(child.value) == 'list':
                        return True
        return False
    
    def _get_function_name(self, node: ast.Call) -> str:
        """Extract function name from Call node"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""
    
    def _check_caching(self, tree: ast.AST, file_path: Path):
        """Check for caching opportunities"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for pure functions without caching
                if self._is_pure_function(node) and not self._has_decorator(node, 'lru_cache'):
                    self._add_optimization(
                        file_path,
                        'caching_opportunity',
                        f'Function {node.name} appears to be a pure function - consider adding @lru_cache decorator',
                        'low',
                        node.lineno
                    )
    
    def _is_pure_function(self, node: ast.FunctionDef) -> bool:
        """Check if function appears to be pure"""
        # Simplified check - pure functions don't modify state
        # In practice, this would require more sophisticated analysis
        return len(node.args.args) > 0 and len(node.body) > 3
    
    def _has_decorator(self, node: ast.FunctionDef, decorator_name: str) -> bool:
        """Check if function has a specific decorator"""
        return any(isinstance(d, ast.Name) and d.id == decorator_name 
                   for d in node.decorator_list)
    
    def _check_object_creation(self, tree: ast.AST, file_path: Path):
        """Check for excessive object creation"""
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                # Check for object creation in loops
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func_name = self._get_function_name(child)
                        if func_name and func_name[0].isupper():  # Class name
                            self._add_optimization(
                                file_path,
                                'object_creation_in_loop',
                                f'Object creation in loop - consider object pooling or reusing objects',
                                'high',
                                node.lineno
                            )
                            break
    
    def _check_memory_leaks(self, tree: ast.AST, file_path: Path):
        """Check for potential memory leaks"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Check for accumulating data structures
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id.endswith('_cache') or target.id.endswith('_buffer'):
                            self._add_optimization(
                                file_path,
                                'potential_memory_leak',
                                f'Accumulating data structure {target.id} - implement size limits or LRU eviction',
                                'medium',
                                node.lineno
                            )
    
    def _generate_recommendations(self) -> List[str]:
        """Generate memory optimization recommendations"""
        recommendations = []
        
        if self.stats['by_category']['large_list_literal'] > 0:
            recommendations.append("Load large data from files or databases instead of inline literals")
        
        if self.stats['by_category']['large_dict_literal'] > 0:
            recommendations.append("Use databases or key-value stores for large dictionaries")
        
        if self.stats['by_category']['object_creation_in_loop'] > 0:
            recommendations.append("Implement object pooling or reuse objects to reduce allocations")
        
        if self.stats['by_category']['many_instance_variables'] > 0:
            recommendations.append("Use __slots__ in classes with many instance variables to reduce memory")
        
        if self.stats['by_category']['generator_opportunity'] > 0:
            recommendations.append("Replace list returns with generators for large datasets")
        
        recommendations.extend([
            "Use weak references for cache keys to prevent memory leaks",
            "Implement proper cleanup in __del__ methods",
            "Use context managers (with statements) for resource cleanup",
            "Consider using memory views for large binary data",
            "Use array module or numpy for numerical data instead of lists",
            "Implement LRU caching with size limits",
            "Profile memory usage using memory_profiler or tracemalloc",
            "Avoid circular references that prevent garbage collection",
            "Use __slots__ for classes with fixed attributes",
            "Consider using dataclasses for memory-efficient data containers"
        ])
        
        return recommendations


def main():
    """Main entry point"""
    src_dir = "/workspace/src"
    
    optimizer = MemoryOptimizer(src_dir)
    report = optimizer.optimize()
    
    # Print summary
    print("\n" + "="*80)
    print("MEMORY OPTIMIZATION SUMMARY")
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
    output_file = "/workspace/MEMORY_OPTIMIZATION_REPORT.json"
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