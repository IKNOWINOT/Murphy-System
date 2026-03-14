# API Examples

## Overview

This document provides comprehensive examples for using the Murphy System Runtime API. Examples cover common use cases, best practices, and implementation patterns.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Metrics](#metrics)
4. [Confidence Engine](#confidence-engine)
5. [Org Chart Operations](#org-chart-operations)
6. [Telemetry](#telemetry)
7. [Knowledge Management](#knowledge-management)
8. [Advanced Examples](#advanced-examples)

---

## Getting Started

### Basic Setup

```python
from src.system_integrator import SystemIntegrator

# Initialize the integrator
integrator = SystemIntegrator()

# Check system status
status = integrator.get_system_status()
print(f"System Status: {status}")
```

### Python Client Example

```python
from src.system_integrator import SystemIntegrator
import requests

class MurphyClient:
    """Simple client for Murphy System Runtime API"""
    
    def __init__(self, api_key, base_url="http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def request(self, method, endpoint, data=None):
        """Make an API request"""
        url = f"{self.base_url}{endpoint}"
        response = requests.request(
            method,
            url,
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()

# Usage
client = MurphyClient(api_key="sk-murphy-abc123...")
status = client.request("GET", "/v1/status")
print(status)
```

---

## Authentication

### Generate API Key

```python
from src.system_integrator import SystemIntegrator

integrator = SystemIntegrator()

# Generate new API key
api_key = integrator.auth.generate_api_key(
    user_id="user123",
    description="Production API key",
    scopes=["read", "write", "metrics"]
)

print(f"API Key: {api_key}")
```

### Validate API Key

```python
# Validate API key
validation = integrator.auth.validate_api_key(api_key)

if validation["valid"]:
    print(f"User: {validation['user_id']}")
    print(f"Scopes: {validation['scopes']}")
    print(f"Expires: {validation['expires']}")
else:
    print("Invalid API key")
```

### Refresh JWT Token

```python
# Generate initial JWT token
token = integrator.auth.generate_jwt({
    "user_id": "user123",
    "scopes": ["read", "write"]
})

# Use token until near expiration
# Refresh token
new_token = integrator.auth.refresh_token(token)
print(f"New Token: {new_token}")
```

---

## Metrics

### Collect a Metric

```python
from src.system_integrator import SystemIntegrator
from datetime import datetime

integrator = SystemIntegrator()

# Collect a simple metric
integrator.telemetry.collect_metric(
    metric_type="performance",
    metric_name="response_time",
    value=42.5,
    labels={"endpoint": "/api/query", "method": "GET"}
)

# Collect metric with timestamp
integrator.telemetry.collect_metric(
    metric_type="system",
    metric_name="cpu_usage",
    value=75.3,
    labels={"host": "server-1"},
    timestamp=datetime.utcnow().isoformat()
)
```

### Query Metrics

```python
# Get all performance metrics
metrics = integrator.telemetry.get_metrics(
    metric_type="performance"
)

for metric in metrics:
    print(f"{metric['metric_name']}: {metric['value']}")

# Get specific metric with time range
metrics = integrator.telemetry.get_metrics(
    metric_type="performance",
    metric_name="response_time",
    start_time="2024-01-01T00:00:00",
    end_time="2024-01-02T00:00:00",
    limit=100
)

# Get aggregated metrics
avg_response_time = integrator.telemetry.get_aggregated_metrics(
    metric_type="performance",
    metric_name="response_time",
    aggregation_type="avg",
    start_time="2024-01-01T00:00:00",
    end_time="2024-01-02T00:00:00"
)

print(f"Average Response Time: {avg_response_time}ms")
```

### Batch Metric Collection

```python
import time

# Collect metrics in batch
batch_metrics = [
    {
        "metric_type": "performance",
        "metric_name": "response_time",
        "value": 42.5,
        "labels": {"endpoint": "/api/query"}
    },
    {
        "metric_type": "performance",
        "metric_name": "throughput",
        "value": 1000,
        "labels": {"endpoint": "/api/query"}
    },
    {
        "metric_type": "system",
        "metric_name": "cpu_usage",
        "value": 75.3,
        "labels": {"host": "server-1"}
    }
]

# Collect all metrics
for metric in batch_metrics:
    integrator.telemetry.collect_metric(**metric)
```

---

## Confidence Engine

### Calculate Confidence

```python
from src.system_integrator import SystemIntegrator

integrator = SystemIntegrator()

# Calculate confidence with context
confidence = integrator.confidence.calculate_confidence(
    context="query_evaluation",
    query="What is the system architecture?",
    evidence=["System has 5 core components", "Modular design"]
)

print(f"Confidence Score: {confidence['score']}")
print(f"Confidence Level: {confidence['level']}")
print(f"Reasoning: {confidence['reasoning']}")
```

### Batch Confidence Calculation

```python
queries = [
    "How does the system scale?",
    "What are the security features?",
    "How to deploy the system?"
]

results = []
for query in queries:
    confidence = integrator.confidence.calculate_confidence(
        context="query_evaluation",
        query=query
    )
    results.append({
        "query": query,
        "confidence": confidence
    })

for result in results:
    print(f"Query: {result['query']}")
    print(f"Confidence: {result['confidence']['score']}")
```

### Confidence Thresholding

```python
# Set confidence threshold
threshold = 0.8

query = "What is the system architecture?"
confidence = integrator.confidence.calculate_confidence(
    context="query_evaluation",
    query=query
)

if confidence['score'] >= threshold:
    print("Proceeding with query - High confidence")
    # Execute query
else:
    print(f"Low confidence ({confidence['score']:.2f}) - Need more information")
    # Request clarification
```

---

## Org Chart Operations

### Create Organization Structure

```python
from src.org_compiler import OrgCompiler
from src.org_compiler.org_chart import OrgChartNode

# Create organization compiler
compiler = OrgCompiler()

# Define roles
roles = [
    {
        "role_id": "CEO",
        "role_name": "Chief Executive Officer",
        "reports_to": None,
        "department": "Executive",
        "authority_level": 10
    },
    {
        "role_id": "CTO",
        "role_name": "Chief Technology Officer",
        "reports_to": "CEO",
        "department": "Technology",
        "authority_level": 9
    },
    {
        "role_id": "CFO",
        "role_name": "Chief Financial Officer",
        "reports_to": "CEO",
        "department": "Finance",
        "authority_level": 9
    }
]

# Compile organization
org_chart = compiler.compile_roles(roles)

print(f"Organization compiled with {len(org_chart.nodes)} roles")
```

### Query Organization Structure

```python
# Get all roles at a specific level
executive_roles = compiler.query_roles(
    authority_level_min=8
)

print("Executive Roles:")
for role in executive_roles:
    print(f"  - {role['role_name']} (Level {role['authority_level']})")

# Get reporting chain
reporting_chain = compiler.get_reporting_chain("CFO")
print("Reporting Chain for CFO:")
for role in reporting_chain:
    print(f"  - {role['role_name']}")
```

### Enterprise-Scale Compilation

```python
from src.org_compiler.enterprise_compiler import EnterpriseRoleTemplateCompiler

# Use enterprise compiler for large organizations
enterprise_compiler = EnterpriseRoleTemplateCompiler()

# Compile 1000 roles efficiently
large_org = enterprise_compiler.compile_roles(
    roles=large_role_list,
    use_cache=True,
    parallel=True
)

print(f"Compiled {len(large_org['roles'])} roles in {large_org['compilation_time']}s")

# Query with pagination
page1 = enterprise_compiler.get_roles_paginated(page=1, page_size=100)
print(f"Page 1: {len(page1['roles'])} roles")
```

---

## Telemetry

### Collect Telemetry Data

```python
from src.system_integrator import SystemIntegrator
from datetime import datetime

integrator = SystemIntegrator()

# Collect system metrics
integrator.telemetry.collect_metric(
    metric_type="system",
    metric_name="cpu_usage",
    value=75.3,
    labels={"host": "server-1"}
)

integrator.telemetry.collect_metric(
    metric_type="system",
    metric_name="memory_usage",
    value=62.1,
    labels={"host": "server-1"}
)

# Collect performance metrics
start_time = time.time()
# ... perform operation ...
end_time = time.time()

integrator.telemetry.collect_metric(
    metric_type="performance",
    metric_name="operation_duration",
    value=(end_time - start_time) * 1000,  # milliseconds
    labels={"operation": "data_processing"}
)
```

### Analyze Telemetry Patterns

```python
# Analyze patterns in CPU usage
patterns = integrator.telemetry.analyze_patterns(
    metric_type="system",
    metric_name="cpu_usage",
    time_window=3600  # last hour
)

print("CPU Usage Patterns:")
for pattern in patterns:
    print(f"  - {pattern['type']}: {pattern['description']}")

# Detect anomalies
anomalies = integrator.telemetry.detect_anomalies(
    metric_type="system",
    metric_name="memory_usage",
    threshold=3.0  # 3 standard deviations
)

if anomalies:
    print("Anomalies Detected:")
    for anomaly in anomalies:
        print(f"  - {anomaly['timestamp']}: {anomaly['value']}")
```

### Predict Future Metrics

```python
# Predict CPU usage for next 5 minutes
predictions = integrator.telemetry.predict_metrics(
    metric_type="system",
    metric_name="cpu_usage",
    forecast_horizon=300  # 5 minutes
)

print("CPU Usage Predictions:")
for prediction in predictions:
    print(f"  - {prediction['timestamp']}: {prediction['value']:.2f}%")
```

---

## Knowledge Management

### Add Documents

```python
from src.system_integrator import SystemIntegrator

integrator = SystemIntegrator()

# Add a document
document = {
    "title": "System Architecture Guide",
    "content": """
    The Murphy System Runtime consists of:
    - Core system components
    - Confidence engine
    - Telemetry system
    - Knowledge management
    """,
    "author": "Corey Post InonI LLC"
}

metadata = {
    "category": "documentation",
    "tags": ["architecture", "system", "guide"],
    "version": "1.0",
    "language": "en"
}

doc_id = integrator.librarian_adapter.add_document(
    document,
    metadata=metadata
)

print(f"Document added with ID: {doc_id}")
```

### Search Documents

```python
# Simple search
results = integrator.librarian_adapter.search(
    query="system architecture",
    limit=5
)

print("Search Results:")
for result in results:
    print(f"  - {result['document']['title']} (Score: {result['score']:.2f})")
    print(f"    {result['document']['content'][:100]}...")

# Semantic search
results = integrator.librarian_adapter.semantic_search(
    query="How is the system organized?",
    filters={"category": "documentation"},
    limit=3
)

print("Semantic Search Results:")
for result in results:
    print(f"  - Relevance: {result['relevance']:.2f}")
    print(f"    {result['summary']}")
```

### Knowledge Graph Operations

```python
# Add relationship between documents
integrator.librarian_adapter.knowledge_base.add_relationship(
    doc1_id="doc1",
    doc2_id="doc2",
    relation_type="references",
    metadata={"strength": 0.9}
)

# Get related documents
related = integrator.librarian_adapter.knowledge_base.get_related_documents(
    document_id="doc1",
    max_depth=2
)

print("Related Documents:")
for doc in related:
    print(f"  - {doc['title']} (Distance: {doc['distance']})")
```

---

## Advanced Examples

### Complete Workflow Example

```python
from src.system_integrator import SystemIntegrator
import time

def process_query(query):
    """Complete query processing workflow"""
    integrator = SystemIntegrator()
    
    # Step 1: Calculate confidence
    start_time = time.time()
    confidence = integrator.confidence.calculate_confidence(
        context="query_evaluation",
        query=query
    )
    
    # Collect metrics
    integrator.telemetry.collect_metric(
        metric_type="performance",
        metric_name="confidence_calculation_time",
        value=(time.time() - start_time) * 1000,
        labels={"query": query[:50]}
    )
    
    # Step 2: Check confidence threshold
    if confidence['score'] < 0.8:
        # Search knowledge base for additional context
        results = integrator.librarian_adapter.search(query, limit=5)
        
        # Use results to improve confidence
        if results:
            confidence = integrator.confidence.calculate_confidence(
                context="query_evaluation",
                query=query,
                evidence=[r['document']['content'] for r in results]
            )
    
    # Step 3: Process query
    if confidence['score'] >= 0.8:
        # Execute query
        result = execute_query(query)
        
        # Collect metrics
        integrator.telemetry.collect_metric(
            metric_type="performance",
            metric_name="query_execution_time",
            value=(time.time() - start_time) * 1000,
            labels={"query": query[:50], "success": "true"}
        )
        
        return {
            "result": result,
            "confidence": confidence
        }
    else:
        # Request clarification
        integrator.telemetry.collect_metric(
            metric_type="business",
            metric_name="clarification_request",
            value=1,
            labels={"query": query[:50]}
        )
        
        return {
            "result": None,
            "confidence": confidence,
            "message": "Please provide more information"
        }

def execute_query(query):
    """Execute the query (placeholder)"""
    # Implement actual query execution logic
    return f"Result for: {query}"

# Usage
query = "How does the system handle large organizations?"
result = process_query(query)
print(result)
```

### Batch Processing Example

```python
from src.system_integrator import SystemIntegrator
import concurrent.futures

def process_batch(queries):
    """Process multiple queries in parallel"""
    integrator = SystemIntegrator()
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all queries
        future_to_query = {
            executor.submit(process_single_query, integrator, q): q
            for q in queries
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_query):
            query = future_to_query[future]
            try:
                result = future.result()
                results.append({"query": query, "result": result})
            except Exception as e:
                results.append({"query": query, "error": str(e)})
    
    return results

def process_single_query(integrator, query):
    """Process a single query"""
    start_time = time.time()
    
    confidence = integrator.confidence.calculate_confidence(
        context="query_evaluation",
        query=query
    )
    
    integrator.telemetry.collect_metric(
        metric_type="performance",
        metric_name="query_processing_time",
        value=(time.time() - start_time) * 1000
    )
    
    return confidence

# Usage
queries = [
    "What is the system architecture?",
    "How does it scale?",
    "What are the security features?"
]

results = process_batch(queries)
for result in results:
    print(f"Query: {result['query']}")
    print(f"Confidence: {result['result']['score']}")
```

### Error Handling Example

```python
from src.system_integrator import SystemIntegrator
import logging

def safe_query_processing(query):
    """Process query with comprehensive error handling"""
    integrator = SystemIntegrator()
    
    try:
        # Validate input
        if not query or len(query) > 1000:
            raise ValueError("Invalid query length")
        
        # Process query
        confidence = integrator.confidence.calculate_confidence(
            context="query_evaluation",
            query=query
        )
        
        # Collect metrics
        integrator.telemetry.collect_metric(
            metric_type="performance",
            metric_name="query_success",
            value=1,
            labels={"query": query[:50]}
        )
        
        return confidence
        
    except ValueError as e:
        # Input validation error
        logging.error(f"Validation error: {e}")
        integrator.telemetry.collect_metric(
            metric_type="error",
            metric_name="validation_error",
            value=1,
            labels={"error_type": "value_error"}
        )
        raise
        
    except Exception as e:
        # Unexpected error
        logging.error(f"Unexpected error: {e}", exc_info=True)
        integrator.telemetry.collect_metric(
            metric_type="error",
            metric_name="unexpected_error",
            value=1,
            labels={"error_type": type(e).__name__}
        )
        raise

# Usage
try:
    result = safe_query_processing("What is the system?")
    print(f"Confidence: {result['score']}")
except ValueError as e:
    print(f"Validation Error: {e}")
except Exception as e:
    print(f"Error: {e}")
```

---

## Time Tracking

### Start Timer

**Request:**
```http
POST /api/time/entries/start
Content-Type: application/json

{
  "user_id": "user-123",
  "project_id": "proj-456",
  "description": "Working on feature X"
}
```

**Response:**
```json
{
  "entry_id": "entry-789",
  "started_at": "2026-03-14T09:00:00Z",
  "status": "running"
}
```

### Stop Timer

**Request:**
```http
POST /api/time/entries/entry-789/stop
Content-Type: application/json
{}
```

**Response:**
```json
{
  "entry_id": "entry-789",
  "started_at": "2026-03-14T09:00:00Z",
  "stopped_at": "2026-03-14T10:30:00Z",
  "duration_minutes": 90,
  "status": "completed"
}
```

### Generate Invoice

**Request:**
```http
POST /api/time/billing/invoice
Content-Type: application/json

{
  "client_id": "client-001",
  "period_start": "2026-03-01",
  "period_end": "2026-03-14",
  "include_expenses": true
}
```

**Response:**
```json
{
  "invoice_id": "inv-2026-001",
  "client_id": "client-001",
  "period": "2026-03-01 to 2026-03-14",
  "total_hours": 120.5,
  "total_amount": 18075.00,
  "currency": "USD",
  "status": "draft"
}
```

### Get Billing Summary

**Request:**
```http
GET /api/time/billing/summary/client-001
```

**Response:**
```json
{
  "client_id": "client-001",
  "total_hours_ytd": 842.5,
  "total_billed_ytd": 126375.00,
  "outstanding_balance": 18075.00,
  "last_invoice_date": "2026-02-28",
  "currency": "USD"
}
```

### Dashboard Summary

**Request:**
```http
GET /api/time/dashboard/summary/team
```

**Response:**
```json
{
  "period": "current_week",
  "team_total_hours": 287.5,
  "active_timers": 4,
  "projects": [
    {"project_id": "proj-456", "hours": 120.0, "team_members": 3},
    {"project_id": "proj-789", "hours": 167.5, "team_members": 5}
  ]
}
```

---

## License

BSL 1.1 (converts to Apache 2.0 after four years) - See LICENSE.md for details.

## Support

For API questions or issues:
- Contact: corey.gfc@gmail.com
- Owner: Corey Post InonI LLC