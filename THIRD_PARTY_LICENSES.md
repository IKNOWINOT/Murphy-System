# Third-Party Licenses — Murphy System

**Last Updated:** 2026-03-13

Murphy System is licensed under BSL 1.1 (Business Source License).
This document lists all third-party dependencies, their licenses, and
links to the full license text.

All dependencies use permissive licenses (MIT, BSD, Apache 2.0, ISC,
PSF, MPL 2.0) that are compatible with BSL 1.1 distribution.

---

## Core Dependencies

| Package | License | URL |
|---------|---------|-----|
| fastapi | MIT | https://github.com/tiangolo/fastapi/blob/master/LICENSE |
| uvicorn | BSD-3-Clause | https://github.com/encode/uvicorn/blob/master/LICENSE.md |
| pydantic | MIT | https://github.com/pydantic/pydantic/blob/main/LICENSE |
| pydantic-settings | MIT | https://github.com/pydantic/pydantic-settings/blob/main/LICENSE |
| python-multipart | Apache-2.0 | https://github.com/Kludex/python-multipart/blob/master/LICENSE.txt |
| flask | BSD-3-Clause | https://github.com/pallets/flask/blob/main/LICENSE.txt |
| flask-cors | MIT | https://github.com/corydolphin/flask-cors/blob/main/LICENSE |
| starlette | BSD-3-Clause | https://github.com/encode/starlette/blob/master/LICENSE.md |

## Async Support

| Package | License | URL |
|---------|---------|-----|
| aiohttp | Apache-2.0 | https://github.com/aio-libs/aiohttp/blob/master/LICENSE.txt |
| httpx | BSD-3-Clause | https://github.com/encode/httpx/blob/master/LICENSE.md |

## Database

| Package | License | URL |
|---------|---------|-----|
| sqlalchemy | MIT | https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE |
| psycopg2-binary | LGPL-3.0 | https://github.com/psycopg/psycopg2/blob/master/LICENSE |
| alembic | MIT | https://github.com/sqlalchemy/alembic/blob/main/LICENSE |

> **Note on psycopg2-binary:** LGPL-3.0 permits dynamic linking (the
> standard Python import mechanism) without copyleft obligations on the
> calling code. Murphy System does not statically link or modify psycopg2.

## Cache & Queue

| Package | License | URL |
|---------|---------|-----|
| redis | MIT | https://github.com/redis/redis-py/blob/master/LICENSE |
| celery | BSD-3-Clause | https://github.com/celery/celery/blob/main/LICENSE |

## Data Processing

| Package | License | URL |
|---------|---------|-----|
| pandas | BSD-3-Clause | https://github.com/pandas-dev/pandas/blob/main/LICENSE |
| numpy | BSD-3-Clause | https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| scipy | BSD-3-Clause | https://github.com/scipy/scipy/blob/main/LICENSE.txt |
| sympy | BSD-3-Clause | https://github.com/sympy/sympy/blob/master/LICENSE |

## Machine Learning

| Package | License | URL |
|---------|---------|-----|
| scikit-learn | BSD-3-Clause | https://github.com/scikit-learn/scikit-learn/blob/main/COPYING |
| torch | BSD-3-Clause | https://github.com/pytorch/pytorch/blob/main/LICENSE |
| torch-geometric | MIT | https://github.com/pyg-team/pytorch_geometric/blob/master/LICENSE |
| transformers | Apache-2.0 | https://github.com/huggingface/transformers/blob/main/LICENSE |
| sentencepiece | Apache-2.0 | https://github.com/google/sentencepiece/blob/master/LICENSE |
| tensorboard | Apache-2.0 | https://github.com/tensorflow/tensorboard/blob/master/LICENSE |

## NLP

| Package | License | URL |
|---------|---------|-----|
| spacy | MIT | https://github.com/explosion/spaCy/blob/master/LICENSE |
| nltk | Apache-2.0 | https://github.com/nltk/nltk/blob/develop/LICENSE.txt |

## LLM Integration

| Package | License | URL |
|---------|---------|-----|
| openai | Apache-2.0 | https://github.com/openai/openai-python/blob/main/LICENSE |
| anthropic | MIT | https://github.com/anthropics/anthropic-sdk-python/blob/main/LICENSE |
| deepinfra | Apache-2.0 | https://github.com/deepinfra/deepinfra-python/blob/main/LICENSE |

## Data Validation

| Package | License | URL |
|---------|---------|-----|
| jsonschema | MIT | https://github.com/python-jsonschema/jsonschema/blob/main/COPYING |
| pyyaml | MIT | https://github.com/yaml/pyyaml/blob/main/LICENSE |
| toml | MIT | https://github.com/uiri/toml/blob/master/LICENSE |

## HTTP & API

| Package | License | URL |
|---------|---------|-----|
| requests | Apache-2.0 | https://github.com/psf/requests/blob/main/LICENSE |
| urllib3 | MIT | https://github.com/urllib3/urllib3/blob/main/LICENSE.txt |
| beautifulsoup4 | MIT | https://www.crummy.com/software/BeautifulSoup/ |

## File Processing

| Package | License | URL |
|---------|---------|-----|
| python-magic | MIT | https://github.com/ahupp/python-magic/blob/master/LICENSE |
| pillow | HPND | https://github.com/python-pillow/Pillow/blob/main/LICENSE |
| pypdf2 | BSD-3-Clause | https://github.com/py-pdf/pypdf/blob/main/LICENSE |
| weasyprint | BSD-3-Clause | https://github.com/Kozea/WeasyPrint/blob/main/LICENSE |

> **Note on WeasyPrint:** BSD-3-Clause; used as an **optional** dependency for
> rich HTML→PDF rendering. The code falls back to reportlab when WeasyPrint's
> system libraries (cairo, pango, gdk-pixbuf2) are unavailable. Attribution
> required per BSD-3-Clause: © WeasyPrint contributors.

## Cryptography & Security

| Package | License | URL |
|---------|---------|-----|
| cryptography | Apache-2.0 / BSD-3-Clause | https://github.com/pyca/cryptography/blob/main/LICENSE |
| pyjwt | MIT | https://github.com/jpadilla/pyjwt/blob/master/LICENSE |
| bcrypt | Apache-2.0 | https://github.com/pyca/bcrypt/blob/main/LICENSE |

## Monitoring & Logging

| Package | License | URL |
|---------|---------|-----|
| prometheus-client | Apache-2.0 | https://github.com/prometheus/client_python/blob/master/LICENSE |
| python-json-logger | BSD-2-Clause | https://github.com/madzak/python-json-logger/blob/master/LICENSE |
| sentry-sdk | MIT | https://github.com/getsentry/sentry-python/blob/master/LICENSE |

## Testing & Code Quality

| Package | License | URL |
|---------|---------|-----|
| pytest | MIT | https://github.com/pytest-dev/pytest/blob/main/LICENSE |
| pytest-asyncio | Apache-2.0 | https://github.com/pytest-dev/pytest-asyncio/blob/main/LICENSE |
| pytest-cov | MIT | https://github.com/pytest-dev/pytest-cov/blob/master/LICENSE |
| pytest-mock | MIT | https://github.com/pytest-dev/pytest-mock/blob/main/LICENSE |
| pytest-timeout | MIT | https://github.com/pytest-dev/pytest-timeout/blob/master/LICENSE |
| black | MIT | https://github.com/psf/black/blob/main/LICENSE |
| flake8 | MIT | https://github.com/PyCQA/flake8/blob/main/LICENSE |
| mypy | MIT | https://github.com/python/mypy/blob/master/LICENSE |
| ruff | MIT | https://github.com/astral-sh/ruff/blob/main/LICENSE |

## Documentation

| Package | License | URL |
|---------|---------|-----|
| mkdocs | BSD-2-Clause | https://github.com/mkdocs/mkdocs/blob/master/LICENSE |
| mkdocs-material | MIT | https://github.com/squidfunk/mkdocs-material/blob/master/LICENSE |

## Utilities

| Package | License | URL |
|---------|---------|-----|
| python-dotenv | BSD-3-Clause | https://github.com/theskumar/python-dotenv/blob/main/LICENSE |
| click | BSD-3-Clause | https://github.com/pallets/click/blob/main/LICENSE.txt |
| rich | MIT | https://github.com/Textualize/rich/blob/master/LICENSE |
| textual | MIT | https://github.com/Textualize/textual/blob/main/LICENSE |
| pyfiglet | MIT | https://github.com/pwaller/pyfiglet/blob/master/LICENSE |
| tqdm | MPL-2.0 / MIT | https://github.com/tqdm/tqdm/blob/master/LICENCE |
| pyperclip | BSD-3-Clause | https://github.com/asweigart/pyperclip/blob/master/LICENSE.txt |
| prompt-toolkit | BSD-3-Clause | https://github.com/prompt-toolkit/python-prompt-toolkit/blob/master/LICENSE |

## Date & Time

| Package | License | URL |
|---------|---------|-----|
| python-dateutil | Apache-2.0 / BSD-3-Clause | https://github.com/dateutil/dateutil/blob/master/LICENSE |
| pytz | MIT | https://github.com/stub42/pytz/blob/master/LICENSE.txt |

## Git Integration

| Package | License | URL |
|---------|---------|-----|
| gitpython | BSD-3-Clause | https://github.com/gitpython-developers/GitPython/blob/main/LICENSE |

## Docker & Kubernetes

| Package | License | URL |
|---------|---------|-----|
| docker | Apache-2.0 | https://github.com/docker/docker-py/blob/main/LICENSE |
| kubernetes | Apache-2.0 | https://github.com/kubernetes-client/python/blob/master/LICENSE |

## Cloud Providers

| Package | License | URL |
|---------|---------|-----|
| boto3 | Apache-2.0 | https://github.com/boto/boto3/blob/develop/LICENSE |
| google-cloud-storage | Apache-2.0 | https://github.com/googleapis/python-storage/blob/main/LICENSE |
| azure-storage-blob | MIT | https://github.com/Azure/azure-sdk-for-python/blob/main/LICENSE |

## Payment Processing

| Package | License | URL |
|---------|---------|-----|
| stripe | MIT | https://github.com/stripe/stripe-python/blob/master/LICENSE |

## Communication

| Package | License | URL |
|---------|---------|-----|
| twilio | MIT | https://github.com/twilio/twilio-python/blob/main/LICENSE |
| sendgrid | MIT | https://github.com/sendgrid/sendgrid-python/blob/main/LICENSE |

## Data Serialization

| Package | License | URL |
|---------|---------|-----|
| msgpack | Apache-2.0 | https://github.com/msgpack/msgpack-python/blob/main/COPYING |
| protobuf | BSD-3-Clause | https://github.com/protocolbuffers/protobuf/blob/main/LICENSE |

## Compression & System

| Package | License | URL |
|---------|---------|-----|
| zstandard | BSD-3-Clause | https://github.com/indygreg/python-zstandard/blob/main/LICENSE |
| psutil | BSD-3-Clause | https://github.com/giampaolo/psutil/blob/master/LICENSE |
| watchdog | Apache-2.0 | https://github.com/gorakhargosh/watchdog/blob/master/LICENSE |
| matplotlib | PSF-based | https://github.com/matplotlib/matplotlib/blob/main/LICENSE/LICENSE |
| networkx | BSD-3-Clause | https://github.com/networkx/networkx/blob/main/LICENSE.txt |

## Development

| Package | License | URL |
|---------|---------|-----|
| ipython | BSD-3-Clause | https://github.com/ipython/ipython/blob/main/LICENSE |
| jupyter | BSD-3-Clause | https://github.com/jupyter/jupyter/blob/master/LICENSE |
| notebook | BSD-3-Clause | https://github.com/jupyter/notebook/blob/main/LICENSE |
| websocket-client | Apache-2.0 | https://github.com/websocket-client/websocket-client/blob/master/LICENSE |
| tomli | MIT | https://github.com/hukkin/tomli/blob/master/LICENSE |

## Node.js Dependencies (bots/)

| Package | License | URL |
|---------|---------|-----|
| vitest | MIT | https://github.com/vitest-dev/vitest/blob/main/LICENSE |
| zod | MIT | https://github.com/colinhacks/zod/blob/main/LICENSE |

---

## Removed Dependencies

| Package | Former License | Reason | Replacement |
|---------|---------------|--------|-------------|
| pylint | GPL-2.0 | Copyleft incompatible with BSL 1.1 distribution | ruff (MIT) |

---

## License Compatibility Summary

All listed dependencies use licenses that are compatible with BSL 1.1:
- **MIT** — Permissive, no copyleft
- **BSD-2-Clause / BSD-3-Clause** — Permissive, no copyleft
- **Apache-2.0** — Permissive, patent grant
- **ISC** — Permissive (MIT-equivalent)
- **PSF** — Python Software Foundation license, permissive
- **MPL-2.0** — Weak copyleft, file-level only (compatible)
- **HPND** — Historical Permission Notice and Disclaimer, permissive
- **LGPL-3.0** (psycopg2-binary only) — Dynamic linking permitted without copyleft

No GPL, AGPL, SSPL, CC-BY-NC, CC-BY-ND, or EUPL dependencies are included.
