# Murphy System - Demo Guide

Complete guide for demonstrating Murphy System 1.0 capabilities.

## Quick Start

### From Visual Studio Code

1. **Open Murphy System** in VS Code
2. **Press F5** (or Run → Start Debugging)
3. **Select a demo** from the dropdown:
   - Murphy: Quick Demo (2 min) - Basic features
   - Murphy: Full Demo (10 min) - All features
   - Murphy: API Demo - REST endpoints
   - Murphy: Integration Demo - GitHub integration
   - Murphy: Business Automation Demo - 5 engines
   - Murphy: AI/ML Demo - Advanced features

### From Command Line

```bash
cd "Murphy System/murphy_integrated"

# Quick 2-minute demo
python demo_murphy.py --demo quick

# Full 10-minute demo
python demo_murphy.py --demo full

# Specific demos
python demo_murphy.py --demo api          # API endpoints
python demo_murphy.py --demo integration  # Integration engine
python demo_murphy.py --demo business     # Business automation
python demo_murphy.py --demo aiml         # AI/ML features

# Everything!
python demo_murphy.py --demo all
```

## Available Demos

### 1. Quick Demo (2 minutes)

**What it shows:**
- Health check & system status
- Task execution
- Basic API functionality

**Perfect for:**
- First-time viewers
- Quick capability check
- Status verification

**Command:**
```bash
python demo_murphy.py --demo quick
```

### 2. Full Demo (10 minutes)

**What it shows:**
- Everything in Quick Demo
- Integration Engine (SwissKiss)
- Business Automation (5 engines)
- Murphy Validation (G/D/H + 5D)
- HITL approval system

**Perfect for:**
- Comprehensive overview
- Technical presentations
- Investor demos

**Command:**
```bash
python demo_murphy.py --demo full
```

### 3. API Demo

**What it shows:**
- All REST API endpoints
- Request/response examples
- Status codes
- JSON payloads

**Perfect for:**
- Developers
- Integration partners
- API consumers

**Command:**
```bash
python demo_murphy.py --demo api
```

**Endpoints demonstrated:**
- `GET /api/health` - Health check
- `GET /api/status` - System status
- `GET /api/info` - System information
- `GET /api/modules` - List modules
- `POST /api/execute` - Execute task
- `POST /api/integrations/add` - Add integration
- `POST /api/automation/{engine}/{action}` - Run automation

### 4. Integration Demo

**What it shows:**
- SwissKiss auto-integration
- GitHub repository ingestion
- Capability extraction
- Module generation
- HITL approval workflow

**Perfect for:**
- DevOps teams
- CI/CD integration
- Automation engineers

**Command:**
```bash
python demo_murphy.py --demo integration
```

### 5. Business Automation Demo

**What it shows:**
- Sales Engine (lead gen, qualification, outreach)
- Marketing Engine (content, social media, SEO)
- R&D Engine (bug fixes, testing, deployment)
- Business Management (finance, support, docs)
- Production Management (releases, QA, deployment)

**Perfect for:**
- Business stakeholders
- C-suite executives
- Operations teams

**Command:**
```bash
python demo_murphy.py --demo business
```

### 6. AI/ML Demo

**What it shows:**
- Murphy Validation (G/D/H formula)
- 5D Uncertainty Assessment
- Shadow Agent Learning
- Swarm Knowledge Pipeline
- Pattern recognition
- Self-improvement

**Perfect for:**
- AI researchers
- ML engineers
- Technical deep dives

**Command:**
```bash
python demo_murphy.py --demo aiml
```

## VS Code Integration

### Debug Configurations

Press **F5** to access these configurations:

1. **Murphy: Quick Demo (2 min)** - Fast overview
2. **Murphy: Full Demo (10 min)** - Complete showcase
3. **Murphy: API Demo** - REST endpoints
4. **Murphy: Integration Demo** - SwissKiss integration
5. **Murphy: Business Automation Demo** - 5 engines
6. **Murphy: AI/ML Demo** - Advanced AI features
7. **Murphy: Start Server (Debug)** - Run with debugging
8. **Murphy: Run Tests** - Execute test suite

### Tasks

Press **Ctrl+Shift+P** → "Tasks: Run Task" to access:

- **Murphy: Start Server** - Start Murphy runtime
- **Murphy: Stop Server** - Stop Murphy runtime
- **Murphy: Install Dependencies** - Install requirements
- **Murphy: Run Quick Demo** - 2-minute demo
- **Murphy: Run Full Demo** - 10-minute demo
- **Murphy: Health Check** - Check server health
- **Murphy: View API Docs** - Open API documentation
- **Murphy: Run Tests** - Run test suite

## Manual Testing

### Start Murphy Server

```bash
cd "Murphy System/murphy_integrated"
./start.sh
```

Server runs on: `http://localhost:6666`

### Test Endpoints Manually

```bash
# Health check
curl http://localhost:6666/api/health

# System status
curl http://localhost:6666/api/status

# System info
curl http://localhost:6666/api/info

# Execute task
curl -X POST http://localhost:6666/api/execute \
  -H "Content-Type: application/json" \
  -d '{"task_type":"test","description":"Demo task"}'

# Add integration
curl -X POST http://localhost:6666/api/integrations/add \
  -H "Content-Type: application/json" \
  -d '{"repository_url":"https://github.com/example/repo","integration_type":"github"}'
```

### View API Documentation

Open in browser: `http://localhost:6666/docs`

Interactive Swagger UI with all endpoints documented.

## Demo Scenarios

### Scenario 1: First-Time Demo

**Audience:** Someone seeing Murphy for the first time
**Duration:** 5 minutes
**Steps:**
1. Run Quick Demo: `python demo_murphy.py --demo quick`
2. Show API docs: Open `http://localhost:6666/docs`
3. Execute one live API call
4. Explain key innovations

### Scenario 2: Technical Deep Dive

**Audience:** Developers, engineers
**Duration:** 15 minutes
**Steps:**
1. Run Full Demo: `python demo_murphy.py --demo full`
2. Show code: Open key files in VS Code
3. Run API Demo: `python demo_murphy.py --demo api`
4. Show integration: `python demo_murphy.py --demo integration`
5. Q&A with live API testing

### Scenario 3: Business Presentation

**Audience:** C-suite, investors, business stakeholders
**Duration:** 10 minutes
**Steps:**
1. Run Full Demo: `python demo_murphy.py --demo full`
2. Focus on business automation section
3. Show ROI potential (5 automated engines)
4. Demonstrate self-improvement capability
5. Discuss go-to-market strategy

### Scenario 4: AI/ML Showcase

**Audience:** AI researchers, ML engineers
**Duration:** 20 minutes
**Steps:**
1. Run AI/ML Demo: `python demo_murphy.py --demo aiml`
2. Deep dive into Murphy Validation formula
3. Explain 5D uncertainty assessment
4. Show Shadow Agent learning
5. Demonstrate swarm intelligence
6. Live experimentation

## Troubleshooting

### Server Not Starting

```bash
# Check if port 6666 is available
lsof -i :6666

# Kill existing process
pkill -f murphy_system_1.0_runtime.py

# Restart
./start.sh
```

### Import Errors

```bash
# Install dependencies
pip install -r requirements_murphy_1.0.txt

# Verify installation
python -c "import fastapi, pydantic; print('OK')"
```

### Demo Script Errors

```bash
# Run with verbose output
python demo_murphy.py --demo quick 2>&1 | tee demo.log

# Check server is running
curl http://localhost:6666/api/health
```

## Tips for Great Demos

### Before the Demo

1. **Test everything** - Run the demo once before showing
2. **Start the server** - Ensure Murphy is running
3. **Check dependencies** - All packages installed
4. **Prepare questions** - Anticipate audience questions
5. **Have backup** - Screenshots if live demo fails

### During the Demo

1. **Start simple** - Begin with Quick Demo
2. **Build complexity** - Progress to advanced features
3. **Show, don't tell** - Let Murphy demonstrate itself
4. **Pause for questions** - Engage your audience
5. **Have fun!** - Murphy is impressive, enjoy showing it

### After the Demo

1. **Share links** - API docs, GitHub, documentation
2. **Provide access** - Let them try it themselves
3. **Follow up** - Answer questions via email
4. **Gather feedback** - Improve demos based on input

## Advanced Usage

### Custom Demo Script

Create your own demo by importing the MurphyDemo class:

```python
from demo_murphy import MurphyDemo

demo = MurphyDemo()

# Custom demo sequence
demo.print_header("MY CUSTOM DEMO")
demo.check_server()
demo.demo_quick()
# Add your custom tests here
```

### Recording Demos

```bash
# Install asciinema for terminal recording
pip install asciinema

# Record demo
asciinema rec murphy_demo.cast -c "python demo_murphy.py --demo full"

# Play recording
asciinema play murphy_demo.cast
```

### Automated Testing

```bash
# Run demos as tests
python demo_murphy.py --demo quick --no-start > /dev/null && echo "PASS" || echo "FAIL"
```

## Resources

- **API Documentation**: http://localhost:6666/docs
- **User Guide**: MURPHY_NOW_WORKING.md
- **Architecture**: MURPHY_V3_ARCHITECTURE.md
- **Quick Start**: MURPHY_1.0_QUICK_START.md
- **Full Docs**: FINAL_DOCUMENTATION_INDEX.md

## Support

For demo support or questions:
1. Check MURPHY_NOW_WORKING.md
2. View API docs at /docs endpoint
3. Review example demos in examples/ directory
4. Test with curl commands manually

---

**Happy Demoing! 🚀**

Murphy System 1.0 - The Future of AI Automation
