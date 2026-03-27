"""
Murphy System Load Testing with Locust

Usage:
    pip install locust
    locust -f tests/performance/locustfile.py --host=http://localhost:8000

Web UI at http://localhost:8089

Environment variables:
    MURPHY_TEST_USER - Test user email (default: test@murphy.systems)
    MURPHY_TEST_PASS - Test user password (default: testpass123)
"""

import os
from locust import HttpUser, task, between


class MurphyUser(HttpUser):
    """Simulates a typical Murphy System user."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Login on start."""
        email = os.environ.get("MURPHY_TEST_USER", "test@murphy.systems")
        password = os.environ.get("MURPHY_TEST_PASS", "testpass123")
        
        response = self.client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token", "")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = ""
            self.headers = {}
    
    @task(10)
    def health_check(self):
        """Most common: health check."""
        self.client.get("/api/health")
    
    @task(5)
    def status_check(self):
        """Check system status."""
        self.client.get("/api/status", headers=self.headers)
    
    @task(3)
    def chat_message(self):
        """Send a chat message."""
        self.client.post("/api/chat", 
            json={"message": "What can you do?"},
            headers=self.headers
        )
    
    @task(2)
    def list_modules(self):
        """List available modules."""
        self.client.get("/api/modules", headers=self.headers)
    
    @task(2)
    def list_workflows(self):
        """List workflows."""
        self.client.get("/api/workflows", headers=self.headers)
    
    @task(1)
    def founder_status(self):
        """Check founder status (owner only)."""
        self.client.get("/api/founder/status", headers=self.headers)


class APIOnlyUser(HttpUser):
    """Simulates unauthenticated API calls."""
    
    wait_time = between(0.5, 2)
    
    @task(10)
    def health_check(self):
        """Health check - most common."""
        self.client.get("/api/health")
    
    @task(5)
    def openapi_schema(self):
        """Fetch OpenAPI schema."""
        self.client.get("/api/openapi.json")
    
    @task(2)
    def landing_page(self):
        """Load landing page."""
        self.client.get("/")
