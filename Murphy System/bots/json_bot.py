"""JSONBot with detailed error messages and strict mode."""
from __future__ import annotations

import ast
import json
import logging
from typing import Any


from typing import Type
from pydantic import BaseModel, ValidationError


class JSONBot:
    def __init__(self, strict: bool = False) -> None:
        self.strict = strict

    def parse(self, text: str) -> Any:
        try:
            return json.loads(text)
        except Exception as exc:  # catch broad to record any parse failure
            msg = f"JSON parse error at position {getattr(exc, 'pos', '?')}: {exc}"
            if self.strict:
                raise ValueError(msg) from exc
            return {"error": msg}

    def validate(self, data: dict, model: Type[BaseModel]):
        """Validate ``data`` against a Pydantic ``model``.

        If ``strict`` is enabled, any validation errors raise ``RuntimeError``;
        otherwise a dictionary describing issues is returned.
        """
        try:
            return model(**data)
        except ValidationError as exc:  # pragma: no cover - simple passthrough
            if self.strict:
                raise RuntimeError(f"Strict Mode Rejection: {exc}") from exc
            return {"valid": False, "issues": exc.errors()}

    def stream_objects(self, file_obj, buffer_size: int = 4096):
        """Yield JSON objects from a file-like object incrementally.

        The file may contain a list (e.g. ``[{}, {}, ...]``) or newline-delimited
        JSON objects. This allows large datasets to be processed without loading
        them entirely into memory.
        """
        decoder = json.JSONDecoder()
        buffer = ""
        in_array = False
        while True:
            chunk = file_obj.read(buffer_size)
            if not chunk:
                break
            buffer += chunk
            while True:
                buffer = buffer.lstrip()
                if not buffer:
                    break
                if not in_array and buffer[0] == '[':
                    in_array = True
                    buffer = buffer[1:]
                    continue
                try:
                    obj, idx = decoder.raw_decode(buffer)
                    yield obj
                    buffer = buffer[idx:]
                    if in_array:
                        buffer = buffer.lstrip()
                        if buffer.startswith(','):
                            buffer = buffer[1:]
                        elif buffer.startswith(']'):
                            buffer = buffer[1:]
                            in_array = False
                except ValueError:
                    # Need more data
                    break
        # drain
        buffer = buffer.strip()
        if buffer in (']', ''):
            return
        if buffer:
            try:
                obj, _ = decoder.raw_decode(buffer)
                yield obj
            except ValueError:
                if self.strict:
                    raise

    # --- Absorption & Reversion Module v3 additions ---
    def convert_to_json(self, input_data: str, input_format: str | None = None) -> dict:
        """Convert various structured formats to JSON-compatible dict."""
        try:
            if input_format == 'json' or (not input_format and input_data.strip().startswith('{')):
                return json.loads(input_data)
            if input_format == 'yaml' or (not input_format and ':' in input_data and '-' in input_data):
                import yaml
                return yaml.safe_load(input_data)
            if input_format == 'csv' or (not input_format and ',' in input_data and '\n' in input_data):
                import csv
                from io import StringIO
                reader = csv.DictReader(StringIO(input_data))
                return {"rows": [row for row in reader]}
            if input_format == 'xml' or (not input_format and input_data.strip().startswith('<')):
                import xml.etree.ElementTree as ET
                root = ET.fromstring(input_data)

                def parse_xml(el):
                    return {
                        el.tag: {**el.attrib, **{c.tag: parse_xml(c) for c in el}}
                        if list(el)
                        else el.text
                    }

                return parse_xml(root)
            if input_format == 'ini' or (not input_format and '[DEFAULT]' in input_data or '=' in input_data):
                import configparser
                config = configparser.ConfigParser()
                config.read_string(input_data)
                return {section: dict(config.items(section)) for section in config.sections()}
            if input_format == 'python' or (not input_format and 'dict' in input_data or ':' in input_data):
                return ast.literal_eval(input_data)
            if input_format == 'text' or not input_format:
                return self._parse_text_blob(input_data)
            raise ValueError('Unknown format')
        except Exception as exc:  # pragma: no cover - best effort parse
            return {"error": f"Could not parse input. Reason: {exc}"}

    def _parse_text_blob(self, text: str) -> dict:
        result: dict[str, str] = {}
        for i, line in enumerate(text.strip().splitlines()):
            if ':' in line:
                key, val = line.split(':', 1)
                result[key.strip()] = val.strip()
            else:
                result[f"line_{i}"] = line.strip()
        return result

    @staticmethod
    def to_json_string(data: dict, indent: int = 2) -> str:
        return json.dumps(data, indent=indent)

    def json_to_format(self, data: dict, output_format: str) -> str:
        if output_format == 'json':
            return json.dumps(data, indent=2)
        if output_format == 'yaml':
            import yaml
            return yaml.dump(data, sort_keys=False)
        if output_format == 'csv':
            import csv
            from io import StringIO
            if 'rows' not in data:
                raise ValueError("Data must contain 'rows' key with list of dicts to export CSV.")
            output = StringIO()
            fieldnames = data['rows'][0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in data['rows']:
                writer.writerow(row)
            return output.getvalue()
        if output_format == 'ini':
            import configparser
            config = configparser.ConfigParser()
            for section, values in data.items():
                config[section] = values
            output = StringIO()
            config.write(output)
            return output.getvalue()
        if output_format == 'xml':
            import xml.etree.ElementTree as ET

            def build_xml(parent, dict_data):
                for tag, val in dict_data.items():
                    if isinstance(val, dict):
                        elem = ET.SubElement(parent, tag)
                        build_xml(elem, val)
                    else:
                        elem = ET.SubElement(parent, tag)
                        elem.text = str(val)

            root_tag = next(iter(data))
            root = ET.Element(root_tag)
            build_xml(root, data[root_tag])
            return ET.tostring(root, encoding='unicode')
        raise ValueError(f"Unsupported output format: {output_format}")

    # --- hive_mind_math_patch_v2.0 addition ---
    def validate_dependencies(self, matrix: list[list[int]]) -> bool:
        """Check if dependency matrix has potential cascading failures."""
        size = len(matrix)
        for i in range(size):
            for j in range(size):
                if matrix[i][j] and matrix[j][i]:
                    if self.strict:
                        raise RuntimeError("Circular dependency detected")
                    return False
        return True


from .tool_dispatcher import dispatch
from .feedback_bot import FeedbackBot

_logger = logging.getLogger(__name__)

def handle_validated_task(task_json: dict) -> dict:
    """Route validated task to dispatcher and log outcome."""
    result = dispatch(task_json)
    if FeedbackBot:
        try:
            FeedbackBot.log_task_outcome(task_json.get("task_id", "?"), result)
        except Exception as exc:
            _logger.debug("Suppressed exception: %s", exc)
    return result
