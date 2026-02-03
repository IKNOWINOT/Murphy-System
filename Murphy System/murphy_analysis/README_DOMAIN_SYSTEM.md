# Murphy System - Domain Classification & Generative Domain System

## Overview

The Murphy System now includes a comprehensive **Business Domain System** with **Generative Domain Capabilities** that intelligently classifies and handles any business request.

## Quick Start

### Using Standard Domains

```python
from domain_engine import DomainEngine

# Initialize engine
engine = DomainEngine()

# Analyze a request
request = "We need to build a new mobile app for our customers"
analysis = engine.analyze_request(request)

print(f"Coverage: {analysis['coverage']}")
print(f"Matched Domains: {analysis['matched_domains']}")
# Output: Coverage: 0.85
#         Matched Domains: {'product': 3.0, 'engineering': 2.5, 'marketing': 1.5}
```

### Creating Generative Domains

```python
# For novel requests
request = "Build an AI-powered sustainable supply chain"
analysis = engine.analyze_request(request)

if analysis['needs_generative']:
    # Select template
    template = engine.select_template(request, analysis)
    
    # Generate questions
    questions = engine.generate_questions(template, request)
    
    # Collect responses (from user)
    responses = {
        'technology_name': 'AI-Powered Supply Chain',
        'problem_solved': 'Optimize logistics while reducing carbon footprint',
        'sub_domains': 'AI/ML Operations, Sustainability Metrics, Supply Chain Optimization',
        # ... more responses
    }
    
    # Synthesize domain
    domain = engine.synthesize_domain(template, responses)
    
    # Validate and integrate
    is_valid, issues = engine.validate_domain(domain)
    if is_valid:
        engine.integrate_domain(domain)
        print(f"New domain created: {domain.name}")
```

## Standard Domains

The system includes 9 comprehensive business domains:

1. **Business Domain** - Strategy, growth, governance
2. **Engineering Domain** - Technical design and development
3. **Financial Domain** - Planning, analysis, management
4. **Legal Domain** - Compliance, risk, protection
5. **Operations Domain** - Execution and processes
6. **Marketing Domain** - Positioning and acquisition
7. **HR Domain** - Talent and organization
8. **Sales Domain** - Revenue and relationships
9. **Product Domain** - Strategy and development

Each domain includes:
- Purpose and sub-domains
- 8 key discovery questions
- Cross-domain impact mappings
- Domain-specific constraints
- Validation gates

## Generative Domain Templates

When a request doesn't fit existing domains (<70% coverage), the system uses one of 4 templates:

### 1. New Industry Vertical Template
For industry-specific requirements (Healthcare, Finance, Retail, etc.)

### 2. Hybrid Domain Template
For requests spanning multiple domains

### 3. Emerging Technology Template
For new technology adoption (AI, Blockchain, IoT, etc.)

### 4. Process Innovation Template
For novel approaches to business processes

## Cross-Domain Impact Analysis

The system automatically analyzes how domains affect each other:

```python
# Get cross-domain impact analysis
domains = ['engineering', 'product', 'marketing']
analysis = engine.get_cross_impact_analysis(domains)

print(analysis['high_impact_pairs'])
# Output: [
#   {'source': 'engineering', 'target': 'product', 'level': 'HIGH'},
#   {'source': 'product', 'target': 'marketing', 'level': 'HIGH'}
# ]
```

## API Integration

### Backend Endpoints

```python
# Get all domains
GET /api/domains

# Analyze request
POST /api/analyze-domain
{
  "request": "Build a mobile app"
}

# Create generative domain
POST /api/create-generative-domain
{
  "template_type": "technology",
  "responses": {...}
}

# Cross-impact analysis
POST /api/cross-impact-analysis
{
  "domains": ["engineering", "product"]
}
```

## Documentation

- **DOMAIN_SYSTEM_ARCHITECTURE.md** - Complete system design (5,000+ lines)
- **DOMAIN_SYSTEM_IMPLEMENTATION_SUMMARY.md** - Technical details and examples
- **domain_engine.py** - Source code with inline documentation

## Key Features

✅ **Automatic Classification** - Analyzes any request and matches to domains
✅ **Generative Domains** - Creates custom domains for novel requests
✅ **Cross-Impact Analysis** - Maps dependencies between domains
✅ **Question Framework** - 7-phase discovery process
✅ **Template System** - 4 templates for different scenarios
✅ **Knowledge Growth** - System learns from each new domain
✅ **Full Integration** - Works seamlessly with Murphy System

## Example: AI-Powered Sustainable Supply Chain

**Request:** "Build an AI-powered sustainable supply chain system"

**Process:**
1. System detects 45% coverage (needs generative domain)
2. Selects Hybrid + Technology templates
3. Generates 8 targeted questions
4. User provides answers
5. System creates new domain with:
   - Sub-domains: AI/ML Ops, Sustainability Metrics, Supply Chain Optimization
   - Cross-impacts: Mapped to all 9 standard domains
   - Gates: Data Quality, Sustainability, AI Performance, Integration, Compliance
6. Domain integrated and available for future use

## Benefits

1. **No Blind Spots** - Every request gets proper classification
2. **Adaptive Learning** - System handles novel situations
3. **Systematic Approach** - Template-based consistency
4. **Knowledge Accumulation** - Grows smarter over time
5. **Complete Transparency** - Clear reasoning and impacts

## Next Steps

- Frontend UI for domain selection
- Interactive Q&A wizard
- Cross-impact visualization
- Domain browser
- Machine learning enhancements

---

**Status:** ✅ Production Ready
**Version:** January 20, 2026
**Location:** `src/domain_engine.py`
