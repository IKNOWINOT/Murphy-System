# Murphy Complete AI Agent System

## 🎯 What is Murphy?

Murphy is a complete AI Agent System with autonomous capabilities, multi-agent coordination, and comprehensive business automation features.

### ✅ Latest Features (Just Added!)
1. **Fixed `/librarian` command** - Now works correctly
2. **Event logging system** - Tracks all interactions with unique IDs
3. **Click-to-view-logs** - Click any message with 📋 to see detailed logs
4. **Beautiful log modal** - Shows complete request/response data

### 🚀 Core Features
- **LLM Manager** - Multi-provider AI with automatic key rotation
- **Librarian System** - Long-term memory and knowledge management
- **Artifact Systems** - Document and code generation/management
- **Shadow Agents** - Learn from your patterns and automate tasks
- **Cooperative Swarm** - Multi-agent coordination for complex tasks
- **Command System** - 61 ready-to-use commands
- **Business Module** - E-commerce and payment integration
- **Production Tools** - Deployment, SSL, and monitoring

## 📋 Prerequisites

- **Python 3.11 or 3.12** (NOT 3.13 - has compatibility issues)
- **pip** (Python package installer)
- **Groq API keys** (for LLM functionality)
- **Aristotle API key** (optional, for enhanced features)

## 🚀 Quick Start

### 1. Set Up API Keys

Edit `groq_keys.txt` and add your Groq API keys (one per line):
```
gsk_your_first_key_here
gsk_your_second_key_here
gsk_your_third_key_here
```

Edit `aristotle_key.txt` and add your Aristotle key:
```
your_aristotle_key_here
```

### 2. Install Dependencies

**Windows:**
```bash
pip install -r requirements.txt
```

**Linux/Mac:**
```bash
pip3 install -r requirements.txt
```

### 3. Start the Server

**Windows:**
```bash
python murphy_complete_integrated.py
```

**Linux/Mac:**
```bash
python3 murphy_complete_integrated.py
```

### 4. Access the UI

Open your browser and go to:
```
http://localhost:3002
```

## 🧪 Test the New Features

### Test 1: Librarian Command
```
/librarian What can Murphy do?
```
- Should work without errors
- Response shows 📋 indicator
- Click message to view detailed logs

### Test 2: View Event Logs
1. Send any command
2. Look for 📋 icon on response
3. Click the message
4. Modal shows:
   - Event ID and timestamp
   - Command executed
   - Full request data
   - Full response data
   - Any errors

### Test 3: System Status
```
/status
```
Shows all system components and their status

## 📁 Files Included

This package contains **ALL** files needed for a complete Murphy installation:
- Main server and UI (with all fixes)
- All 30+ Python modules
- Configuration templates
- Complete documentation

## 🔍 Troubleshooting

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :3002
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :3002
kill -9 <PID>
```

### Dependencies Won't Install
- Make sure you're using Python 3.11 or 3.12 (NOT 3.13)
- Upgrade pip: `python -m pip install --upgrade pip`
- Try installing packages individually

### Librarian Not Working
- Check API keys are set up correctly
- Check server logs for errors
- Test API: `curl -X POST http://localhost:3002/api/librarian/ask -H "Content-Type: application/json" -d '{"query":"test"}'`

## 📚 Available Commands

Use `/help` to see all 61 commands!

## 🎊 What's New

### UI Fixes
✅ Fixed `/librarian` command parameter  
✅ Added event logging system  
✅ Added click-to-view-logs  
✅ Created log viewing modal  
✅ Messages show 📋 when logs available  

See WHATS_NEW.md for complete details!

Enjoy Murphy! 🎉