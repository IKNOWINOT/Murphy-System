/**
 * Murphy System Load Test
 * 
 * This script performs load testing on the Murphy System API
 * using k6 (https://k6.io/)
 * 
 * Usage: k6 run load-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiResponseTime = new Trend('api_response_time');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '5m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 200 },  // Ramp up to 200 users
    { duration: '5m', target: 200 },  // Stay at 200 users
    { duration: '5m', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    'http_req_duration': ['p(95)<1000'], // 95% of requests should be below 1s
    'errors': ['rate<0.1'],              // Error rate should be below 10%
    'http_req_failed': ['rate<0.05'],    // Failed requests should be below 5%
  },
};

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-api-key';

const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
};

// Test scenarios
export default function () {
  // Scenario 1: Health Check (10% of requests)
  if (Math.random() < 0.1) {
    testHealthCheck();
  }
  
  // Scenario 2: Task Submission (40% of requests)
  else if (Math.random() < 0.5) {
    testTaskSubmission();
  }
  
  // Scenario 3: Task Status Check (30% of requests)
  else if (Math.random() < 0.8) {
    testTaskStatus();
  }
  
  // Scenario 4: Shadow Agent Prediction (20% of requests)
  else {
    testShadowAgentPrediction();
  }
  
  sleep(1);
}

function testHealthCheck() {
  const res = http.get(`${BASE_URL}/health`);
  
  const success = check(res, {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 200ms': (r) => r.timings.duration < 200,
  });
  
  errorRate.add(!success);
  apiResponseTime.add(res.timings.duration);
}

function testTaskSubmission() {
  const payload = JSON.stringify({
    description: 'Test task for load testing',
    parameters: {
      test: true,
      timestamp: Date.now(),
    },
  });
  
  const res = http.post(
    `${BASE_URL}/api/forms/task-execution`,
    payload,
    { headers }
  );
  
  const success = check(res, {
    'task submission status is 200': (r) => r.status === 200,
    'task submission has task_id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.task_id !== undefined;
      } catch (e) {
        return false;
      }
    },
    'task submission response time < 1000ms': (r) => r.timings.duration < 1000,
  });
  
  errorRate.add(!success);
  apiResponseTime.add(res.timings.duration);
}

function testTaskStatus() {
  // Use a mock task ID for testing
  const taskId = 'test-task-' + Math.floor(Math.random() * 1000);
  
  const res = http.get(
    `${BASE_URL}/api/tasks/${taskId}/status`,
    { headers }
  );
  
  const success = check(res, {
    'task status response received': (r) => r.status === 200 || r.status === 404,
    'task status response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  errorRate.add(!success);
  apiResponseTime.add(res.timings.duration);
}

function testShadowAgentPrediction() {
  const payload = JSON.stringify({
    input_features: {
      task_type: 'validation',
      complexity: Math.floor(Math.random() * 10),
      context: {
        test: true,
      },
    },
    use_fallback: true,
  });
  
  const res = http.post(
    `${BASE_URL}/api/shadow-agent/predict`,
    payload,
    { headers }
  );
  
  const success = check(res, {
    'prediction status is 200': (r) => r.status === 200,
    'prediction has confidence': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.confidence !== undefined;
      } catch (e) {
        return false;
      }
    },
    'prediction response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  errorRate.add(!success);
  apiResponseTime.add(res.timings.duration);
}

// Setup function (runs once at the start)
export function setup() {
  console.log('Starting load test...');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`API Key: ${API_KEY.substring(0, 10)}...`);
  
  // Verify API is accessible
  const res = http.get(`${BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`API not accessible: ${res.status}`);
  }
  
  console.log('API is accessible, starting test...');
}

// Teardown function (runs once at the end)
export function teardown(data) {
  console.log('Load test completed!');
}

// Handle summary
export function handleSummary(data) {
  return {
    'load-test-results.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, options) {
  const indent = options.indent || '';
  const enableColors = options.enableColors || false;
  
  let summary = '\n';
  summary += `${indent}Load Test Summary\n`;
  summary += `${indent}================\n\n`;
  
  // Requests
  summary += `${indent}Requests:\n`;
  summary += `${indent}  Total: ${data.metrics.http_reqs.values.count}\n`;
  summary += `${indent}  Rate: ${data.metrics.http_reqs.values.rate.toFixed(2)}/s\n\n`;
  
  // Response times
  summary += `${indent}Response Times:\n`;
  summary += `${indent}  Avg: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms\n`;
  summary += `${indent}  Min: ${data.metrics.http_req_duration.values.min.toFixed(2)}ms\n`;
  summary += `${indent}  Max: ${data.metrics.http_req_duration.values.max.toFixed(2)}ms\n`;
  summary += `${indent}  p(95): ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms\n`;
  summary += `${indent}  p(99): ${data.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms\n\n`;
  
  // Errors
  summary += `${indent}Errors:\n`;
  summary += `${indent}  Rate: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%\n`;
  summary += `${indent}  Failed Requests: ${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%\n\n`;
  
  // Virtual Users
  summary += `${indent}Virtual Users:\n`;
  summary += `${indent}  Max: ${data.metrics.vus_max.values.max}\n\n`;
  
  // Thresholds
  summary += `${indent}Thresholds:\n`;
  for (const [name, threshold] of Object.entries(data.thresholds)) {
    const passed = threshold.ok ? '✓' : '✗';
    summary += `${indent}  ${passed} ${name}\n`;
  }
  
  return summary;
}