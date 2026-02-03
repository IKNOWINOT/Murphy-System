#!/usr/bin/env python3
"""
Fix imports to use murphy_models instead of models for Murphy-specific classes
"""

import os
import re
from pathlib import Path

# Files that need Murphy models
MURPHY_FILES = [
    'murphy_integrated/src/confidence_engine/uncertainty_calculator.py',
    'murphy_integrated/src/confidence_engine/murphy_gate.py',
    'murphy_integrated/src/confidence_engine/murphy_validator.py',
]

# Murphy-specific model classes
MURPHY_MODELS = [
    'UncertaintyScores',
    'GateResult',
    'ConfidenceReport',
    'Phase',
    'MurphyValidationResult',
]

def fix_file(file_path):
    """Fix imports in a single file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Check if file imports any Murphy models
    needs_murphy_models = any(model in content for model in MURPHY_MODELS)
    
    if needs_murphy_models:
        # Replace imports of Murphy models from .models to .murphy_models
        for model in MURPHY_MODELS:
            # Pattern: from .models import UncertaintyScores
            pattern = rf'from \.models import ([^;\n]*\b{model}\b[^;\n]*)'
            if re.search(pattern, content):
                # Extract the full import list
                match = re.search(pattern, content)
                if match:
                    import_list = match.group(1)
                    # Split by comma and check which are Murphy models
                    imports = [i.strip() for i in import_list.split(',')]
                    murphy_imports = [i for i in imports if any(m in i for m in MURPHY_MODELS)]
                    other_imports = [i for i in imports if not any(m in i for m in MURPHY_MODELS)]
                    
                    # Replace the line
                    old_line = f'from .models import {import_list}'
                    new_lines = []
                    
                    if murphy_imports:
                        new_lines.append(f'from .murphy_models import {", ".join(murphy_imports)}')
                    if other_imports:
                        new_lines.append(f'from .models import {", ".join(other_imports)}')
                    
                    content = content.replace(old_line, '\n'.join(new_lines))
    
    # Write back if changed
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix imports in Murphy files"""
    files_fixed = 0
    
    for file_path in MURPHY_FILES:
        if os.path.exists(file_path):
            if fix_file(file_path):
                files_fixed += 1
                print(f"Fixed: {file_path}")
        else:
            print(f"Not found: {file_path}")
    
    print(f"\nFiles fixed: {files_fixed}")

if __name__ == '__main__':
    main()