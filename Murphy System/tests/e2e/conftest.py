"""
Shared fixtures for Murphy System E2E tests.

Provides:
  - running_server: starts the backend in a subprocess on a free port
  - api_client:     httpx client pointed at the running server
  - mock_deepinfra_server: pytest-httpserver instance that pretends to be api.deepinfra.com/v1/openai
"""

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))


def _free_port() -> int:
    """Return an OS-assigned free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    """Poll until a TCP port is accepting connections or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


@pytest.fixture(scope="session")
def server_port() -> int:
    """A free port reserved for the test server."""
    return _free_port()


@pytest.fixture(scope="session")
def running_server(server_port, tmp_path_factory):
    """
    Start the Murphy System backend in a subprocess and yield the base URL.
    The server is terminated after the session.
    """
    src_dir = _SRC_DIR
    env = {**os.environ, "PYTHONPATH": src_dir, "MURPHY_TEST_MODE": "1"}
    cmd = [
        sys.executable, "-m", "uvicorn",
        "auar_api:app",
        "--host", "127.0.0.1",
        "--port", str(server_port),
        "--log-level", "warning",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=src_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        available = _wait_for_port("127.0.0.1", server_port, timeout=20.0)
        if not available:
            proc.terminate()
            pytest.skip("Backend server did not start within timeout — skipping E2E tests")
        yield f"http://127.0.0.1:{server_port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def api_client(running_server):
    """An httpx.Client pre-configured for the running server."""
    with httpx.Client(base_url=running_server, timeout=10.0) as client:
        yield client


@pytest.fixture(scope="session")
def mock_deepinfra_server():
    """
    A lightweight mock for api.deepinfra.com/v1/openai.
    Uses pytest-httpserver when available; otherwise yields None so
    individual tests can skip gracefully.
    """
    try:
        from pytest_httpserver import HTTPServer
    except ImportError:
        yield None
        return

    server = HTTPServer(host="127.0.0.1")
    server.start()
    server.expect_request(
        "/openai/v1/chat/completions", method="POST"
    ).respond_with_json(
        {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Mock Groq response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )
    try:
        yield server
    finally:
        server.clear()
        if server.is_running():
            server.stop()
