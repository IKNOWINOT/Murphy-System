# Starting the Murphy Integrated System

## Quick Start Guide

### 1. Start the Backend Server

```bash
cd murphy_integrated
python murphy_complete_backend_extended.py
```

The server will start on **http://localhost:6666**

### 2. Open the Terminal UI

Open your browser and navigate to:
```
http://localhost:6666/terminal_integrated.html
```

Or open the file directly:
```bash
# On Linux/Mac
open terminal_integrated.html

# On Windows
start terminal_integrated.html
```

**The terminal UI is a command-line interface that connects to the Murphy backend.**

## Terminal Commands

The terminal UI provides a command-line interface to interact with Murphy System:

### System Commands
- `help` - Show all available commands
- `api` - Show API endpoints
- `status` - Show system status and components
- `clear` - Clear terminal output

### Task Submission
- `submit <JSON>` - Submit a task for execution
  - Example: `submit {"task_type":"analysis","description":"Analyze Q4 sales"}`
- `validate <JSON>` - Validate a task without executing
  - Example: `validate {"task_type":"general","description":"Test task"}`

### Learning & Corrections
- `correct <JSON>` - Submit a correction
  - Example: `correct {"task_id":"123","correction_type":"output_error","original_output":"wrong","corrected_output":"right","explanation":"Fixed"}`
- `patterns` - Show extracted correction patterns
- `stats` - Show correction statistics

### Human-in-the-Loop
- `interventions` - Show pending intervention requests

### Quick Command Buttons
The terminal includes quick-access buttons for common commands:
- Help, API Endpoints, System Status
- Submit Task, Validate Task, Submit Correction
- Statistics, Clear

## API Endpoints

### Form Endpoints
- `POST /api/forms/plan-upload` - Upload pre-existing plan
- `POST /api/forms/plan-generation` - Generate plan from description
- `POST /api/forms/task-execution` - Execute task with Murphy validation
- `POST /api/forms/validation` - Validate task without executing
- `POST /api/forms/correction` - Submit correction
- `GET /api/forms/submission/<id>` - Get submission status

### Correction Endpoints
- `GET /api/corrections/patterns` - Get extracted patterns
- `GET /api/corrections/statistics` - Get correction statistics
- `GET /api/corrections/training-data` - Get shadow agent training data

### HITL Endpoints
- `GET /api/hitl/interventions/pending` - Get pending interventions
- `POST /api/hitl/interventions/<id>/respond` - Respond to intervention
- `GET /api/hitl/statistics` - Get HITL statistics

### System Info
- `GET /api/system/info` - Get integrated system information

## Example Usage

### 1. Submit a Task

**Via Terminal:**
1. Open terminal_integrated.html
2. Type: `submit {"task_type":"analysis","description":"Analyze Q4 sales","parameters":{"quarter":"Q4"}}`
3. Press Enter
4. View confidence scores and results

**Via API:**
```bash
curl -X POST http://localhost:6666/api/forms/task-execution \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "analysis",
    "description": "Analyze sales data for Q4",
    "parameters": {"quarter": "Q4", "year": 2024}
  }'
```

### 2. Validate a Task

**Via Terminal:**
1. Type: `validate {"task_type":"general","description":"Process customer data"}`
2. Press Enter
3. View confidence scores and approval decision

**Via API:**
```bash
curl -X POST http://localhost:6666/api/forms/validation \
  -H "Content-Type: application/json" \
  -d '{
    "task_data": {
      "task_type": "general",
      "description": "Process customer data"
    }
  }'
```

### 3. Submit a Correction

**Via Terminal:**
1. Type: `correct {"task_id":"task_12345","correction_type":"output_error","original_output":"Wrong result","corrected_output":"Correct result","explanation":"Fixed calculation error"}`
2. Press Enter
3. View confirmation and patterns extracted

**Via API:**
```bash
curl -X POST http://localhost:6666/api/forms/correction \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task_12345",
    "correction_type": "output_error",
    "original_output": "Wrong result",
    "corrected_output": "Correct result",
    "explanation": "Fixed calculation error"
  }'
```

### 4. View Statistics

**Via Terminal:**
1. Type: `stats`
2. Press Enter
3. View correction statistics

**Via API:**
```bash
# Correction statistics
curl http://localhost:6666/api/corrections/statistics

# HITL statistics
curl http://localhost:6666/api/hitl/statistics

# System info
curl http://localhost:6666/api/system/info
```

## Troubleshooting

### Server won't start
- Check if port 6666 is already in use
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check Python version (3.11+ recommended)

### Terminal shows "OFFLINE"
- Verify server is running on http://localhost:6666
- Check browser console for connection errors
- Try: `curl http://localhost:6666/api/system/info`

### Import errors
- Run the import test: `python tests/test_basic_imports.py`
- All 5 tests should pass
- If not, check that you're in the murphy_integrated directory

### Commands not working
- Make sure terminal shows "ONLINE" status badge
- Check that backend is running: `python murphy_complete_backend_extended.py`
- Verify JSON syntax in commands (use double quotes)

## Next Steps

1. **Test the system** - Try submitting tasks and corrections
2. **Monitor performance** - Check the monitoring tab regularly
3. **Review corrections** - See what Murphy is learning
4. **Integrate with existing workflows** - Use the API endpoints

## Support

For issues or questions:
1. Check the integration documentation in the docs/ folder
2. Review PHASE_3_COMPLETION_REPORT.md for import fixes
3. See INTEGRATION_COMPLETE_SUMMARY.md for architecture details