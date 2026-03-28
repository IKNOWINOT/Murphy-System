# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
Created by: Corey Post

---

# Murphy System — Plugin SDK Guide

This guide covers everything you need to build, test, and publish a plugin for the Murphy System marketplace.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Quick Start (5-Minute Guide)](#2-quick-start-5-minute-guide)
3. [Full SDK API Reference](#3-full-sdk-api-reference)
   - [ConnectorPlugin (Abstract Base Class)](#connectorplugin-abstract-base-class)
   - [ConnectorCategory Enum](#connectorcategory-enum)
   - [AuthType Enum](#authtype-enum)
   - [PluginLoader](#pluginloader)
   - [PluginValidator & ValidationResult](#pluginvalidator--validationresult)
4. [Plugin Examples](#4-plugin-examples)
   - [Example 1: Slack Notification Plugin](#example-1-slack-notification-plugin)
   - [Example 2: PostgreSQL Database Connector Plugin](#example-2-postgresql-database-connector-plugin)
   - [Example 3: Custom ML Scorer Plugin](#example-3-custom-ml-scorer-plugin)
5. [Testing Your Plugin](#5-testing-your-plugin)
6. [Submission Process](#6-submission-process)
7. [Marketplace Listing Instructions](#7-marketplace-listing-instructions)

---

## 1. Installation

### Install via pip

```bash
pip install murphy-system
```

This installs the core Murphy System runtime along with the Plugin SDK utilities needed to author, validate, and load plugins.

### Install from source (recommended for contributors)

```bash
git clone https://github.com/inoni/Murphy-System.git
cd Murphy-System
pip install -e ".[dev]"
```

The `-e` flag installs in editable mode so local changes to the SDK are immediately reflected.

### Requirements

- Python 3.10 or higher
- pip 22+
- (Optional) Docker — required for integration tests against live services

---

## 2. Quick Start (5-Minute Guide)

The following example creates a minimal "Hello World" plugin that can be loaded and executed by the Murphy System runtime.

```python
# hello_world_plugin.py

from murphy_system.sdk import ConnectorPlugin, ConnectorCategory, AuthType

class HelloWorldPlugin(ConnectorPlugin):
    """A minimal example plugin that returns a greeting."""

    NAME = "hello_world"
    VERSION = "1.0.0"
    CATEGORY = ConnectorCategory.UTILITY
    AUTH_TYPE = AuthType.NONE

    def authenticate(self, credentials: dict) -> bool:
        # No authentication required for this plugin
        return True

    def execute(self, action: str, payload: dict) -> dict:
        name = payload.get("name", "World")
        return {"message": f"Hello, {name}! Murphy System is running."}

    def health_check(self) -> dict:
        return {"status": "ok", "plugin": self.NAME}

    def schema(self) -> dict:
        return {
            "actions": ["greet"],
            "input": {
                "name": {"type": "string", "required": False, "default": "World"}
            },
            "output": {
                "message": {"type": "string"}
            }
        }
```

**Load and run it:**

```python
from murphy_system.sdk import PluginLoader

loader = PluginLoader()
plugin = loader.load("hello_world_plugin.HelloWorldPlugin")

plugin.authenticate({})
result = plugin.execute("greet", {"name": "Murphy"})
print(result)
# → {"message": "Hello, Murphy! Murphy System is running."}
```

---

## 3. Full SDK API Reference

### `ConnectorPlugin` (Abstract Base Class)

**Module:** `murphy_system.sdk.base`

`ConnectorPlugin` is the abstract base class that every Murphy System plugin must inherit from. It enforces a consistent interface for authentication, execution, health checks, and schema declaration.

```python
from abc import ABC, abstractmethod

class ConnectorPlugin(ABC):
    NAME: str       # Unique snake_case plugin identifier
    VERSION: str    # Semantic version string, e.g. "1.2.0"
    CATEGORY: ConnectorCategory
    AUTH_TYPE: AuthType

    @abstractmethod
    def authenticate(self, credentials: dict) -> bool:
        ...

    @abstractmethod
    def execute(self, action: str, payload: dict) -> dict:
        ...

    @abstractmethod
    def health_check(self) -> dict:
        ...

    @abstractmethod
    def schema(self) -> dict:
        ...
```

#### Method: `authenticate(credentials: dict) -> bool`

Called once before any `execute()` call. Receives a dictionary of credentials whose keys are defined by the plugin's `schema()`. Must return `True` if authentication succeeds, or raise `AuthenticationError` on failure.

| Parameter     | Type   | Description                              |
|---------------|--------|------------------------------------------|
| `credentials` | `dict` | Key-value credential pairs (e.g. tokens) |

**Returns:** `bool` — `True` on success.

**Raises:** `murphy_system.sdk.exceptions.AuthenticationError`

---

#### Method: `execute(action: str, payload: dict) -> dict`

Main execution entry point. The `action` string identifies which operation to perform (must be one of the actions declared in `schema()`). The `payload` dict carries input data.

| Parameter | Type   | Description                         |
|-----------|--------|-------------------------------------|
| `action`  | `str`  | The action identifier to execute    |
| `payload` | `dict` | Input data for the action           |

**Returns:** `dict` — Structured result conforming to the action's output schema.

**Raises:** `murphy_system.sdk.exceptions.ExecutionError`, `murphy_system.sdk.exceptions.UnsupportedActionError`

---

#### Method: `health_check() -> dict`

Returns the current operational status of the plugin and any underlying service it connects to. Called periodically by the Murphy System runtime.

**Returns:** `dict` with at minimum:
```python
{
    "status": "ok" | "degraded" | "error",
    "plugin": "<NAME>",
    "details": {}   # optional additional metadata
}
```

---

#### Method: `schema() -> dict`

Declares the plugin's supported actions, input schemas, output schemas, and credential requirements. Used by the runtime for validation and by the marketplace for documentation generation.

**Returns:** `dict` structured as:
```python
{
    "actions": ["action_one", "action_two"],
    "credentials": {
        "api_key": {"type": "string", "secret": True, "required": True}
    },
    "input": {
        "action_one": {
            "field_name": {"type": "string", "required": True}
        }
    },
    "output": {
        "action_one": {
            "result": {"type": "string"}
        }
    }
}
```

---

### `ConnectorCategory` Enum

**Module:** `murphy_system.sdk.enums`

Use `ConnectorCategory` to classify your plugin. The marketplace uses this value to organise the plugin directory.

```python
from murphy_system.sdk.enums import ConnectorCategory
```

| Value                       | Description                                      |
|-----------------------------|--------------------------------------------------|
| `COMMUNICATION`             | Messaging, email, and notification services      |
| `DATABASE`                  | Relational and NoSQL database connectors         |
| `STORAGE`                   | Object storage, file systems, CDN                |
| `ANALYTICS`                 | BI tools, data warehouses, reporting             |
| `ML_AI`                     | Machine learning models and AI service APIs      |
| `CRM`                       | Customer relationship management platforms       |
| `ERP`                       | Enterprise resource planning systems             |
| `DEVOPS`                    | CI/CD, monitoring, and infrastructure tools      |
| `SECURITY`                  | IAM, SIEM, vulnerability scanners                |
| `PAYMENTS`                  | Payment gateways and financial transaction APIs  |
| `ECOMMERCE`                 | Online store and marketplace platforms           |
| `SOCIAL_MEDIA`              | Social network APIs and engagement tools         |
| `IOT`                       | IoT device management and sensor data            |
| `HEALTHCARE`                | Clinical data, EHR/EMR, and FHIR connectors      |
| `LEGAL`                     | Contract management and compliance tools         |
| `LOGISTICS`                 | Shipping, supply chain, and fleet management     |
| `MARKETING`                 | Email marketing, ad platforms, SEO tools         |
| `PRODUCTIVITY`              | Calendars, task managers, office suites          |
| `DATA_PIPELINE`             | ETL/ELT orchestration and data flow tools        |
| `UTILITY`                   | General-purpose and miscellaneous plugins        |

---

### `AuthType` Enum

**Module:** `murphy_system.sdk.enums`

Declares the authentication mechanism the plugin uses. This drives the credential input form shown in the Murphy System UI.

```python
from murphy_system.sdk.enums import AuthType
```

| Value            | Description                                               |
|------------------|-----------------------------------------------------------|
| `NONE`           | No authentication required                               |
| `API_KEY`        | Single static API key passed in headers or query params  |
| `BASIC`          | HTTP Basic Auth (username + password)                    |
| `OAUTH2`         | OAuth 2.0 authorization code or client credentials flow  |
| `JWT`            | JSON Web Token-based authentication                      |
| `CERTIFICATE`    | Mutual TLS / client certificate authentication           |
| `CUSTOM`         | Plugin-defined credential fields declared in `schema()`  |

---

### `PluginLoader`

**Module:** `murphy_system.sdk.loader`

`PluginLoader` discovers, imports, and instantiates plugin classes from Python module paths or local directories.

```python
from murphy_system.sdk import PluginLoader

loader = PluginLoader(plugin_dir="./plugins")
```

#### Constructor

```python
PluginLoader(plugin_dir: str | None = None)
```

| Parameter    | Type            | Description                                              |
|--------------|-----------------|----------------------------------------------------------|
| `plugin_dir` | `str` or `None` | Optional path to scan for plugin modules automatically   |

#### Methods

| Method                                                  | Returns                 | Description                                       |
|---------------------------------------------------------|-------------------------|---------------------------------------------------|
| `load(module_path: str) -> ConnectorPlugin`             | `ConnectorPlugin`       | Load plugin by `"module.ClassName"` dotted path   |
| `load_all() -> list[ConnectorPlugin]`                   | `list[ConnectorPlugin]` | Load all plugins discovered in `plugin_dir`       |
| `get(name: str) -> ConnectorPlugin \| None`             | `ConnectorPlugin`       | Retrieve a loaded plugin instance by `NAME`       |
| `list_loaded() -> list[str]`                            | `list[str]`             | Return `NAME` values of all currently loaded plugins |

---

### `PluginValidator` & `ValidationResult`

**Module:** `murphy_system.sdk.validator`

`PluginValidator` performs static and runtime validation of a plugin before submission or deployment.

```python
from murphy_system.sdk import PluginValidator

validator = PluginValidator()
result = validator.validate(MyPlugin)
if result.is_valid:
    print("Plugin is ready for submission.")
else:
    for error in result.errors:
        print(f"[ERROR] {error}")
```

#### `PluginValidator` Methods

| Method                                                     | Returns            | Description                                       |
|------------------------------------------------------------|--------------------|---------------------------------------------------|
| `validate(plugin_class: type) -> ValidationResult`        | `ValidationResult` | Full static + runtime validation of a plugin class |
| `validate_schema(schema: dict) -> ValidationResult`       | `ValidationResult` | Validate only the schema dict structure           |
| `validate_credentials(plugin, creds: dict) -> bool`       | `bool`             | Test credential structure against declared schema  |

#### `ValidationResult`

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    plugin_name: str
    plugin_version: str
```

| Field            | Type        | Description                                      |
|------------------|-------------|--------------------------------------------------|
| `is_valid`       | `bool`      | `True` if no errors were found                   |
| `errors`         | `list[str]` | Blocking issues that must be resolved            |
| `warnings`       | `list[str]` | Non-blocking suggestions for improvement         |
| `plugin_name`    | `str`       | Value of `NAME` from the validated class         |
| `plugin_version` | `str`       | Value of `VERSION` from the validated class      |

---

## 4. Plugin Examples

### Example 1: Slack Notification Plugin

Sends messages to a Slack channel via the Slack Web API.

```python
# slack_notification_plugin.py

import json
import urllib.request
import urllib.error
from murphy_system.sdk import ConnectorPlugin, ConnectorCategory, AuthType
from murphy_system.sdk.exceptions import AuthenticationError, ExecutionError

class SlackNotificationPlugin(ConnectorPlugin):
    """Send notifications to Slack channels using the Slack Web API."""

    NAME = "slack_notification"
    VERSION = "1.0.0"
    CATEGORY = ConnectorCategory.COMMUNICATION
    AUTH_TYPE = AuthType.API_KEY

    def __init__(self):
        self._token: str | None = None
        self._base_url = "https://slack.com/api"

    def authenticate(self, credentials: dict) -> bool:
        token = credentials.get("bot_token")
        if not token or not token.startswith("xoxb-"):
            raise AuthenticationError("Invalid Slack bot token. Token must start with 'xoxb-'.")
        # Verify the token against Slack's auth.test endpoint
        response = self._api_call("auth.test", {}, token=token)
        if not response.get("ok"):
            raise AuthenticationError(f"Slack authentication failed: {response.get('error')}")
        self._token = token
        return True

    def execute(self, action: str, payload: dict) -> dict:
        if action == "send_message":
            return self._send_message(payload)
        elif action == "send_block_message":
            return self._send_block_message(payload)
        elif action == "list_channels":
            return self._list_channels(payload)
        else:
            from murphy_system.sdk.exceptions import UnsupportedActionError
            raise UnsupportedActionError(f"Action '{action}' is not supported by {self.NAME}.")

    def health_check(self) -> dict:
        if not self._token:
            return {"status": "error", "plugin": self.NAME, "details": "Not authenticated."}
        response = self._api_call("auth.test", {})
        ok = response.get("ok", False)
        return {
            "status": "ok" if ok else "error",
            "plugin": self.NAME,
            "details": {"team": response.get("team"), "bot_user": response.get("user")}
        }

    def schema(self) -> dict:
        return {
            "actions": ["send_message", "send_block_message", "list_channels"],
            "credentials": {
                "bot_token": {
                    "type": "string",
                    "secret": True,
                    "required": True,
                    "description": "Slack Bot OAuth Token (xoxb-...)"
                }
            },
            "input": {
                "send_message": {
                    "channel": {"type": "string", "required": True, "description": "Channel ID or name"},
                    "text": {"type": "string", "required": True, "description": "Message text"}
                },
                "send_block_message": {
                    "channel": {"type": "string", "required": True},
                    "blocks": {"type": "array", "required": True, "description": "Slack Block Kit blocks array"}
                },
                "list_channels": {
                    "limit": {"type": "integer", "required": False, "default": 100}
                }
            },
            "output": {
                "send_message": {
                    "ok": {"type": "boolean"},
                    "ts": {"type": "string", "description": "Message timestamp"},
                    "channel": {"type": "string"}
                },
                "list_channels": {
                    "channels": {"type": "array"}
                }
            }
        }

    # ── Private helpers ──────────────────────────────────────────────────────

    def _send_message(self, payload: dict) -> dict:
        channel = payload.get("channel")
        text = payload.get("text")
        if not channel or not text:
            raise ExecutionError("'channel' and 'text' are required for send_message.")
        return self._api_call("chat.postMessage", {"channel": channel, "text": text})

    def _send_block_message(self, payload: dict) -> dict:
        channel = payload.get("channel")
        blocks = payload.get("blocks")
        if not channel or not blocks:
            raise ExecutionError("'channel' and 'blocks' are required for send_block_message.")
        return self._api_call("chat.postMessage", {"channel": channel, "blocks": blocks})

    def _list_channels(self, payload: dict) -> dict:
        limit = payload.get("limit", 100)
        return self._api_call("conversations.list", {"limit": limit})

    def _api_call(self, method: str, data: dict, token: str | None = None) -> dict:
        token = token or self._token
        url = f"{self._base_url}/{method}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ExecutionError(f"Slack API HTTP error {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise ExecutionError(f"Slack API connection error: {exc.reason}") from exc
```

---

### Example 2: PostgreSQL Database Connector Plugin

Connects to a PostgreSQL database and supports query and insert operations.

```python
# postgresql_connector_plugin.py

from murphy_system.sdk import ConnectorPlugin, ConnectorCategory, AuthType
from murphy_system.sdk.exceptions import AuthenticationError, ExecutionError

class PostgreSQLConnectorPlugin(ConnectorPlugin):
    """Connect to PostgreSQL databases — query, insert, and manage data."""

    NAME = "postgresql_connector"
    VERSION = "1.0.0"
    CATEGORY = ConnectorCategory.DATABASE
    AUTH_TYPE = AuthType.BASIC

    def __init__(self):
        self._conn = None
        self._dsn: str | None = None

    def authenticate(self, credentials: dict) -> bool:
        try:
            import psycopg2  # type: ignore[import]
        except ImportError as exc:
            raise AuthenticationError(
                "psycopg2 is required: pip install psycopg2-binary"
            ) from exc

        host = credentials.get("host", "localhost")
        port = credentials.get("port", 5432)
        dbname = credentials.get("dbname")
        user = credentials.get("username")
        password = credentials.get("password")

        if not all([dbname, user, password]):
            raise AuthenticationError("'dbname', 'username', and 'password' are required.")

        try:
            self._conn = psycopg2.connect(
                host=host, port=port, dbname=dbname, user=user, password=password,
                connect_timeout=10
            )
            self._dsn = f"postgresql://{user}@{host}:{port}/{dbname}"
            return True
        except Exception as exc:
            raise AuthenticationError(f"PostgreSQL connection failed: {exc}") from exc

    def execute(self, action: str, payload: dict) -> dict:
        if action == "query":
            return self._query(payload)
        elif action == "insert":
            return self._insert(payload)
        elif action == "connect_info":
            return self._connect_info()
        else:
            from murphy_system.sdk.exceptions import UnsupportedActionError
            raise UnsupportedActionError(f"Action '{action}' is not supported.")

    def health_check(self) -> dict:
        if self._conn is None:
            return {"status": "error", "plugin": self.NAME, "details": "Not connected."}
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            return {"status": "ok", "plugin": self.NAME, "details": {"dsn": self._dsn}}
        except Exception as exc:
            return {"status": "error", "plugin": self.NAME, "details": str(exc)}

    def schema(self) -> dict:
        return {
            "actions": ["query", "insert", "connect_info"],
            "credentials": {
                "host":     {"type": "string",  "required": False, "default": "localhost"},
                "port":     {"type": "integer", "required": False, "default": 5432},
                "dbname":   {"type": "string",  "required": True},
                "username": {"type": "string",  "required": True},
                "password": {"type": "string",  "required": True, "secret": True}
            },
            "input": {
                "query": {
                    "sql":    {"type": "string", "required": True,  "description": "SQL SELECT statement"},
                    "params": {"type": "array",  "required": False, "description": "Parameterized query values"}
                },
                "insert": {
                    "table":  {"type": "string", "required": True},
                    "rows":   {"type": "array",  "required": True,  "description": "List of dicts to insert"}
                }
            },
            "output": {
                "query": {
                    "rows":    {"type": "array"},
                    "columns": {"type": "array"},
                    "count":   {"type": "integer"}
                },
                "insert": {
                    "inserted": {"type": "integer", "description": "Number of rows inserted"}
                }
            }
        }

    # ── Private helpers ──────────────────────────────────────────────────────

    def _query(self, payload: dict) -> dict:
        sql = payload.get("sql")
        params = payload.get("params", [])
        if not sql:
            raise ExecutionError("'sql' is required for query action.")
        if not sql.strip().upper().startswith("SELECT"):
            raise ExecutionError("Only SELECT statements are allowed in the query action.")
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            return {"rows": rows, "columns": columns, "count": len(rows)}
        except Exception as exc:
            raise ExecutionError(f"Query execution failed: {exc}") from exc

    def _insert(self, payload: dict) -> dict:
        table = payload.get("table")
        rows = payload.get("rows", [])
        if not table or not rows:
            raise ExecutionError("'table' and 'rows' are required for insert action.")
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ExecutionError("'rows' must be a list of dicts.")
        try:
            columns = list(rows[0].keys())
            col_str = ", ".join(f'"{c}"' for c in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f'INSERT INTO "{table}" ({col_str}) VALUES ({placeholders})'
            with self._conn.cursor() as cur:
                for row in rows:
                    cur.execute(sql, [row[c] for c in columns])
            self._conn.commit()
            return {"inserted": len(rows)}
        except Exception as exc:
            self._conn.rollback()
            raise ExecutionError(f"Insert failed: {exc}") from exc

    def _connect_info(self) -> dict:
        return {"connected": self._conn is not None, "dsn": self._dsn}
```

> **⚠️ SQL Injection Warning — Dynamic Table and Column Names**
>
> The `_insert` helper above interpolates `table` and `columns` **directly into the SQL string** using
> f-strings.  Row *values* are safely passed as parameterised arguments (`[row[c] for c in columns]`),
> but the **table name** and **column names** are **not** parameterised — most database drivers do not
> support bind parameters for identifiers.
>
> If `table` or any column name can be influenced by untrusted input (e.g. user-supplied plugin
> configuration or API requests), this is a **SQL injection risk**.
>
> **Recommended mitigations:**
>
> 1. **Allowlist table and column names** against a hard-coded set of permitted identifiers before
>    building the SQL string:
>    ```python
>    ALLOWED_TABLES = {"orders", "products", "audit_log"}
>    ALLOWED_COLUMNS = {"id", "name", "created_at", "status"}
>
>    if table not in ALLOWED_TABLES:
>        raise ExecutionError(f"Table '{table}' is not permitted.")
>    for col in columns:
>        if col not in ALLOWED_COLUMNS:
>            raise ExecutionError(f"Column '{col}' is not permitted.")
>    ```
>
> 2. **Validate identifiers** with a strict regex (e.g. `^[A-Za-z_][A-Za-z0-9_]{0,63}$`) before
>    interpolation if a fixed allowlist is not practical.
>
> 3. **Never** build table or column names from raw user input without one of the above checks.

---

### Example 3: Custom ML Scorer Plugin

A lightweight machine learning confidence scorer using a simple keyword model. Demonstrates how to bring an ML pipeline into Murphy System.

```python
# ml_scorer_plugin.py

import re
from murphy_system.sdk import ConnectorPlugin, ConnectorCategory, AuthType
from murphy_system.sdk.exceptions import ExecutionError

class MLScorerPlugin(ConnectorPlugin):
    """A simple ML-based confidence scorer for text classification."""

    NAME = "ml_scorer"
    VERSION = "1.0.0"
    CATEGORY = ConnectorCategory.ML_AI
    AUTH_TYPE = AuthType.NONE

    # Keyword weights per label — replace with a real model in production
    _KEYWORD_WEIGHTS: dict[str, dict[str, float]] = {
        "positive": {"great": 1.0, "excellent": 1.2, "good": 0.8, "love": 1.1, "amazing": 1.3},
        "negative": {"bad": 1.0, "terrible": 1.4, "awful": 1.3, "hate": 1.2, "poor": 0.9},
        "neutral":  {"okay": 0.6, "fine": 0.5, "average": 0.7, "alright": 0.6}
    }

    def __init__(self):
        self._model_loaded = False

    def authenticate(self, credentials: dict) -> bool:
        # No credentials needed; "authentication" just triggers model warm-up
        self._model_loaded = True
        return True

    def execute(self, action: str, payload: dict) -> dict:
        if action == "score":
            return self._score(payload)
        elif action == "batch_score":
            return self._batch_score(payload)
        elif action == "model_info":
            return self._model_info()
        else:
            from murphy_system.sdk.exceptions import UnsupportedActionError
            raise UnsupportedActionError(f"Action '{action}' is not supported.")

    def health_check(self) -> dict:
        return {
            "status": "ok" if self._model_loaded else "error",
            "plugin": self.NAME,
            "details": {"model_loaded": self._model_loaded, "labels": list(self._KEYWORD_WEIGHTS)}
        }

    def schema(self) -> dict:
        return {
            "actions": ["score", "batch_score", "model_info"],
            "credentials": {},
            "input": {
                "score": {
                    "text": {"type": "string", "required": True, "description": "Text to classify"}
                },
                "batch_score": {
                    "texts": {"type": "array", "required": True, "description": "List of strings to score"}
                }
            },
            "output": {
                "score": {
                    "label":       {"type": "string",  "description": "Predicted label"},
                    "confidence":  {"type": "number",  "description": "Confidence score 0.0–1.0"},
                    "scores":      {"type": "object",  "description": "Per-label raw scores"}
                },
                "batch_score": {
                    "results": {"type": "array"}
                }
            }
        }

    # ── Private helpers ──────────────────────────────────────────────────────

    def _score(self, payload: dict) -> dict:
        text = payload.get("text", "")
        if not text:
            raise ExecutionError("'text' is required for the score action.")
        return self._compute_score(text)

    def _batch_score(self, payload: dict) -> dict:
        texts = payload.get("texts", [])
        if not texts or not isinstance(texts, list):
            raise ExecutionError("'texts' must be a non-empty list for batch_score.")
        return {"results": [self._compute_score(t) for t in texts]}

    def _model_info(self) -> dict:
        return {
            "model_type": "keyword_weighted",
            "version": self.VERSION,
            "labels": list(self._KEYWORD_WEIGHTS),
            "description": "Simple keyword-weight confidence scorer. Replace with a real model for production use."
        }

    def _compute_score(self, text: str) -> dict:
        tokens = re.findall(r"\b\w+\b", text.lower())
        raw_scores: dict[str, float] = {label: 0.0 for label in self._KEYWORD_WEIGHTS}
        for token in tokens:
            for label, weights in self._KEYWORD_WEIGHTS.items():
                if token in weights:
                    raw_scores[label] += weights[token]
        total = sum(raw_scores.values()) or 1.0
        confidences = {label: round(score / total, 4) for label, score in raw_scores.items()}
        best_label = max(confidences, key=lambda k: confidences[k])
        return {
            "label": best_label,
            "confidence": confidences[best_label],
            "scores": confidences
        }
```

---

## 5. Testing Your Plugin

### Unit test structure

Place tests alongside your plugin code or in a `tests/` directory:

```
my_plugin/
├── my_plugin.py
├── tests/
│   ├── __init__.py
│   └── test_my_plugin.py
└── requirements.txt
```

### Example pytest tests

```python
# tests/test_slack_notification_plugin.py

import pytest
from unittest.mock import patch, MagicMock
from slack_notification_plugin import SlackNotificationPlugin
from murphy_system.sdk.exceptions import AuthenticationError, ExecutionError

@pytest.fixture
def plugin():
    return SlackNotificationPlugin()

class TestAuthenticate:
    def test_invalid_token_prefix_raises(self, plugin):
        with pytest.raises(AuthenticationError, match="xoxb-"):
            plugin.authenticate({"bot_token": "invalid-token"})

    def test_slack_api_failure_raises(self, plugin):
        with patch.object(plugin, "_api_call", return_value={"ok": False, "error": "invalid_auth"}):
            with pytest.raises(AuthenticationError, match="invalid_auth"):
                plugin.authenticate({"bot_token": "xoxb-fake-token"})

    def test_successful_auth(self, plugin):
        with patch.object(plugin, "_api_call", return_value={"ok": True, "team": "TestTeam", "user": "bot"}):
            result = plugin.authenticate({"bot_token": "xoxb-fake-token"})
        assert result is True

class TestExecute:
    def test_send_message_missing_channel(self, plugin):
        plugin._token = "xoxb-fake"
        with pytest.raises(ExecutionError, match="channel"):
            plugin.execute("send_message", {"text": "Hello"})

    def test_send_message_success(self, plugin):
        plugin._token = "xoxb-fake"
        mock_response = {"ok": True, "ts": "12345.6789", "channel": "C01234"}
        with patch.object(plugin, "_api_call", return_value=mock_response):
            result = plugin.execute("send_message", {"channel": "C01234", "text": "Hi"})
        assert result["ok"] is True
        assert result["channel"] == "C01234"

    def test_unsupported_action(self, plugin):
        from murphy_system.sdk.exceptions import UnsupportedActionError
        plugin._token = "xoxb-fake"
        with pytest.raises(UnsupportedActionError):
            plugin.execute("delete_workspace", {})

class TestHealthCheck:
    def test_not_authenticated(self, plugin):
        result = plugin.health_check()
        assert result["status"] == "error"

    def test_healthy(self, plugin):
        plugin._token = "xoxb-fake"
        with patch.object(plugin, "_api_call", return_value={"ok": True, "team": "T1", "user": "bot"}):
            result = plugin.health_check()
        assert result["status"] == "ok"

class TestSchema:
    def test_schema_has_required_keys(self, plugin):
        s = plugin.schema()
        assert "actions" in s
        assert "credentials" in s
        assert "send_message" in s["actions"]
```

### Running tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=. --cov-report=term-missing

# Validate the plugin using the SDK validator
python - <<'EOF'
from murphy_system.sdk import PluginValidator
from slack_notification_plugin import SlackNotificationPlugin

result = PluginValidator().validate(SlackNotificationPlugin)
print("Valid:", result.is_valid)
for e in result.errors:
    print("ERROR:", e)
for w in result.warnings:
    print("WARN:", w)
EOF
```

All plugins submitted to the marketplace must achieve **100% pass rate** with no `ERROR`-level validation findings.

---

## 6. Submission Process

### Prerequisites

Before submitting, ensure your plugin meets these requirements:

| Requirement                         | Details                                              |
|-------------------------------------|------------------------------------------------------|
| Inherits `ConnectorPlugin`          | All 4 abstract methods implemented                   |
| `NAME` is unique and snake_case     | Check the [marketplace registry] for conflicts       |
| `VERSION` follows semver            | e.g., `1.0.0`                                        |
| `schema()` is complete              | All actions, inputs, outputs, and credentials listed |
| Tests present and passing           | Minimum 80% line coverage                            |
| No hardcoded credentials            | Use `credentials` dict in `authenticate()`           |
| Dependencies declared               | List in `requirements.txt` or `pyproject.toml`       |
| `PluginValidator` passes            | Zero errors, ideally zero warnings                   |

### Submission steps

1. **Fork the repository**

   ```bash
   gh repo fork inoni/Murphy-System --clone
   cd Murphy-System
   ```

2. **Create a feature branch**

   ```bash
   git checkout -b plugin/your-plugin-name
   ```

3. **Place your plugin** under `Murphy System/plugins/<your_plugin_name>/`

   ```
   Murphy System/plugins/slack_notification/
   ├── __init__.py
   ├── slack_notification_plugin.py
   ├── requirements.txt
   ├── README.md
   └── tests/
       └── test_slack_notification_plugin.py
   ```

4. **Run the validator**

   ```bash
   python -m murphy_system.sdk.cli validate Murphy\ System/plugins/slack_notification/
   ```

5. **Open a Pull Request** against `main` with the title: `[Plugin] Your Plugin Name vX.Y.Z`

6. **Fill in the PR template** (see below) and await review from a core maintainer.

### PR description template

```markdown
## Plugin Submission: <Plugin Name>

**Category:** <ConnectorCategory value>
**Version:** <semver>
**Auth Type:** <AuthType value>

### Description
<!-- One paragraph describing what this plugin does -->

### Actions
| Action | Description |
|--------|-------------|
| action_one | ... |

### External dependencies
<!-- List any third-party packages required -->

### Test coverage
<!-- Attach or paste coverage report summary -->

### Checklist
- [ ] `PluginValidator` passes with zero errors
- [ ] All abstract methods implemented
- [ ] Tests present with ≥ 80% coverage
- [ ] No hardcoded secrets
- [ ] `schema()` fully documents all actions
- [ ] README.md included in plugin directory
```

---

## 7. Marketplace Listing Instructions

Once your PR is merged, your plugin is automatically listed in the Murphy System Marketplace. To optimise your listing:

### Required metadata (in `README.md` front-matter)

```yaml
---
plugin_name: slack_notification
display_name: "Slack Notifications"
version: "1.0.0"
author: "Your Name"
author_email: "you@example.com"
category: COMMUNICATION
auth_type: API_KEY
description: "Send messages and alerts to Slack channels from any Murphy System workflow."
tags: [slack, messaging, notifications, alerts]
min_murphy_version: "2.0.0"
license: MIT
homepage: "https://github.com/your-org/your-plugin"
---
```

### Quality tiers

| Tier        | Badge       | Requirements                                                 |
|-------------|-------------|--------------------------------------------------------------|
| Community   | ⭐           | Passes validation, tests present                             |
| Verified    | ✅ Verified  | ≥ 90% test coverage, docs complete, maintained actively      |
| Official    | 🏅 Official  | Maintained by Inoni LLC or a certified partner organisation  |

### Marketplace categories page

Your plugin will appear at:
`https://marketplace.murphy-system.io/plugins/<your_plugin_name>`

The listing page is auto-generated from your `README.md`, `schema()` output, and the front-matter metadata above. Keep your `README.md` clear and your `schema()` descriptions accurate — they power the user-facing documentation.
