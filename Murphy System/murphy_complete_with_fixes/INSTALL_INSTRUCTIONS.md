# Murphy Complete System - Installation Instructions

## 🎯 What's Included

This is the **COMPLETE Murphy AI Agent System** with all the latest UI fixes:

### ✅ Latest UI Fixes (Just Added!)
1. **Fixed `/librarian` command** - Now works correctly
2. **Event logging system** - Tracks all interactions
3. **Click-to-view-logs** - Click any message with 📋 to see detailed logs
4. **Log viewing modal** - Beautiful popup showing complete request/response data

### 🚀 Complete System Features
- **LLM Manager** - 9 Groq API keys with rotation
- **Librarian System** - Memory and knowledge management
- **Artifact Systems** - Document and code management
- **Shadow Agent System** - Autonomous learning and automation
- **Cooperative Swarm** - Multi-agent coordination
- **Command System** - 61 commands ready to use
- **Business Module** - E-commerce and payment systems
- **Production Module** - Deployment and SSL management
- **Database Module** - Data persistence
- **Workflow Module** - Task automation
- **Learning Module** - Pattern recognition

## 📋 Prerequisites

### Required
- Python 3.11 or 3.12 (NOT 3.13)
- pip (Python package installer)
- Windows, Linux, or macOS

### API Keys Needed
- Groq API keys (for LLM functionality)
- Aristotle API key (optional, for enhanced features)

## 🔧 Installation Steps

### 1. Extract the Package
```bash
# Extract the zip file to your desired location
unzip murphy_complete_with_fixes.zip
cd murphy_complete_with_fixes
```

### 2. Set Up API Keys

Create `groq_keys.txt` with your Groq API keys (one per line):
```
gsk_your_first_key_here
gsk_your_second_key_here
gsk_your_third_key_here
```

Create `aristotle_key.txt` with your Aristotle key:
```
your_aristotle_key_here
```

### 3. Install Dependencies

**On Windows:**
```bash
python -m pip install -r requirements.txt
```

**On Linux/Mac:**
```bash
pip3 install -r requirements.txt
```

### 4. Start the Server

**On Windows:**
```bash
python murphy_complete_integrated.py
```

**On Linux/Mac:**
```bash
python3 murphy_complete_integrated.py
```

### 5. Access the UI

Open your browser and go to:
```
http://localhost:3002
```

## 🧪 Testing the New Features

### Test 1: Librarian Command
```
/librarian What can Murphy do?
```
- Should work without errors
- Response should show 📋 indicator
- Click the message to view detailed logs

### Test 2: LLM Generation
```
Hello Murphy, tell me about yourself
```
- Should generate a response
- Response should have 📋 indicator
- Click to view logs

### Test 3: System Status
```
/status
```
- Should show all system components
- Should display current status

### Test 4: Log Viewing
1. Look for messages with 📋 icon
2. Click on any message with this icon
3. Modal should popup showing:
   - Event ID and timestamp
   - Command/query executed
   - Full request data
   - Full response data
   - Any errors

## 📁 Important Files

### Core System Files
- `murphy_complete_integrated.py` - Main server (WITH UI FIXES)
- `murphy_ui_final.html` - Web interface (WITH CLICK-TO-VIEW-LOGS)
- `requirements.txt` - Python dependencies

### Configuration Files
- `groq_keys.txt` - Your Groq API keys (you create this)
- `aristotle_key.txt` - Your Aristotle key (you create this)

### Module Files
- `llm_providers_enhanced.py` - LLM management
- `librarian_system.py` - Knowledge management
- `command_system.py` - Command processing
- `shadow_agent_system.py` - Autonomous agents
- `cooperative_swarm_system.py` - Multi-agent coordination
- And many more...

## 🔍 Troubleshooting

### Server Won't Start
**Problem:** Port 3002 already in use
**Solution:**
```bash
# On Windows
netstat -ano | findstr :3002
taskkill /PID <PID> /F

# On Linux/Mac
lsof -i :3002
kill -9 <PID>
```

### Librarian Not Working
**Problem:** Command fails or returns error
**Solution:**
1. Check server logs for errors
2. Verify API keys are set up correctly
3. Test the API directly:
```bash
curl -X POST http://localhost:3002/api/librarian/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}'
```

### Logs Not Showing
**Problem:** Click on message doesn't show logs
**Solution:**
1. Check browser console (F12) for errors
2. Verify the message has 📋 indicator
3. Make sure event_id is in the API response
4. Refresh the page and try again

### Dependencies Installation Failed
**Problem:** pip install fails
**Solution:**
1. Make sure you're using Python 3.11 or 3.12 (NOT 3.13)
2. Try upgrading pip: `python -m pip install --upgrade pip`
3. Install packages one by one if needed

### Python 3.13 Issues
**Problem:** pydantic or aiohttp installation fails
**Solution:**
- Downgrade to Python 3.12 or 3.11
- Python 3.13 requires Visual C++ Build Tools which can be problematic

## 🎯 What's New in This Version

### UI Fixes (Latest)
✅ Fixed `/librarian` command parameter mismatch  
✅ Added comprehensive event logging system  
✅ Added click-to-view-logs functionality  
✅ Created beautiful log viewing modal  
✅ Messages now show 📋 indicator when logs are available  

### Server Enhancements
✅ Event logging stores last 1000 events  
✅ New API endpoints: `/api/logs/<event_id>` and `/api/logs`  
✅ All LLM and librarian calls now logged  
✅ Each event gets unique ID for tracking  

## 📚 Documentation

All documentation is included in the package:
- `README.md` - Main documentation
- `UI_FIXES_COMPLETE.md` - Details of UI fixes
- `INSTALLATION.md` - This file
- `COMMANDS.md` - Command reference
- `API.md` - API documentation

## 🆘 Getting Help

If you encounter issues:
1. Check the server logs in the terminal
2. Check browser console (F12) for JavaScript errors
3. Verify all files were extracted correctly
4. Make sure API keys are set up correctly
5. Ensure you're using Python 3.11 or 3.12

## 🎊 Success Checklist

After installation, you should be able to:
- [ ] Access the UI at http://localhost:3002
- [ ] Use `/librarian` command successfully
- [ ] See 📋 indicator on messages
- [ ] Click messages to view detailed logs
- [ ] Generate LLM responses
- [ ] View system status with `/status`
- [ ] See all 61 commands with `/help`

## 🚀 Next Steps

Once installed:
1. Explore the UI and try different commands
2. Test the librarian with various questions
3. Click on messages to view logs
4. Create artifacts and documents
5. Set up automations with shadow agents
6. Create agent swarms for complex tasks

Enjoy your complete Murphy AI Agent System with all the latest fixes! 🎉