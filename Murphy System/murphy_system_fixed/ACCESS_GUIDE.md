# Murphy System v2.0 - Access Guide

## 🎯 How to Access the System

### Step 1: Open the Frontend
**Frontend URL:** 
```
https://3000-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai/murphy_complete_v2.html
```

This will load the **Murphy System Interface** with:
- Terminal output
- Agent graph
- State tree
- Process flow
- System metrics

### Step 2: Initialize the System
1. Click the **"INITIALIZE SYSTEM"** button
2. The frontend will automatically connect to the backend API
3. Watch the terminal for initialization messages
4. The system will create:
   - 5 agents (Sales, Engineering, Financial, Legal, Operations)
   - 4 components (LLM Router, Domain Engine, Gate Builder, Swarm Generator)
   - 1 root state
   - 2 gates (Regulatory, Security)

### Step 3: Explore and Interact
- **Click on agents** in the graph to see details
- **Click on states** in the state tree to evolve/regenerate/rollback
- **Watch the terminal** for real-time updates
- **Monitor metrics** in the right sidebar

---

## 🔧 What's Behind the Scenes

### Two Separate Servers

**Frontend Server (Port 3000)**
- Serves the HTML/CSS/JavaScript files
- Provides the user interface
- URL: https://3000-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai

**Backend Server (Port 8000)**
- Handles API requests
- Manages WebSocket connections
- Runs the Murphy System logic
- URL: https://8000-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai

### How They Connect

The frontend automatically detects if you're accessing it:
- **Locally**: Uses `http://localhost:8000` for API calls
- **Publicly**: Uses the backend public URL for API calls

The frontend makes API calls to the backend:
- Fetch system status
- Initialize the system
- Get/update states
- Get/update agents
- Evolve/regenerate/rollback states

The backend sends WebSocket updates to the frontend:
- Agent activity updates
- State evolution updates
- Gate validation results
- Process flow updates

---

## ✅ Troubleshooting

### Issue: Frontend shows API response instead of UI
**Solution**: You're accessing the wrong URL. Use the **frontend URL (port 3000)**, not the backend URL (port 8000).

### Issue: "Connection failed" or "Disconnected"
**Solution**: 
- Check that the backend is running on port 8000
- Refresh the page
- Check browser console for errors (F12)

### Issue: Nothing happens when clicking "INITIALIZE"
**Solution**:
- Check browser console for CORS errors
- Verify backend is accessible
- Try refreshing the page

### Issue: Visualizations not rendering
**Solution**:
- Check browser console for JavaScript errors
- Ensure D3.js and Cytoscape.js loaded successfully
- Try clearing browser cache

---

## 📊 System Architecture

```
User Browser
    ↓
Frontend Server (3000) ← YOU ARE HERE
    ↓ (API calls)
Backend Server (8000)
    ↓ (WebSocket updates)
Frontend receives updates
    ↓
UI updates in real-time
```

---

## 🎯 Key Points

1. **Only access the frontend URL (port 3000)** - this is where the UI lives
2. **The backend (port 8000)** is only for API communication, not for direct access
3. **The frontend automatically connects** to the backend when you initialize
4. **Both servers must be running** for the system to work
5. **WebSocket enables real-time updates** between frontend and backend

---

## 🚀 Ready to Start?

Open this URL in your browser:
```
https://3000-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai/murphy_complete_v2.html
```

Then click **"INITIALIZE SYSTEM"** and explore!

---

**Last Updated**: January 21, 2026
**Status**: Both servers running and ready