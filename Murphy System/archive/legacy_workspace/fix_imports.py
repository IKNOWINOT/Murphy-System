#!/usr/bin/env python3
"""
Fix imports in integrated files to use murphy_integrated paths instead of murphy_implementation
"""

import os
import re
from pathlib import Path

# Define import mappings
IMPORT_MAPPINGS = {
    # murphy_implementation.forms -> src.form_intake
    r'from murphy_implementation\.forms': 'from src.form_intake',
    r'import murphy_implementation\.forms': 'import src.form_intake',
    
    # murphy_implementation.plan_decomposition -> src.form_intake
    r'from murphy_implementation\.plan_decomposition': 'from src.form_intake',
    r'import murphy_implementation\.plan_decomposition': 'import src.form_intake',
    
    # murphy_implementation.validation -> src.confidence_engine
    r'from murphy_implementation\.validation': 'from src.confidence_engine',
    r'import murphy_implementation\.validation': 'import src.confidence_engine',
    
    # murphy_implementation.risk -> src.confidence_engine.risk
    r'from murphy_implementation\.risk': 'from src.confidence_engine.risk',
    r'import murphy_implementation\.risk': 'import src.confidence_engine.risk',
    
    # murphy_implementation.performance -> src.confidence_engine
    r'from murphy_implementation\.performance': 'from src.confidence_engine',
    r'import murphy_implementation\.performance': 'import src.confidence_engine',
    
    # murphy_implementation.execution -> src.execution_engine
    r'from murphy_implementation\.execution': 'from src.execution_engine',
    r'import murphy_implementation\.execution': 'import src.execution_engine',
    
    # murphy_implementation.hitl -> src.supervisor_system
    r'from murphy_implementation\.hitl': 'from src.supervisor_system',
    r'import murphy_implementation\.hitl': 'import src.supervisor_system',
    
    # murphy_implementation.correction -> src.learning_engine
    r'from murphy_implementation\.correction': 'from src.learning_engine',
    r'import murphy_implementation\.correction': 'import src.learning_engine',
    
    # murphy_implementation.shadow_agent -> src.learning_engine
    r'from murphy_implementation\.shadow_agent': 'from src.learning_engine',
    r'import murphy_implementation\.shadow_agent': 'import src.learning_engine',
}

# File name mappings (for when files were renamed)
FILE_NAME_MAPPINGS = {
    'models.py': {
        'validation': 'murphy_models',
        'execution': 'form_execution_models',
        'hitl': 'hitl_models',
        'correction': 'correction_models',
        'shadow_agent': 'shadow_models',
    },
    'decomposer.py': 'plan_decomposer',
    'executor.py': 'form_executor',
    'monitor.py': 'hitl_monitor',
    'correction_model.py': 'correction_models',
    'validation_and_patterns.py': 'pattern_extraction',
    'data_transformer.py': 'training_data_transformer',
    'data_validator.py': 'training_data_validator',
    'evaluation.py': 'shadow_evaluation',
    'monitoring.py': 'shadow_monitoring',
    'integration.py': 'shadow_integration',
}

def fix_file_imports(file_path):
    """Fix imports in a single file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Apply import mappings
    for old_pattern, new_pattern in IMPORT_MAPPINGS.items():
        content = re.sub(old_pattern, new_pattern, content)
    
    # Fix specific file name references
    # e.g., from src.confidence_engine.models -> from src.confidence_engine.murphy_models
    for old_name, mapping in FILE_NAME_MAPPINGS.items():
        if isinstance(mapping, dict):
            for module, new_name in mapping.items():
                pattern = rf'from src\.{module}\.{old_name.replace(".py", "")}'
                replacement = f'from src.{module}.{new_name}'
                content = re.sub(pattern, replacement, content)
        else:
            # Simple string mapping
            old_module = old_name.replace('.py', '')
            content = re.sub(rf'\.{old_module}\b', f'.{mapping}', content)
    
    # Remove sys.path.insert hacks
    content = re.sub(
        r"sys\.path\.insert\(0, os\.path\.join\(os\.path\.dirname\(__file__\), ['&quot;]\.\.\/\.\.\/murphy_runtime_analysis['&quot;]\)\)\n?",
        "",
        content
    )
    
    # Write back if changed
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix imports in all integrated files"""
    base_path = Path('murphy_integrated/src')
    
    # Directories to process
    directories = [
        'form_intake',
        'confidence_engine',
        'execution_engine',
        'supervisor_system',
        'learning_engine',
    ]
    
    files_fixed = 0
    files_processed = 0
    
    for directory in directories:
        dir_path = base_path / directory
        if not dir_path.exists():
            continue
        
        # Process all Python files recursively
        for py_file in dir_path.rglob('*.py'):
            files_processed += 1
            if fix_file_imports(py_file):
                files_fixed += 1
                print(f"Fixed: {py_file}")
    
    print(f"\n=== Summary ===")
    print(f"Files processed: {files_processed}")
    print(f"Files fixed: {files_fixed}")

if __name__ == '__main__':
    main()