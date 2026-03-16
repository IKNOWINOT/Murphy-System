"""
Module Generator - Generate Murphy modules from SwissKiss analysis

This module creates Murphy-compatible modules from analyzed repositories:
- Generates wrapper code
- Creates module structure
- Registers with Module Manager
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional


class ModuleGenerator:
    """
    Generate Murphy modules from SwissKiss analysis.

    Takes SwissKiss output and creates:
    - Module wrapper code
    - Module metadata
    - Registration information
    """

    def __init__(self):
        self.modules_dir = Path("./modules")
        self.modules_dir.mkdir(parents=True, exist_ok=True)

    def generate_from_swisskiss(
        self,
        module_yaml: Dict,
        audit: Dict,
        capabilities: List[str]
    ) -> Dict:
        """
        Generate Murphy module from SwissKiss analysis.

        Args:
            module_yaml: The module.yaml from SwissKiss
            audit: The audit.json from SwissKiss
            capabilities: Extracted capabilities

        Returns:
            Module dictionary with all metadata
        """

        module_name = module_yaml['module_name']
        category = module_yaml['category']
        description = module_yaml['description']
        entry_script = module_yaml.get('entry_script', '<define-entry-script>')

        # Determine module path
        module_path = f"modules.{module_name}"

        # Extract commands (functions) from the module
        # For now, we'll create placeholder commands
        commands = self._extract_commands(module_yaml, audit)

        # Create module structure
        module = {
            'name': module_name,
            'category': category,
            'description': description,
            'module_path': module_path,
            'entry_point': entry_script,
            'capabilities': capabilities,
            'commands': commands,
            'metadata': {
                'license': audit.get('license', 'UNKNOWN'),
                'license_ok': audit.get('license_ok', False),
                'languages': audit.get('languages', {}),
                'requirements': audit.get('requirements', []),
                'risk_issues': len(audit.get('risk_scan', {}).get('issues', [])),
                'source': 'swisskiss_loader',
                'version': '1.0.0'
            }
        }

        return module

    def _extract_commands(self, module_yaml: Dict, audit: Dict) -> List[Dict]:
        """
        Extract commands from module.

        For now, creates placeholder commands based on capabilities.
        In future, could parse actual Python code to extract functions.

        Args:
            module_yaml: Module YAML
            audit: Audit data

        Returns:
            List of command dictionaries
        """

        # Default command templates
        commands = [
            {
                'name': 'execute',
                'description': 'Execute the main functionality',
                'parameters': [],
                'returns': 'Result of execution'
            },
            {
                'name': 'help',
                'description': 'Show help information',
                'parameters': [],
                'returns': 'Help text'
            }
        ]

        return commands

    def create_wrapper_code(self, module: Dict) -> str:
        """
        Create wrapper code for the module.

        This generates Python code that wraps the original module
        and makes it compatible with Murphy's module system.

        Args:
            module: Module dictionary

        Returns:
            Python code as string
        """

        code_lines = [
            '"""',
            f"Murphy Module Wrapper: {module['name']}",
            '',
            f"Description: {module['description']}",
            f"Category: {module['category']}",
            f"Capabilities: {', '.join(module['capabilities'])}",
            '"""',
            '',
            'from typing import Dict, List, Optional, Any',
            '',
            '',
            f"class {module['name'].replace('-', '_').title()}Module:",
            f'    """Murphy module for {module["name"]}"""',
            '',
            '    def __init__(self):',
            f'        self.name = "{module["name"]}"',
            f'        self.description = "{module["description"]}"',
            f'        self.capabilities = {module["capabilities"]}',
            '',
        ]

        # Add command methods
        for command in module['commands']:
            params_str = ", ".join(
                f'{p["name"]}: {p.get("type", "Any")} = {repr(p.get("default"))}'
                if "default" in p else f'{p["name"]}: {p.get("type", "Any")}'
                for p in command.get("parameters", [])
            )
            if params_str:
                params_str = ", " + params_str
            code_lines.extend([
                f'    def {command["name"]}(self{params_str}, **kwargs) -> Any:',
                '        """',
                f'        {command["description"]}',
                '        ',
                '        Returns:',
                f'            {command["returns"]}',
                '        """',
                '        import subprocess, json, logging',
                '        logger = logging.getLogger(__name__)',
                f'        payload = {{"command": "{command["name"]}", "args": kwargs}}',
                f'        logger.info("Executing %s with %s", "{command["name"]}", payload)',
                '        # Delegate to the module entry script when available',
                '        entry = getattr(self, "_entry_script", None)',
                '        if entry:',
                '            try:',
                '                result = subprocess.run(',
                '                    ["python", str(entry), json.dumps(payload)],',
                '                    capture_output=True, text=True, timeout=60,',
                '                )',
                '                if result.returncode == 0:',
                '                    return json.loads(result.stdout) if result.stdout.strip() else {{"status": "ok"}}',
                f'                logger.warning("{command["name"]} exited %d: %s", result.returncode, result.stderr)',
                '            except Exception as exc:',
                f'                logger.error("{command["name"]} failed: %s", exc)',
                f'        return {{"status": "not_implemented", "command": "{command["name"]}", "args": kwargs}}',
                '',
            ])

        # Add module instance
        code_lines.extend([
            '',
            '# Create module instance',
            f'module = {module["name"].replace("-", "_").title()}Module()',
        ])

        return '\n'.join(code_lines)

    def save_module(self, module: Dict) -> Path:
        """
        Save module to disk.

        Args:
            module: Module dictionary

        Returns:
            Path to saved module
        """

        module_dir = self.modules_dir / module['name']
        module_dir.mkdir(parents=True, exist_ok=True)

        # Save module metadata
        metadata_path = module_dir / 'module_metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(module, f, indent=2)

        # Save wrapper code
        wrapper_path = module_dir / '__init__.py'
        wrapper_code = self.create_wrapper_code(module)
        with open(wrapper_path, 'w', encoding='utf-8') as f:
            f.write(wrapper_code)

        return module_dir
