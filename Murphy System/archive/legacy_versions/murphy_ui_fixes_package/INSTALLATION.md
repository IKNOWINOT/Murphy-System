# Murphy UI Fixes - Installation Guide

## What's Included

This package contains the fixed Murphy system files with:
1. ✅ Fixed `/librarian` command
2. ✅ Event logging system
3. ✅ Click-to-view-logs functionality
4. ✅ Beautiful log viewing modal

## Files Included

- `murphy_complete_integrated.py` - Updated server with event logging
- `murphy_ui_final.html` - Updated UI with click handlers and modal
- `README.md` - Complete documentation of fixes
- `todo.md` - Checklist of completed tasks

## Installation Steps

### 1. Backup Your Current Files
```bash
# Backup your existing files first!
cp murphy_complete_integrated.py murphy_complete_integrated.py.backup
cp murphy_ui_final.html murphy_ui_final.html.backup
```

### 2. Replace Files
```bash
# Copy the new files to your Murphy directory
cp murphy_complete_integrated.py /path/to/your/murphy/directory/
cp murphy_ui_final.html /path/to/your/murphy/directory/
```

### 3. Restart the Server
```bash
# Stop the current server
pkill -f murphy_complete_integrated.py

# Start the new server
python3 murphy_complete_integrated.py
```

### 4. Test the Fixes

Open your browser to `http://localhost:3002` and test:

1. **Test Librarian Command:**
   ```
   /librarian What can Murphy do?
   ```
   - Should work without errors
   - Response should show 📋 indicator

2. **Test Log Viewing:**
   - Click on any message with 📋 indicator
   - Modal should popup with detailed logs
   - Should show request/response data

3. **Test LLM Generation:**
   ```
   Hello Murphy!
   ```
   - Should generate response
   - Response should have 📋 indicator
   - Click to view logs

## What Changed

### Server Changes (murphy_complete_integrated.py)
- Added event logging system (stores last 1000 events)
- Added `log_event()` function
- Added `/api/logs/<event_id>` endpoint
- Added `/api/logs?limit=N` endpoint
- Updated `/api/llm/generate` to log events
- Updated `/api/librarian/ask` to log events and accept `query` parameter

### UI Changes (murphy_ui_final.html)
- Fixed librarian command to send `query` instead of `question`
- Updated `addMessage()` to accept and store event_id
- Added click handlers to messages with event_ids
- Added `showEventLogs()` function
- Added log viewing modal HTML/CSS
- Added 📋 indicator for messages with logs

## Troubleshooting

### Librarian Not Working
- Check server logs for errors
- Verify the server is running on port 3002
- Test the API directly: `curl -X POST http://localhost:3002/api/librarian/ask -H "Content-Type: application/json" -d '{"query":"test"}'`

### Logs Not Showing
- Verify event_id is in the API response
- Check browser console for JavaScript errors
- Make sure you're clicking on messages with 📋 indicator

### Modal Not Appearing
- Check browser console for errors
- Verify CSS is loaded correctly
- Try refreshing the page

## Support

If you encounter any issues:
1. Check the server logs
2. Check browser console (F12)
3. Verify all files were copied correctly
4. Make sure you restarted the server

## Features

### Event Logging
Every API call now generates a unique event_id and stores:
- Timestamp
- Command/query
- Request data
- Response data
- Any errors

### Log Viewing
Click any message with 📋 to see:
- Complete event information
- Formatted JSON data
- Request/response details
- Error information (if any)

### Librarian Command
Now works correctly with:
- `/librarian` - Uses default question
- `/librarian Your question` - Uses your custom question

Enjoy your enhanced Murphy system! 🚀