# Murphy System Runtime v2 - Quick User Guide

## 🚀 Quick Start

### Access the Live Demo
**URL:** https://9090-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai/murphy_complete_ui.html

### System Status
- ✅ Backend: Running on port 6666
- ✅ Frontend: Running on port 9090
- ✅ DomainEngine: Fully integrated
- ✅ All naming conventions fixed
- ✅ 9 Groq API keys active (load balancing)

---

## 📋 What's New in v2

### Naming Convention Fixes
The system now uses clear, unambiguous naming to prevent errors:

| Old Name | New Name | Purpose |
|----------|----------|---------|
| `domain_depth` | `expertise_depth` | Level of expertise (0-100) |
| `domain` | `domain_name` | Domain identifier (string) |
| N/A | `domain_object` | Full Domain object with all info |

### Key Improvements
1. **No Name Collisions** - Clear distinction between strings and objects
2. **Full DomainEngine Integration** - Tasks and gates include complete domain information
3. **Better Error Messages** - Clear validation and error reporting
4. **Backward Compatible** - Old API calls still work

---

## 🎯 How to Use

### Step 1: Create a Document
1. Click "Create Document" in the Documents tab
2. Enter title and content
3. Click "Create"

**Example:**
```
Title: Smart Home Automation System
Content: Design and implement a comprehensive smart home automation 
system with voice control, energy monitoring, security integration, 
and mobile app interface. Budget: $50,000.
```

### Step 2: Magnify with Domain Expertise
1. Select the document
2. Click "🔍 Magnify" button
3. Select a domain (engineering, financial, legal, etc.)
4. System increases expertise_depth and adds domain knowledge

**What happens:**
- expertise_depth increases by +15
- Domain-specific information is added
- History tracks the magnification

### Step 3: Simplify (Optional)
1. Click "Simplify" button
2. System distills to essentials
3. expertise_depth decreases by -10

**When to use:**
- When you need to focus on core requirements
- To reduce complexity
- To clarify essentials

### Step 4: Solidify and Generate Tasks
1. Click "Solidify" button
2. System generates:
   - Master prompt (comprehensive requirements)
   - Domain-specific prompts (for each matched domain)
   - Swarm tasks (assigned to org chart roles)
   - Domain gates (validation checkpoints)

**What you get:**
- 5+ prompts (master + domain-specific)
- 4+ tasks (one per domain)
- 10+ gates (validation checkpoints)

### Step 5: Review Generated Artifacts

#### Prompts
- **Master Prompt:** Comprehensive requirements document
- **Domain Prompts:** Domain-specific requirements and tasks

#### Tasks
- Each task includes:
  - `task_id`: Unique identifier
  - `domain_name`: Domain identifier (e.g., "engineering")
  - `domain_object`: Full domain info with purpose, gates, constraints
  - `role`: Org chart role (e.g., "Chief Engineer")
  - `prompt`: Task description
  - `status`: assigned → executing → completed

#### Gates
- Each gate includes:
  - `gate_id`: Unique identifier
  - `name`: Gate name (e.g., "Technical Feasibility Gate")
  - `domain_name`: Domain identifier
  - `domain_object`: Full domain info
  - `severity`: 0.0-1.0 (higher = more critical)
  - `status`: active → passed → failed

---

## 🏗️ Available Domains

The system has 9 standard business domains:

### 1. Business Domain
- **Purpose:** Overarching business strategy and operations
- **Sub-domains:** Executive Strategy, Business Development, Market Analysis
- **Key Questions:** Business model, KPIs, competitive landscape, growth targets
- **Gates:** Business Viability, Market Validation, Financial Feasibility

### 2. Engineering Domain
- **Purpose:** Technical design, development, and implementation
- **Sub-domains:** Software Engineering, Mechanical Engineering, Electrical Engineering
- **Key Questions:** Technical requirements, technology stack, performance needs
- **Gates:** Technical Feasibility, Architecture Review, Security Review

### 3. Financial Domain
- **Purpose:** Financial planning, analysis, and management
- **Sub-domains:** Accounting, FP&A, Treasury Management, Tax Planning
- **Key Questions:** Budget, revenue projections, cash flow, ROI
- **Gates:** Budget Approval, ROI Validation, Financial Viability

### 4. Legal Domain
- **Purpose:** Legal compliance and risk management
- **Sub-domains:** Corporate Law, Regulatory Compliance, IP Law
- **Key Questions:** Legal requirements, compliance needs, IP protection
- **Gates:** Legal Review, Compliance Validation, Contract Review

### 5. Operations Domain
- **Purpose:** Operational processes and logistics
- **Sub-domains:** Process Management, Supply Chain, Quality Control
- **Key Questions:** Operational requirements, process flows, quality standards
- **Gates:** Operational Readiness, Process Validation, Quality Assurance

### 6. Marketing Domain
- **Purpose:** Marketing strategy and brand management
- **Sub-domains:** Brand Management, Digital Marketing, Market Research
- **Key Questions:** Brand strategy, target audience, marketing channels
- **Gates:** Brand Alignment, Market Readiness, Campaign Validation

### 7. HR Domain
- **Purpose:** Human resources and talent management
- **Sub-domains:** Recruitment, Training, Compensation, Employee Relations
- **Key Questions:** Staffing needs, skill requirements, culture
- **Gates:** Staffing Adequacy, Cultural Alignment, Compliance Check

### 8. Sales Domain
- **Purpose:** Sales strategy and revenue generation
- **Sub-domains:** Direct Sales, Channel Sales, Sales Operations
- **Key Questions:** Sales targets, pricing strategy, customer segments
- **Gates:** Sales Strategy Validation, Pricing Approval, Market Access

### 9. Product Domain
- **Purpose:** Product strategy and development
- **Sub-domains:** Product Management, UX Design, Product Roadmap
- **Key Questions:** Product vision, user needs, feature priorities
- **Gates:** Product Viability, UX Validation, Market Fit

---

## 🔧 API Endpoints

### Documents
- `POST /api/documents` - Create document
- `POST /api/documents/{id}/magnify` - Add domain expertise
- `POST /api/documents/{id}/simplify` - Simplify document
- `POST /api/documents/{id}/solidify` - Generate tasks and gates
- `GET /api/documents/{id}` - Get document details

### Domains
- `GET /api/domains` - Get all available domains
- `POST /api/analyze-domain` - Analyze request for domain coverage
- `POST /api/create-generative-domain` - Create new domain

### Tasks
- `GET /api/tasks` - Get all tasks
- `POST /api/tasks/{id}/execute` - Execute a task
- `GET /api/tasks/{id}` - Get task details

### Gates
- `GET /api/gates` - Get all gates
- `POST /api/gates/{id}/validate` - Validate a gate

---

## 📊 Understanding the Data

### Document Structure
```json
{
  "doc_id": "DOC-0",
  "title": "Document Title",
  "content": "Document content...",
  "state": "INITIAL",  // INITIAL → MAGNIFIED → SIMPLIFIED → SOLIDIFIED
  "confidence": 0.45,  // 0.0-1.0 confidence score
  "expertise_depth": 0,  // 0-100 level of expertise
  "history": [],  // Track all actions
  "created_at": "2026-01-20T19:00:00"
}
```

### Task Structure
```json
{
  "task_id": "TASK-0",
  "domain_name": "engineering",
  "domain_object": {
    "name": "Engineering Domain",
    "purpose": "Technical design...",
    "gates": ["Technical Feasibility Gate", ...],
    "constraints": ["Technical feasibility", ...]
  },
  "role": "Chief Engineer",
  "prompt": "Task description...",
  "status": "assigned",
  "created_at": "2026-01-20T19:00:00"
}
```

### Gate Structure
```json
{
  "gate_id": "GATE-0",
  "name": "Technical Feasibility Gate",
  "domain_name": "engineering",
  "domain_object": { /* full domain info */ },
  "severity": 0.9,
  "status": "active",
  "created_at": "2026-01-20T19:00:00"
}
```

---

## 🎨 UI Features

### Tabs
1. **Overview** - System status and metrics
2. **Documents** - Living document management
3. **Tasks** - Swarm task management
4. **Gates** - Domain gate validation
5. **Approvals** - Approval queue
6. **Terminal** - System logs and commands

### Controls
- **Create Document** - Start new project
- **🔍 Magnify** - Add domain expertise
- **Simplify** - Distill to essentials
- **Solidify** - Generate tasks and gates
- **Execute Task** - Run swarm task
- **Validate Gate** - Check gate requirements

### Real-time Updates
- Terminal shows all system operations
- Status indicators update in real-time
- Progress bars show task completion
- Confidence scores update automatically

---

## 💡 Tips and Best Practices

### Document Creation
- Use detailed content for better domain matching
- Include technical, financial, and business keywords
- Be specific about requirements and constraints

### Magnification
- Start with broader domains (business, engineering)
- Add specialized domains (financial, legal) as needed
- Monitor expertise_depth to avoid over-specialization

### Simplification
- Use when document becomes too complex
- Helps focus on core requirements
- Reduces expertise_depth by 10 points

### Solidification
- Only solidify when document is clear and complete
- System generates all necessary artifacts
- Review generated tasks and gates before execution

### Task Execution
- Tasks are assigned to org chart roles
- Each task includes domain-specific context
- Monitor task status in real-time

### Gate Validation
- Gates ensure quality and compliance
- Higher severity = more critical
- Must pass all gates before completion

---

## 🔍 Troubleshooting

### Common Issues

#### "Domain not found" error
**Solution:** Use one of the 9 standard domains: business, engineering, financial, legal, operations, marketing, hr, sales, product

#### No domains matched
**Solution:** Add more domain-specific keywords to your document content (e.g., "technical", "budget", "compliance")

#### Tasks not generating
**Solution:** Make sure document is solidified (state = "SOLIDIFIED")

#### Gates not appearing
**Solution:** Check that domains have gates defined in DomainEngine

---

## 📞 Support

### Documentation
- Complete Test Report: `TEST_REPORT.md`
- Naming Conventions: `NAMING_CONVENTIONS_FIXED.md`
- Update Summary: `UPDATE_SUMMARY_NAMING_FIXES.md`

### System Status
- Backend: http://localhost:6666
- Frontend: http://localhost:9090
- Public URL: https://9090-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai

---

## ✅ Test Results

All systems tested and validated:
- ✅ 52 unit tests passed (100%)
- ✅ 27 end-to-end workflow tests passed (100%)
- ✅ All naming conventions verified
- ✅ DomainEngine integration confirmed
- ✅ Backward compatibility maintained

**Ready for user review and testing!**

---

**Last Updated:** January 20, 2026  
**Version:** v2.0 - Naming Conventions Fixed  
**Status:** ✅ Production Ready