"""Re-export ConfidenceEngine from mfgc_core for backward compatibility."""

try:
    from ..mfgc_core import ConfidenceEngine
except ImportError:
    from mfgc_core import ConfidenceEngine

__all__ = ['ConfidenceEngine']
