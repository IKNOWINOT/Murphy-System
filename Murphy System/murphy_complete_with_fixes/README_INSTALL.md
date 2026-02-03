# Murphy System - Installation Guide

## Quick Start

### Linux/Mac:
```bash
chmod +x install.sh
./install.sh
```

### Windows:
```cmd
install.bat
```

---

## Manual Installation

### 1. Prerequisites
- **Python 3.8+** (3.11 recommended)
- **pip** (Python package manager)
- **Internet connection** (for API calls)

### 2. Install Dependencies

#### Option A: Using requirements.txt
```bash
pip install -r requirements.txt
```

#### Option B: Manual installation
```bash
pip install flask==3.0.0 flask-cors==4.0.0 flask-socketio==5.3.5
pip install groq==0.4.1 requests==2.31.0 psutil==5.9.6 pydantic==2.5.0
```

### 3. Setup API Keys

Create `groq_keys.txt` and add your Groq API keys (one per line):
```
gsk_your_key_here_1
gsk_your_key_here_2
```

Get free keys at: https://console.groq.com/keys

### 4. Run Murphy

```bash
python3 murphy_complete_integrated.py
```

### 5. Access Murphy

- **Dashboard:** http://localhost:3002
- **API Status:** http://localhost:3002/api/status
- **Health Check:** http://localhost:3002/api/monitoring/health

---

## System Requirements

### Minimum:
- CPU: 2 cores
- RAM: 2 GB
- Disk: 5 GB free
- Python: 3.8+

### Recommended:
- CPU: 4+ cores
- RAM: 4+ GB
- Disk: 10 GB free
- Python: 3.11

### Current Usage:
- Murphy process: ~3 MB RAM (idle)
- Very lightweight!

---

## File Structure

```
murphy/
├── murphy_complete_integrated.py  # Main server
├── groq_keys.txt                  # Your API keys
├── requirements.txt               # Python dependencies
├── install.sh                     # Linux/Mac installer
├── install.bat                    # Windows installer
├── start_murphy.sh               # Start script (Linux/Mac)
├── start_murphy.bat              # Start script (Windows)
├── stop_murphy.sh                # Stop script (Linux/Mac)
├── stop_murphy.bat               # Stop script (Windows)
├── real_test.py                  # Test suite
└── *_system.py                   # System modules
```

---

## Testing

Run the test suite:
```bash
python3 real_test.py
```

Expected output: **5/5 tests passing**

---

## Troubleshooting

### Port 3002 already in use
```bash
# Linux/Mac
lsof -ti:3002 | xargs kill -9

# Windows
netstat -ano | findstr :3002
taskkill /PID <PID> /F
```

### Missing dependencies
```bash
pip install -r requirements.txt --upgrade
```

### API key errors
- Check `groq_keys.txt` has valid keys
- Get free keys at: https://console.groq.com/keys
- Each key should be on a new line

### Import errors
Make sure all `*_system.py` files are in the same directory as `murphy_complete_integrated.py`

---

## Configuration

Edit `.env` file (created by installer):
```env
FLASK_ENV=development
FLASK_DEBUG=False
SECRET_KEY=your-secret-key-change-this
DATABASE_URL=sqlite:///murphy.db
PORT=3002
HOST=0.0.0.0
```

---

## What's Included

### 21 Operational Systems:
1. LLM (16 Groq keys + Aristotle)
2. Librarian
3. Monitoring
4. Artifacts
5. Shadow Agents
6. Cooperative Swarm
7. Commands (61 total)
8. Learning Engine
9. Workflow Orchestrator
10. Database
11. Business Automation
12. Production Readiness
13. Payment Verification
14. Artifact Download
15. Scheduled Automation
16. Librarian Integration
17. Agent Communication
18. Generative Gates
19. Enhanced Gates
20. Dynamic Projection Gates
21. Autonomous Business Development

### 82+ API Endpoints
- System management
- LLM generation
- Librarian queries
- Workflow orchestration
- Business automation
- And much more...

---

## Support

For issues or questions:
1. Check the logs: `murphy_server.log`
2. Run tests: `python3 real_test.py`
3. Check system status: `curl http://localhost:3002/api/status`

---

## License

Murphy System is licensed under the Apache License 2.0.

See the [LICENSE](LICENSE) file for details.

Copyright 2026 Murphy System Contributors

---

**Happy Automating! 🚀**