# Murphy System - Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Verify Backend is Running
The backend should already be running. Check with:
```bash
ps aux | grep murphy_backend_complete.py
```

If not running, start it:
```bash
python3 murphy_backend_complete.py
```

### Step 2: Access the Application
**Important**: Use `localhost:3002` NOT the exposed public URL.

Open your browser and navigate to:
```
http://localhost:3002
```

### Step 3: Test the System

#### Test 1: Check System Status
In the terminal, type:
```
/status
```

You should see:
- All 10 components marked as ✅ true
- Version: 3.0.0
- LLM: 9 Groq API keys
- Librarian: Fully operational

#### Test 2: Try Natural Language
Type in plain English:
```
hello
```

You should see:
- Intent classification
- Suggested commands
- Helpful response

#### Test 3: Create Something
Type:
```
I want to create a document about my business plan
```

You should see:
- Intent: CREATION
- Complete workflow with 4 steps
- Suggested commands

---

## 🎯 Key Features

### Natural Language Terminal
- Type anything in plain English
- System understands intent and suggests commands
- Provides step-by-step workflows

### 10 Integrated Systems
1. ✅ Monitoring
2. ✅ Artifacts
3. ✅ Shadow Agents
4. ✅ Cooperative Swarm
5. ✅ Command System
6. ✅ Authentication
7. ✅ Database
8. ✅ Modules
9. ✅ LLM (9 Groq keys)
10. ✅ Librarian (Natural Language)

### 6 UI Panels
- Organization Chart
- Agent Graph
- Process Flow
- Librarian Panel
- Plan Review Panel
- Document Editor Panel

---

## 💡 Tips

### 1. Use Natural Language
Instead of:
```
/document create contract
```

Try:
```
I need to create a contract
```

### 2. Ask for Help
Type:
```
/help
```

See all available commands grouped by module.

### 3. Check Status
Type:
```
/status
```

See system health and component status.

---

## 📚 Example Interactions

### Query Example
```
You: what can you help me with?
System: I can help you find information. Try: /status, /help
```

### Task Example
```
You: create a new document
System: Here's the workflow:
  1. /document create <type>
  2. /document magnify <domain>
  3. /document solidify
  4. /swarm execute CREATIVE
```

### Troubleshooting Example
```
You: something's wrong
System: Let me help. Try:
  - /monitoring health
  - /monitoring anomalies
  - /status
```

---

## 🛠️ Troubleshooting

### Problem: Backend not running
**Solution**:
```bash
python3 murphy_backend_complete.py
```

### Problem: Frontend not loading
**Solution**: Use `http://localhost:3002` NOT the exposed URL

### Problem: Terminal not responding
**Solution**: Check browser console for errors, verify backend is running

### Problem: Librarian not working
**Solution**: Check LLM status with `/llm status`

---

## 📖 Documentation

- **Complete Guide**: `BUG_FIXES_AND_SOLUTIONS.md`
- **Integration Details**: `LIBRARIAN_INTEGRATION_COMPLETE.md`
- **Task Tracking**: `todo.md`

---

## 🎉 You're Ready!

The Murphy System is now fully operational with:
- ✅ Natural language interface
- ✅ 10 integrated systems
- ✅ Intelligent command suggestions
- ✅ Workflow generation
- ✅ Real-time updates

**Start exploring at: http://localhost:3002**

---

**Need Help?** Check the documentation files or review the browser console for errors.