"""
Board System – Column Types
=============================

Validation and default-value logic for each supported column type.
Each validator receives a raw value and returns a normalised
``(value, display_value)`` tuple or raises ``ValueError``.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import ColumnType

# ---------------------------------------------------------------------------
# Type-specific validators
# ---------------------------------------------------------------------------

def _validate_text(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    s = str(value) if value is not None else ""
    max_len = settings.get("max_length", 10000)
    if len(s) > max_len:
        raise ValueError(f"Text exceeds max length of {max_len}")
    return s, s


def _validate_number(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid number: {value!r}")
    unit = settings.get("unit", "")
    decimals = settings.get("decimals", 2)
    display = f"{n:.{decimals}f}"
    if unit:
        display = f"{display} {unit}"
    return n, display


def _validate_status(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    labels: Dict[str, str] = settings.get("labels", {})
    if labels and str(value) not in labels and value not in labels.values():
        allowed = list(labels.values()) or list(labels.keys())
        raise ValueError(f"Invalid status {value!r}. Allowed: {allowed}")
    return str(value), str(value)


def _validate_date(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    if isinstance(value, (date, datetime)):
        iso = value.isoformat()
        return iso, iso
    if isinstance(value, str):
        # Accept ISO-8601 date strings
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(value, fmt)
                iso = dt.date().isoformat()
                return iso, iso
            except ValueError:
                continue
        raise ValueError(f"Invalid date format: {value!r}")
    raise ValueError(f"Expected date string or object, got {type(value).__name__}")


def _validate_person(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    if isinstance(value, str):
        return value, value
    if isinstance(value, dict):
        uid = value.get("id", "")
        name = value.get("name", uid)
        return value, name
    if isinstance(value, list):
        ids = [str(v) for v in value]
        return ids, ", ".join(ids)
    raise ValueError(f"Invalid person value: {value!r}")


def _validate_dropdown(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    options: List[str] = settings.get("options", [])
    if options and str(value) not in options:
        raise ValueError(f"Invalid option {value!r}. Allowed: {options}")
    return str(value), str(value)


def _validate_checkbox(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    b = bool(value)
    return b, "✓" if b else ""


def _validate_link(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    if isinstance(value, dict):
        url = value.get("url", "")
        text = value.get("text", url)
        return value, text
    url = str(value)
    return {"url": url, "text": url}, url


def _validate_email(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    s = str(value)
    if s and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s):
        raise ValueError(f"Invalid email: {s!r}")
    return s, s


def _validate_phone(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    s = str(value).strip()
    return s, s


def _validate_rating(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    try:
        r = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid rating: {value!r}")
    max_val = settings.get("max", 5)
    if r < 0 or r > max_val:
        raise ValueError(f"Rating must be between 0 and {max_val}")
    return r, "★" * r


def _validate_color(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    s = str(value)
    if not re.match(r"^#[0-9a-fA-F]{6}$", s):
        raise ValueError(f"Invalid hex color: {s!r}")
    return s, s


def _validate_tag(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    if isinstance(value, list):
        tags = [str(t) for t in value]
    elif isinstance(value, str):
        tags = [t.strip() for t in value.split(",") if t.strip()]
    else:
        raise ValueError(f"Invalid tag value: {value!r}")
    return tags, ", ".join(tags)


def _validate_timeline(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    if isinstance(value, dict):
        start = value.get("start", "")
        end = value.get("end", "")
        return value, f"{start} → {end}"
    raise ValueError("Timeline requires a dict with 'start' and 'end' keys")


def _validate_long_text(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    s = str(value) if value is not None else ""
    preview_len = settings.get("preview_length", 100)
    display = s[:preview_len] + ("…" if len(s) > preview_len else "")
    return s, display


def _validate_dependency(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    if isinstance(value, list):
        ids = [str(v) for v in value]
        return ids, ", ".join(ids)
    if isinstance(value, str):
        ids = [v.strip() for v in value.split(",") if v.strip()]
        return ids, ", ".join(ids)
    raise ValueError(f"Invalid dependency value: {value!r}")


def _validate_file(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    if isinstance(value, dict):
        name = value.get("name", "file")
        return value, name
    if isinstance(value, list):
        names = [v.get("name", "file") if isinstance(v, dict) else str(v) for v in value]
        return value, ", ".join(names)
    return str(value), str(value)


def _validate_auto_number(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid auto_number: {value!r}")
    prefix = settings.get("prefix", "")
    return n, f"{prefix}{n}"


def _validate_formula(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    # Formula values are computed, not user-supplied.
    return value, str(value) if value is not None else ""


def _validate_mirror(value: Any, settings: Dict[str, Any]) -> Tuple[Any, str]:
    # Mirror values are derived from linked boards.
    return value, str(value) if value is not None else ""


# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

COLUMN_VALIDATORS: Dict[ColumnType, Callable[..., Tuple[Any, str]]] = {
    ColumnType.TEXT: _validate_text,
    ColumnType.NUMBER: _validate_number,
    ColumnType.STATUS: _validate_status,
    ColumnType.DATE: _validate_date,
    ColumnType.PERSON: _validate_person,
    ColumnType.DROPDOWN: _validate_dropdown,
    ColumnType.CHECKBOX: _validate_checkbox,
    ColumnType.LINK: _validate_link,
    ColumnType.EMAIL: _validate_email,
    ColumnType.PHONE: _validate_phone,
    ColumnType.RATING: _validate_rating,
    ColumnType.COLOR: _validate_color,
    ColumnType.TAG: _validate_tag,
    ColumnType.TIMELINE: _validate_timeline,
    ColumnType.LONG_TEXT: _validate_long_text,
    ColumnType.DEPENDENCY: _validate_dependency,
    ColumnType.FILE: _validate_file,
    ColumnType.AUTO_NUMBER: _validate_auto_number,
    ColumnType.FORMULA: _validate_formula,
    ColumnType.MIRROR: _validate_mirror,
}


def validate_cell_value(
    column_type: ColumnType,
    value: Any,
    settings: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, str]:
    """Validate and normalise a cell value for the given column type.

    Returns ``(normalised_value, display_value)`` or raises ``ValueError``.
    """
    validator = COLUMN_VALIDATORS.get(column_type)
    if validator is None:
        return value, str(value)
    return validator(value, settings or {})


def default_value(column_type: ColumnType, settings: Optional[Dict[str, Any]] = None) -> Any:
    """Return the sensible default value for a column type."""
    _defaults: Dict[ColumnType, Any] = {
        ColumnType.TEXT: "",
        ColumnType.LONG_TEXT: "",
        ColumnType.NUMBER: 0,
        ColumnType.STATUS: (settings or {}).get("default", ""),
        ColumnType.DATE: None,
        ColumnType.PERSON: None,
        ColumnType.DROPDOWN: "",
        ColumnType.CHECKBOX: False,
        ColumnType.LINK: None,
        ColumnType.EMAIL: "",
        ColumnType.PHONE: "",
        ColumnType.RATING: 0,
        ColumnType.COLOR: "#000000",
        ColumnType.TAG: [],
        ColumnType.TIMELINE: None,
        ColumnType.DEPENDENCY: [],
        ColumnType.FILE: None,
        ColumnType.AUTO_NUMBER: 0,
        ColumnType.FORMULA: None,
        ColumnType.MIRROR: None,
    }
    return _defaults.get(column_type)
