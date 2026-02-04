# Phase 2 API Documentation

## Overview
Complete API documentation for Phase 2 Murphy Validation Enhancement components.

---

## 1. External Validation Service

### ExternalValidationService

**Purpose:** Orchestrates multiple external validators for comprehensive validation.

#### Methods

```python
async def validate(
    validation_type: ValidationType,
    target: str,
    context: Dict[str, Any]
) -> ValidationResult
```

**Parameters:**
- `validation_type`: Type of validation (CREDENTIAL, DATA_SOURCE, DOMAIN_EXPERT, etc.)
- `target`: Item to validate
- `context`: Additional context for validation

**Returns:** `ValidationResult` with status and confidence

**Example:**
```python
service = ExternalValidationService()
result = await service.validate(
    ValidationType.CREDENTIAL,
    "api_key_12345",
    {"credential_type": "api_key", "service_name": "github"}
)
print(f"Valid: {result.status == ValidationStatus.VALID}")
```

---

## 2. Credential Verification System

### CredentialVerificationSystem

**Purpose:** Complete credential management with verification, expiry tracking, and refresh.

#### Methods

```python
def add_credential(
    credential_type: CredentialType,
    service_name: str,
    credential_value: str,
    expires_at: Optional[datetime] = None
) -> str
```

**Parameters:**
- `credential_type`: Type of credential (API_KEY, OAUTH_TOKEN, JWT_TOKEN, etc.)
- `service_name`: Name of the service
- `credential_value`: The credential string
- `expires_at`: Optional expiration date

**Returns:** Credential ID

```python
async def verify_credential(credential_id: str) -> CredentialVerificationResult
```

**Returns:** Verification result with validity status

**Example:**
```python
system = CredentialVerificationSystem()

# Add credential
cred_id = system.add_credential(
    CredentialType.API_KEY,
    "github",
    "ghp_xxxxxxxxxxxx",
    expires_at=datetime.utcnow() + timedelta(days=90)
)

# Verify
result = await system.verify_credential(cred_id)
print(f"Valid: {result.is_valid}")
```

---

## 3. Historical Data Analysis System

### HistoricalDataAnalysisSystem

**Purpose:** Analyzes historical data to calculate UD (Uncertainty in Data).

#### Methods

```python
def record_data_point(
    source_name: str,
    source_type: DataSourceType,
    quality_metrics: Dict[DataQualityMetric, float],
    success_count: int = 0,
    error_count: int = 0
)
```

**Parameters:**
- `source_name`: Name of data source
- `source_type`: Type of source (DATABASE, API, FILE, etc.)
- `quality_metrics`: Dictionary of quality metrics
- `success_count`: Number of successful operations
- `error_count`: Number of failed operations

```python
def calculate_ud(source_name: str) -> float
```

**Returns:** UD score (0.0 to 1.0)

**Example:**
```python
system = HistoricalDataAnalysisSystem()

# Record data points
system.record_data_point(
    source_name="user_api",
    source_type=DataSourceType.API,
    quality_metrics={
        DataQualityMetric.ACCURACY: 0.95,
        DataQualityMetric.COMPLETENESS: 0.90
    },
    success_count=95,
    error_count=5
)

# Calculate UD
ud_score = system.calculate_ud("user_api")
print(f"UD Score: {ud_score}")
```

---

## 4. Domain Expertise System

### DomainExpertiseSystem

**Purpose:** Manages domain experts and calculates UA (Uncertainty in Assumptions).

#### Methods

```python
def register_expert(
    name: str,
    expertise_level: ExpertiseLevel,
    domains: List[str],
    domain_categories: List[DomainCategory],
    years_experience: int
) -> str
```

**Returns:** Expert ID

```python
def calculate_ua(
    assumption: str,
    domain: str,
    assumption_type: AssumptionType
) -> float
```

**Returns:** UA score (0.0 to 1.0)

**Example:**
```python
system = DomainExpertiseSystem()

# Register expert
expert_id = system.register_expert(
    name="Dr. Smith",
    expertise_level=ExpertiseLevel.EXPERT,
    domains=["software_development", "security"],
    domain_categories=[DomainCategory.TECHNOLOGY],
    years_experience=15
)

# Calculate UA
ua_score = system.calculate_ua(
    assumption="All user input is validated on the client side",
    domain="software_development",
    assumption_type=AssumptionType.TECHNICAL
)
print(f"UA Score: {ua_score}")
```

---

## 5. Information Quality System

### InformationQualitySystem

**Purpose:** Assesses information quality and calculates UI (Uncertainty in Information).

#### Methods

```python
def add_information(
    content: str,
    source: InformationSource,
    published_date: Optional[datetime] = None
) -> str
```

**Returns:** Information ID

```python
def calculate_ui(information_id: str) -> float
```

**Returns:** UI score (0.0 to 1.0)

**Example:**
```python
system = InformationQualitySystem()

# Add information
info_id = system.add_information(
    content="Python 3.11 introduces significant performance improvements...",
    source=InformationSource.OFFICIAL_DOCUMENTATION,
    published_date=datetime(2023, 10, 1)
)

# Calculate UI
ui_score = system.calculate_ui(info_id)
print(f"UI Score: {ui_score}")
```

---

## 6. Resource Availability System

### ResourceAvailabilitySystem

**Purpose:** Monitors resources and calculates UR (Uncertainty in Resources).

#### Methods

```python
def register_resource(
    name: str,
    resource_type: ResourceType,
    total_capacity: float,
    available_capacity: float,
    unit: ResourceUnit
) -> str
```

**Returns:** Resource ID

```python
async def check_availability(
    resource_id: str,
    required_amount: float
) -> ResourceAvailabilityCheck
```

**Returns:** Availability check result

**Example:**
```python
system = ResourceAvailabilitySystem()

# Register resource
resource_id = system.register_resource(
    name="Production CPU",
    resource_type=ResourceType.COMPUTE,
    total_capacity=100.0,
    available_capacity=75.0,
    unit=ResourceUnit.CORES
)

# Check availability
result = await system.check_availability(resource_id, 20.0)
print(f"Available: {result.is_available}")
```

---

## 7. Risk Database System

### RiskPatternStorageSystem

**Purpose:** Stores and retrieves risk patterns with advanced querying.

#### Methods

```python
def store_pattern(
    name: str,
    description: str,
    category: RiskCategory,
    severity: RiskSeverity,
    likelihood: RiskLikelihood,
    impact_score: float,
    keywords: List[str]
) -> str
```

**Returns:** Pattern ID

```python
def search_patterns(query: RiskPatternQuery) -> List[RiskPattern]
```

**Returns:** List of matching patterns

**Example:**
```python
system = RiskPatternStorageSystem()

# Store pattern
pattern_id = system.store_pattern(
    name="SQL Injection",
    description="Risk of SQL injection attacks",
    category=RiskCategory.SECURITY,
    severity=RiskSeverity.CRITICAL,
    likelihood=RiskLikelihood.MEDIUM,
    impact_score=9.0,
    keywords=["sql", "injection", "database"]
)

# Search patterns
query = RiskPatternQuery(
    category=RiskCategory.SECURITY,
    min_risk_score=5.0
)
patterns = system.search_patterns(query)
```

---

## 8. Risk Lookup System

### RiskLookupSystem

**Purpose:** Fast risk identification and analysis.

#### Methods

```python
def identify_risks(
    text: str,
    operation: str,
    domain: Optional[str] = None
) -> RiskIdentificationResult
```

**Returns:** Identified risks with scores

```python
def analyze_operation(
    operation: str,
    domain: Optional[str] = None
) -> Dict[str, Any]
```

**Returns:** Comprehensive risk analysis

**Example:**
```python
system = RiskLookupSystem(storage)

# Identify risks
result = system.identify_risks(
    text="DELETE FROM users WHERE id = ?",
    operation="database_query",
    domain="user_management"
)

print(f"Total Risk Score: {result.total_risk_score}")
print(f"Requires Review: {result.requires_human_review}")
```

---

## 9. Risk Scoring System

### RiskScoringSystem

**Purpose:** Calculates risk scores using multiple methods.

#### Methods

```python
def calculate_score(
    pattern: RiskPattern,
    method: ScoringMethod = ScoringMethod.COMPOSITE
) -> RiskScoreBreakdown
```

**Returns:** Detailed score breakdown

**Example:**
```python
system = RiskScoringSystem()

breakdown = system.calculate_score(
    pattern,
    method=ScoringMethod.COMPOSITE
)

print(f"Total Score: {breakdown.total_score}")
print(f"Confidence: {breakdown.confidence}")
```

---

## 10. Risk Mitigation System

### RiskMitigationSystem

**Purpose:** Generates mitigation recommendations and plans.

#### Methods

```python
def get_recommendations(
    pattern: RiskPattern
) -> List[MitigationRecommendation]
```

**Returns:** List of mitigation recommendations

```python
def generate_plan(
    patterns: List[RiskPattern]
) -> MitigationPlan
```

**Returns:** Complete mitigation plan

**Example:**
```python
system = RiskMitigationSystem()

# Get recommendations
recommendations = system.get_recommendations(pattern)

for rec in recommendations:
    print(f"Strategy: {rec.strategy.name}")
    print(f"Priority: {rec.priority}")
    print(f"Cost: ${rec.strategy.cost}")
```

---

## 11. Performance Optimization System

### PerformanceOptimizationSystem

**Purpose:** Provides caching, monitoring, and optimization.

#### Methods

```python
def get_cached(key: str) -> Optional[Any]
def set_cached(key: str, value: Any, ttl: Optional[int] = None)
```

**Caching operations**

```python
async def process_parallel(
    items: List[Any],
    processor: Callable
) -> List[Any]
```

**Parallel processing**

```python
def record_performance(name: str, value: float, unit: str = "ms")
def get_performance_stats() -> Dict[str, Any]
```

**Performance monitoring**

**Example:**
```python
system = PerformanceOptimizationSystem()

# Caching
system.set_cached("user_123", user_data, ttl=300)
cached_user = system.get_cached("user_123")

# Monitoring
system.record_performance("api_call", 150.0, "ms")
stats = system.get_performance_stats()
```

---

## Common Patterns

### Error Handling

All async methods should be wrapped in try-except:

```python
try:
    result = await system.verify_credential(cred_id)
except Exception as e:
    print(f"Verification failed: {e}")
```

### Context Management

Use context dictionaries for additional parameters:

```python
context = {
    "environment": "production",
    "user_role": "admin",
    "max_budget": 10000
}

result = system.analyze_operation(operation, context=context)
```

### Batch Operations

Process multiple items efficiently:

```python
items = [item1, item2, item3]
results = await system.process_parallel(items, processor_func)
```

---

## Integration Example

Complete workflow using multiple systems:

```python
# Initialize systems
historical = HistoricalDataAnalysisSystem()
domain = DomainExpertiseSystem()
info = InformationQualitySystem()
resource = ResourceAvailabilitySystem()
risk_storage = RiskPatternStorageSystem()
risk_lookup = RiskLookupSystem(risk_storage.storage)
performance = PerformanceOptimizationSystem()

# Record historical data
historical.record_data_point(
    "api_endpoint",
    DataSourceType.API,
    {DataQualityMetric.ACCURACY: 0.95},
    success_count=95,
    error_count=5
)

# Calculate uncertainties
ud = historical.calculate_ud("api_endpoint")
ua = domain.calculate_ua("assumption", "domain", AssumptionType.TECHNICAL)
ui = info.calculate_ui(info_id)

# Identify risks
risks = risk_lookup.identify_risks(
    "DELETE operation",
    "database_operation"
)

# Monitor performance
performance.record_performance("uncertainty_calc", 50.0)

print(f"UD: {ud}, UA: {ua}, UI: {ui}")
print(f"Risk Score: {risks.total_risk_score}")
```

---

## Best Practices

1. **Always use async/await** for I/O operations
2. **Cache frequently accessed data** using the performance system
3. **Monitor performance metrics** for all critical operations
4. **Validate inputs** before processing
5. **Handle errors gracefully** with proper error messages
6. **Use type hints** for better code clarity
7. **Document custom implementations** of abstract classes

---

*Last Updated: Phase 2 Complete*