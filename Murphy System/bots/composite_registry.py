import json
import importlib
from pathlib import Path
from typing import Dict, Type, Any

_REGISTRY_PATH = Path(__file__).with_name('composite_registry.json')


def load_registry() -> Dict[str, Any]:
    """Load the composite bot registry JSON."""
    with _REGISTRY_PATH.open() as f:
        return json.load(f)


def load_composite_bots() -> Dict[str, Type[Any]]:
    """Dynamically import composite bot classes from the registry."""
    registry = load_registry()
    bots = {}
    for bot in registry.get('composite_bots', []):
        module = importlib.import_module(f"modern_arcana.{bot['module']}")
        cls = getattr(module, bot['class'])
        bots[bot['name']] = cls
    return bots
