/**
 * Murphy System Load Testing with k6
 * 
 * Usage:
 *   k6 run tests/performance/k6_test.js
 * 
 * With options:
 *   k6 run --vus 10 --duration 30s tests/performance/k6_test.js
 *   k6 run --vus 50 --duration 5m tests/performance/k6_test.js
 * 
 * Environment:
 *   K6_MURPHY_HOST - API host (default: http://localhost:8000)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const healthLatency = new Trend('health_latency');
const chatLatency = new Trend('chat_latency');

// Test configuration
export const options = {
    stages: [
        { duration: '30s', target: 10 },  // Ramp up to 10 users
        { duration: '1m', target: 10 },   // Stay at 10 users
        { duration: '30s', target: 50 },  // Ramp up to 50 users
        { duration: '2m', target: 50 },   // Stay at 50 users
        { duration: '30s', target: 0 },   // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<500'],  // 95% of requests under 500ms
        errors: ['rate<0.1'],              // Error rate under 10%
    },
};

const BASE_URL = __ENV.K6_MURPHY_HOST || 'http://localhost:8000';

export default function() {
    // Health check (most common)
    const healthRes = http.get(`${BASE_URL}/api/health`);
    healthLatency.add(healthRes.timings.duration);
    check(healthRes, {
        'health status is 200': (r) => r.status === 200,
        'health has ok field': (r) => JSON.parse(r.body).ok === true,
    });
    errorRate.add(healthRes.status !== 200);
    
    sleep(0.5);
    
    // Status check
    const statusRes = http.get(`${BASE_URL}/api/status`);
    check(statusRes, {
        'status returns 200 or 401': (r) => r.status === 200 || r.status === 401,
    });
    
    sleep(0.5);
    
    // Chat endpoint (if authenticated)
    const chatRes = http.post(`${BASE_URL}/api/chat`, 
        JSON.stringify({ message: 'ping' }),
        { headers: { 'Content-Type': 'application/json' } }
    );
    chatLatency.add(chatRes.timings.duration);
    check(chatRes, {
        'chat returns response': (r) => r.status === 200 || r.status === 401,
    });
    errorRate.add(chatRes.status >= 500);
    
    sleep(1);
}

export function handleSummary(data) {
    return {
        'tests/performance/k6_results.json': JSON.stringify(data, null, 2),
    };
}
