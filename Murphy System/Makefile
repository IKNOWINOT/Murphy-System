# Murphy System Makefile
# Copyright 2024-2026 Corey Post, Inoni LLC
# License: BSL 1.1
#
# Usage: make setup && make up

.PHONY: setup up down test demo trace flow status help

setup:
	python3 -m venv venv
	venv/bin/pip install --upgrade pip
	venv/bin/pip install -r requirements_murphy_1.0.txt
	@if [ ! -f .env ]; then cp .env.example .env && echo ".env created from .env.example"; fi

up:
	venv/bin/python murphy_system_1.0_runtime.py

down:
	@pkill -f "murphy_system_1.0_runtime" && echo "Murphy API stopped." || echo "No Murphy process found."

test:
	venv/bin/pytest --cov=src --cov-report=term-missing

demo:
	venv/bin/python scripts/quick_demo.py

trace:
	@echo "Opening trace dashboard at http://localhost:8000/api/traces/stats"
	@xdg-open http://localhost:8000/api/traces/stats 2>/dev/null || open http://localhost:8000/api/traces/stats 2>/dev/null || echo "Visit: http://localhost:8000/api/traces/stats"

flow:
	@echo "Flow Canvas URL: http://localhost:5173"

status:
	@curl -s http://localhost:8000/api/health | python3 -m json.tool || echo "Murphy API is not running. Run: make up"

help:
	@echo ""
	@echo "Murphy System - Available Make Targets"
	@echo "======================================="
	@echo "  setup   - Create venv, install dependencies, init .env"
	@echo "  up      - Start the Murphy API (uvicorn, port 8000)"
	@echo "  down    - Stop the Murphy API"
	@echo "  test    - Run pytest with coverage"
	@echo "  demo    - Run the quick demo script"
	@echo "  trace   - Open trace dashboard (http://localhost:8000/api/traces/stats)"
	@echo "  flow    - Print the Flow Canvas URL (http://localhost:5173)"
	@echo "  status  - Health check the running Murphy API"
	@echo "  help    - Show this help message"
	@echo ""
	@echo "Quick start: make setup && make up"
	@echo ""
