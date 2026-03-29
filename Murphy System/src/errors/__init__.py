# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Module: errors/__init__.py
Subsystem: Error Handling
Purpose: Canonical error handling package for Murphy System.
Status: Production

Provides structured error codes (MURPHY-Exxx), a registry mapping
existing exception classes to codes, and FastAPI exception handlers
that return the standard error envelope.
"""
from __future__ import annotations

from .codes import ErrorCode, SUBSYSTEM_RANGES
from .registry import ErrorRegistry, ErrorEntry
from .handlers import register_error_handlers

__all__ = [
    "ErrorCode",
    "ErrorEntry",
    "ErrorRegistry",
    "SUBSYSTEM_RANGES",
    "register_error_handlers",
]
