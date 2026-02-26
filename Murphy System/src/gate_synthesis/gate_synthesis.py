"""Bridge module for tests that import from src.gate_synthesis.gate_synthesis"""
from .gate_generator import GateGenerator as GateSynthesisEngine

__all__ = ['GateSynthesisEngine']
