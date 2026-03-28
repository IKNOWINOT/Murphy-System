"""Tests for APIGatewayAdapter."""

import os
import unittest


from api_gateway_adapter import (
    APIGatewayAdapter,
    RouteDefinition,
    RouteMethod,
    GatewayAuthMethod,
    GatewayRequest,
    RateLimitRule,
    CircuitBreakerConfig,
    CircuitState,
)


class TestAPIGatewayAdapter(unittest.TestCase):

    def setUp(self):
        self.gw = APIGatewayAdapter()

    def _register_test_route(self, route_id="test", path="/api/test", method=RouteMethod.GET,
                              auth=GatewayAuthMethod.NONE):
        route = RouteDefinition(
            route_id=route_id,
            path=path,
            method=method,
            target_service="test_service",
            auth_method=auth,
        )
        self.gw.register_route(route)
        return route

    def test_register_route(self):
        self.assertTrue(self.gw.register_route(RouteDefinition(
            route_id="r1", path="/api/test", method=RouteMethod.GET, target_service="svc"
        )))

    def test_process_request_success(self):
        self._register_test_route()
        req = GatewayRequest(request_id="req1", path="/api/test", method="GET")
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.body)

    def test_process_request_not_found(self):
        req = GatewayRequest(request_id="req2", path="/api/missing", method="GET")
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 404)

    def test_auth_api_key_valid(self):
        self._register_test_route(auth=GatewayAuthMethod.API_KEY)
        self.gw.register_api_key("valid-key", "client1")
        req = GatewayRequest(
            request_id="auth1", path="/api/test", method="GET",
            headers={"X-API-Key": "valid-key"},
        )
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 200)

    def test_auth_api_key_invalid(self):
        self._register_test_route(auth=GatewayAuthMethod.API_KEY)
        req = GatewayRequest(
            request_id="auth2", path="/api/test", method="GET",
            headers={"X-API-Key": "bad-key"},
        )
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 401)

    def test_auth_bearer_missing(self):
        self._register_test_route(auth=GatewayAuthMethod.BEARER_TOKEN)
        req = GatewayRequest(
            request_id="auth3", path="/api/test", method="GET",
            headers={},
        )
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 401)

    def test_auth_bearer_valid(self):
        self._register_test_route(auth=GatewayAuthMethod.BEARER_TOKEN)
        req = GatewayRequest(
            request_id="auth4", path="/api/test", method="GET",
            headers={"Authorization": "Bearer tok-123"},
        )
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 200)

    def test_rate_limit(self):
        route = RouteDefinition(
            route_id="rl", path="/api/rl", method=RouteMethod.GET,
            target_service="svc",
            rate_limit=RateLimitRule(max_requests=2, window_seconds=60, per_client=False),
        )
        self.gw.register_route(route)
        for i in range(2):
            req = GatewayRequest(request_id=f"rl{i}", path="/api/rl", method="GET")
            resp = self.gw.process_request(req)
            self.assertEqual(resp.status_code, 200)
        req = GatewayRequest(request_id="rl_blocked", path="/api/rl", method="GET")
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 429)

    def test_per_client_rate_limit(self):
        route = RouteDefinition(
            route_id="pcrl", path="/api/pcrl", method=RouteMethod.GET,
            target_service="svc",
            rate_limit=RateLimitRule(max_requests=1, window_seconds=60, per_client=True),
        )
        self.gw.register_route(route)
        req1 = GatewayRequest(request_id="pcrl1", path="/api/pcrl", method="GET", client_id="c1")
        resp1 = self.gw.process_request(req1)
        self.assertEqual(resp1.status_code, 200)
        req2 = GatewayRequest(request_id="pcrl2", path="/api/pcrl", method="GET", client_id="c2")
        resp2 = self.gw.process_request(req2)
        self.assertEqual(resp2.status_code, 200)
        req3 = GatewayRequest(request_id="pcrl3", path="/api/pcrl", method="GET", client_id="c1")
        resp3 = self.gw.process_request(req3)
        self.assertEqual(resp3.status_code, 429)

    def test_circuit_breaker_opens(self):
        route = RouteDefinition(
            route_id="cb", path="/api/cb", method=RouteMethod.POST,
            target_service="failing_svc",
            circuit_breaker=CircuitBreakerConfig(failure_threshold=2),
        )
        self.gw.register_route(route)
        self.gw.register_handler("failing_svc", lambda r: 1/0)
        for i in range(2):
            req = GatewayRequest(request_id=f"cb{i}", path="/api/cb", method="POST")
            self.gw.process_request(req)
        req = GatewayRequest(request_id="cb_blocked", path="/api/cb", method="POST")
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 503)

    def test_handler_execution(self):
        self._register_test_route()
        self.gw.register_handler("test_service", lambda r: {"result": "ok"})
        req = GatewayRequest(request_id="h1", path="/api/test", method="GET")
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body["result"], "ok")

    def test_handler_exception(self):
        self._register_test_route(method=RouteMethod.POST)
        self.gw.register_handler("test_service", lambda r: 1/0)
        req = GatewayRequest(request_id="err1", path="/api/test", method="POST")
        resp = self.gw.process_request(req)
        self.assertEqual(resp.status_code, 500)

    def test_caching(self):
        route = RouteDefinition(
            route_id="cache", path="/api/cache", method=RouteMethod.GET,
            target_service="cache_svc",
            cache_ttl=60,
        )
        self.gw.register_route(route)
        req1 = GatewayRequest(request_id="c1", path="/api/cache", method="GET")
        resp1 = self.gw.process_request(req1)
        self.assertFalse(resp1.cached)
        req2 = GatewayRequest(request_id="c2", path="/api/cache", method="GET")
        resp2 = self.gw.process_request(req2)
        self.assertTrue(resp2.cached)

    def test_webhook_subscription(self):
        sub_id = self.gw.subscribe_webhook("task_completed", "https://example.com/hook", "secret")
        self.assertIsNotNone(sub_id)
        subs = self.gw.list_webhook_subscriptions()
        self.assertIn("task_completed", subs)

    def test_webhook_dispatch(self):
        self.gw.subscribe_webhook("task_completed", "https://example.com/hook")
        results = self.gw.dispatch_webhook("task_completed", {"task_id": "123"})
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["dispatched"])

    def test_route_stats(self):
        self._register_test_route()
        req = GatewayRequest(request_id="s1", path="/api/test", method="GET")
        self.gw.process_request(req)
        stats = self.gw.get_route_stats()
        self.assertGreater(len(stats), 0)
        self.assertEqual(stats[0]["request_count"], 1)

    def test_statistics(self):
        stats = self.gw.get_statistics()
        self.assertIn("total_routes", stats)
        self.assertIn("success_rate", stats)

    def test_status(self):
        status = self.gw.status()
        self.assertEqual(status["module"], "api_gateway_adapter")

    def test_any_method_route(self):
        route = RouteDefinition(
            route_id="any", path="/api/any", method=RouteMethod.ANY, target_service="svc"
        )
        self.gw.register_route(route)
        for method in ["GET", "POST", "PUT", "DELETE"]:
            req = GatewayRequest(request_id=f"any_{method}", path="/api/any", method=method)
            resp = self.gw.process_request(req)
            self.assertEqual(resp.status_code, 200)

    def test_latency_recorded(self):
        self._register_test_route()
        req = GatewayRequest(request_id="lat1", path="/api/test", method="GET")
        resp = self.gw.process_request(req)
        self.assertGreaterEqual(resp.latency_ms, 0)


if __name__ == "__main__":
    unittest.main()
