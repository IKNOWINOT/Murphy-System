"""
Locust load test for Murphy System FastAPI server.

Run with:
    locust -f tests/benchmarks/locust_benchmark.py --host http://localhost:8000 \\
           --users 50 --spawn-rate 10 --run-time 60s --headless

GAP 2 closure: real HTTP load test targeting 1000+ req/s and <100ms p95.
"""
try:
    from locust import HttpUser, task, between, events  # type: ignore[import]

    class MurphyLoadUser(HttpUser):
        """Simulates a Murphy System API user."""
        wait_time = between(0.01, 0.05)

        @task(5)
        def health_check(self):
            """GET /api/health — hot path, should be cached."""
            self.client.get("/api/health", name="/api/health")

        @task(3)
        def status_check(self):
            """GET /api/status."""
            self.client.get("/api/status", name="/api/status")

        @task(2)
        def execute_task(self):
            """POST /api/execute — core execution path."""
            self.client.post(
                "/api/execute",
                json={
                    "request": "monitor system health",
                    "user_id": "load_test_user",
                    "repository_id": "load_test_repo",
                },
                name="/api/execute",
            )

        @task(1)
        def list_connectors(self):
            """GET /api/connectors — connector status."""
            self.client.get("/api/connectors", name="/api/connectors")

except ImportError:
    pass
