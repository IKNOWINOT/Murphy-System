"""
Static Code Analyzer

Analyzes Python code without executing it using AST parsing.

Owner: INONI LLC / Corey Post (corey.gfc@gmail.com)
"""

import ast
import inspect
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """Information about a function or method"""
    name: str
    docstring: Optional[str]
    parameters: List[Dict[str, Any]]
    return_type: Optional[str]
    is_async: bool
    is_method: bool
    class_name: Optional[str]
    decorators: List[str]
    line_number: int
    uses_random: bool = False
    uses_network: bool = False
    uses_filesystem: bool = False
    uses_time: bool = False
    uses_external_api: bool = False


@dataclass
class ClassInfo:
    """Information about a class"""
    name: str
    docstring: Optional[str]
    methods: List[FunctionInfo]
    base_classes: List[str]
    decorators: List[str]
    line_number: int


@dataclass
class ImportInfo:
    """Information about an import"""
    module: str
    names: List[str]
    alias: Optional[str]
    is_from_import: bool


@dataclass
class CodeStructure:
    """Complete structure of analyzed code"""
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    global_variables: List[Dict[str, Any]] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)

    # Analysis flags
    uses_random: bool = False
    uses_network: bool = False
    uses_filesystem: bool = False
    uses_database: bool = False
    uses_subprocess: bool = False
    uses_threading: bool = False


class StaticAnalyzer:
    """
    Analyzes Python source code without executing it.

    Uses AST (Abstract Syntax Tree) parsing to extract:
    - Functions and methods
    - Classes
    - Imports and dependencies
    - Type hints
    - Docstrings
    - Usage patterns (network, filesystem, etc.)
    """

    # Modules that indicate specific usage patterns
    RANDOM_MODULES = {'random', 'numpy.random', 'secrets', 'uuid'}
    NETWORK_MODULES = {'requests', 'urllib', 'http', 'socket', 'aiohttp', 'httpx'}
    FILESYSTEM_MODULES = {'os', 'pathlib', 'shutil', 'glob', 'tempfile'}
    DATABASE_MODULES = {'sqlite3', 'psycopg2', 'pymongo', 'sqlalchemy', 'redis'}
    SUBPROCESS_MODULES = {'subprocess', 'os.system', 'os.popen'}
    THREADING_MODULES = {'threading', 'multiprocessing', 'asyncio', 'concurrent'}
    TIME_MODULES = {'time', 'datetime'}

    def __init__(self):
        self.current_class: Optional[str] = None
        self.imported_modules: Set[str] = set()

    def analyze_file(self, file_path: str) -> CodeStructure:
        """
        Analyze a Python file and extract its structure.

        Args:
            file_path: Path to Python file

        Returns:
            CodeStructure object with analysis results
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            return self.analyze_source(source_code)

        except Exception as exc:
            # Return empty structure on error
            logger.debug("Caught exception: %s", exc)
            structure = CodeStructure()
            structure.dependencies.add(f"ERROR: {str(exc)}")
            return structure

    def analyze_source(self, source_code: str) -> CodeStructure:
        """
        Analyze Python source code.

        Args:
            source_code: Python source code as string

        Returns:
            CodeStructure object with analysis results
        """
        try:
            tree = ast.parse(source_code)
            structure = CodeStructure()

            # First pass: collect imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self._process_import(node, structure)
                elif isinstance(node, ast.ImportFrom):
                    self._process_import_from(node, structure)

            # Second pass: analyze structure
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    if self.current_class is None:  # Top-level function
                        func_info = self._process_function(node, is_method=False)
                        structure.functions.append(func_info)

                        # Check if it's an entry point
                        if func_info.name in ['main', 'run', 'execute']:
                            structure.entry_points.append(func_info.name)

                elif isinstance(node, ast.ClassDef):
                    class_info = self._process_class(node)
                    structure.classes.append(class_info)

                elif isinstance(node, ast.Assign):
                    # Global variable assignment
                    if hasattr(node, 'targets'):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                structure.global_variables.append({
                                    'name': target.id,
                                    'line': node.lineno
                                })

            # Set usage flags based on imports
            structure.uses_random = bool(self.imported_modules & self.RANDOM_MODULES)
            structure.uses_network = bool(self.imported_modules & self.NETWORK_MODULES)
            structure.uses_filesystem = bool(self.imported_modules & self.FILESYSTEM_MODULES)
            structure.uses_database = bool(self.imported_modules & self.DATABASE_MODULES)
            structure.uses_subprocess = bool(self.imported_modules & self.SUBPROCESS_MODULES)
            structure.uses_threading = bool(self.imported_modules & self.THREADING_MODULES)

            structure.dependencies = self.imported_modules.copy()

            return structure

        except SyntaxError as exc:
            # Return structure with error
            structure = CodeStructure()
            structure.dependencies.add(f"SYNTAX_ERROR: {str(exc)}")
            return structure

    def _process_import(self, node: ast.Import, structure: CodeStructure):
        """Process import statement"""
        for alias in node.names:
            module_name = alias.name
            self.imported_modules.add(module_name)
            structure.imports.append(ImportInfo(
                module=module_name,
                names=[],
                alias=alias.asname,
                is_from_import=False
            ))

    def _process_import_from(self, node: ast.ImportFrom, structure: CodeStructure):
        """Process from...import statement"""
        if node.module:
            self.imported_modules.add(node.module)
            names = [alias.name for alias in node.names]
            structure.imports.append(ImportInfo(
                module=node.module,
                names=names,
                alias=None,
                is_from_import=True
            ))

    def _process_function(self, node: ast.FunctionDef, is_method: bool = False) -> FunctionInfo:
        """Process function or method definition"""
        # Extract docstring
        docstring = ast.get_docstring(node)

        # Extract parameters
        parameters = []
        for arg in node.args.args:
            param_info = {
                'name': arg.arg,
                'type': self._get_type_annotation(arg.annotation),
                'default': None
            }
            parameters.append(param_info)

        # Add defaults
        defaults = node.args.defaults
        if defaults:
            # Defaults are aligned to the right
            num_defaults = len(defaults)
            for i, default in enumerate(defaults):
                param_idx = len(parameters) - num_defaults + i
                if param_idx >= 0:
                    parameters[param_idx]['default'] = self._get_default_value(default)

        # Extract return type
        return_type = self._get_type_annotation(node.returns)

        # Extract decorators
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]

        # Analyze function body for usage patterns
        uses_random = self._check_usage(node, self.RANDOM_MODULES)
        uses_network = self._check_usage(node, self.NETWORK_MODULES)
        uses_filesystem = self._check_usage(node, self.FILESYSTEM_MODULES)
        uses_time = self._check_usage(node, self.TIME_MODULES)

        return FunctionInfo(
            name=node.name,
            docstring=docstring,
            parameters=parameters,
            return_type=return_type,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=is_method,
            class_name=self.current_class,
            decorators=decorators,
            line_number=node.lineno,
            uses_random=uses_random,
            uses_network=uses_network,
            uses_filesystem=uses_filesystem,
            uses_time=uses_time,
        )

    def _process_class(self, node: ast.ClassDef) -> ClassInfo:
        """Process class definition"""
        # Extract docstring
        docstring = ast.get_docstring(node)

        # Extract base classes
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(f"{base.value.id}.{base.attr}")

        # Extract decorators
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]

        # Process methods
        self.current_class = node.name
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._process_function(item, is_method=True)
                methods.append(method_info)
        self.current_class = None

        return ClassInfo(
            name=node.name,
            docstring=docstring,
            methods=methods,
            base_classes=base_classes,
            decorators=decorators,
            line_number=node.lineno
        )

    def _get_type_annotation(self, annotation) -> Optional[str]:
        """Extract type annotation as string"""
        if annotation is None:
            return None

        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value)
        elif isinstance(annotation, ast.Subscript):
            # Handle List[int], Dict[str, int], etc.
            value = self._get_type_annotation(annotation.value)
            slice_val = self._get_type_annotation(annotation.slice)
            return f"{value}[{slice_val}]"
        elif isinstance(annotation, ast.Tuple):
            # Handle Tuple[int, str]
            elements = [self._get_type_annotation(elt) for elt in annotation.elts]
            return f"({', '.join(elements)})"
        else:
            return "Any"

    def _get_default_value(self, node) -> Any:
        """Extract default value from AST node"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.List):
            return []
        elif isinstance(node, ast.Dict):
            return {}
        else:
            return None

    def _get_decorator_name(self, decorator) -> str:
        """Extract decorator name"""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
        return "unknown"

    def _check_usage(self, node: ast.AST, modules: Set[str]) -> bool:
        """Check if function uses any of the specified modules"""
        # Check if we're looking for filesystem modules
        is_filesystem_check = bool(modules & self.FILESYSTEM_MODULES)

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    # Check for module.function() calls
                    if isinstance(child.func.value, ast.Name):
                        if child.func.value.id in modules:
                            return True
                elif isinstance(child.func, ast.Name):
                    # Check for direct function calls
                    if child.func.id in modules:
                        return True
                    # Check for built-in functions that indicate usage
                    if is_filesystem_check and child.func.id == 'open':
                        # open() indicates filesystem usage
                        return True
        return False

    def get_public_functions(self, structure: CodeStructure) -> List[FunctionInfo]:
        """Get all public functions (not starting with _)"""
        return [f for f in structure.functions if not f.name.startswith('_')]

    def get_public_methods(self, structure: CodeStructure) -> List[FunctionInfo]:
        """Get all public methods from all classes"""
        public_methods = []
        for cls in structure.classes:
            for method in cls.methods:
                if not method.name.startswith('_'):
                    public_methods.append(method)
        return public_methods

    def get_entry_points(self, structure: CodeStructure) -> List[str]:
        """Get potential entry points"""
        entry_points = structure.entry_points.copy()

        # Add __main__ check
        for func in structure.functions:
            if func.name == 'main':
                entry_points.append('main')

        return list(set(entry_points))
