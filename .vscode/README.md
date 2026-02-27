# Murphy System - Visual Studio Code Setup

## Quick Start for VS Code Users

### 1. Open in VS Code

```bash
code "Murphy System"
```

### 2. Install Python Extension

Install the official Python extension from Microsoft if you haven't already.

### 3. Run Demos

**Press F5** and select from:

- 🚀 **Murphy: Quick Demo (2 min)** - Fast overview
- 🌟 **Murphy: Full Demo (10 min)** - Complete showcase
- 🔌 **Murphy: API Demo** - REST endpoints
- 🔗 **Murphy: Integration Demo** - SwissKiss integration
- 💼 **Murphy: Business Automation Demo** - 5 engines
- 🤖 **Murphy: AI/ML Demo** - Advanced AI features

### 4. Use Tasks

**Ctrl+Shift+P** → "Tasks: Run Task" → Select:

- **Murphy: Start Server** - Start Murphy
- **Murphy: Run Quick Demo** - 2-minute demo
- **Murphy: Health Check** - Test server
- **Murphy: View API Docs** - Open documentation

## What's Configured

### Debug Configurations (.vscode/launch.json)

8 pre-configured debug/launch configurations for all demo types plus server debugging.

### Tasks (.vscode/tasks.json)

8 pre-configured tasks for common Murphy operations.

### Demo Script (demo_murphy.py)

Comprehensive demonstration system with 6 demo types:
- Quick (2 min)
- Full (10 min)
- API endpoints
- Integration engine
- Business automation
- AI/ML features

## Files

- **/.vscode/launch.json** - Debug configurations
- **/.vscode/tasks.json** - Task definitions
- **/murphy_integrated/demo_murphy.py** - Demo orchestrator
- **/murphy_integrated/DEMO_GUIDE.md** - Complete demo guide
- **/murphy_integrated/start.sh** - Server startup script

## Usage

### Method 1: Debug Panel (F5)

1. Click Debug icon (▶️ with bug) in sidebar
2. Select demo from dropdown at top
3. Press green play button (or F5)
4. Watch demo in integrated terminal

### Method 2: Command Palette

1. **Ctrl+Shift+P** (Cmd+Shift+P on Mac)
2. Type "Tasks: Run Task"
3. Select Murphy task
4. Watch output

### Method 3: Terminal

1. **Ctrl+`** to open integrated terminal
2. `cd "Murphy System/murphy_integrated"`
3. `python demo_murphy.py --demo quick`

## Features

### Automatic Server Management

The demo script automatically:
- Checks if Murphy is running
- Starts server if needed
- Waits for server to be ready
- Runs demo tests
- Shows results with beautiful formatting

### Visual Output

All demos include:
- ✅ Success indicators
- ⚠️ Warning messages
- ❌ Error messages
- 📊 Formatted JSON output
- Progress indicators
- Section headers

### Error Handling

Graceful handling of:
- Server not running
- Network errors
- API failures
- Missing dependencies

## Tips

### First Time Setup

```bash
# Install dependencies
cd "Murphy System/murphy_integrated"
pip install -r requirements_murphy_1.0.txt
```

### Keep Server Running

For fastest demo experience, keep Murphy running in a separate terminal:

```bash
cd "Murphy System/murphy_integrated"
./start.sh
```

Then run demos with `--no-start`:

```bash
python demo_murphy.py --demo quick --no-start
```

### Multiple Demos

Run all demos in sequence:

```bash
python demo_murphy.py --demo all
```

## Troubleshooting

### Python Not Found

Install Python 3.11+ and ensure it's in PATH.

### Import Errors

```bash
pip install -r requirements_murphy_1.0.txt
```

### Server Won't Start

Check if port 8000 is available:

```bash
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows
```

### Demo Script Errors

Run with verbose output:

```bash
python demo_murphy.py --demo quick 2>&1 | tee demo.log
```

## Documentation

- **DEMO_GUIDE.md** - Complete demo documentation
- **MURPHY_NOW_WORKING.md** - User guide
- **API Docs** - http://localhost:8000/docs

## Support

1. Check DEMO_GUIDE.md for detailed instructions
2. View API documentation at /docs endpoint
3. Review examples in examples/ directory
4. Test manually with curl commands

---

**Press F5 to start!** 🚀
