# Murphy UI Guide

## Using murphy_ui_final.html

### Accessing the UI
1. Start Murphy backend: `python murphy_complete_integrated.py`
2. Open your browser to: http://localhost:3002
3. The UI will load murphy_ui_final.html automatically

### First Time Setup
1. Onboarding modal will appear
2. Enter your name
3. Select your business type
4. Enter your goal
5. Click "Start Using Murphy"

### Sending Messages
- Type in the input field at the bottom
- Press ENTER or click the ENTER button
- Watch the BQA validation workflow in real-time

### Using Commands
- Type commands starting with / (e.g., /help)
- Or click commands in the sidebar
- Commands are mapped to working backend endpoints

### Viewing Task Details
- Tasks appear as clickable items in messages
- Click any task to open the detail modal
- Left panel shows LLM description
- Right panel shows System description
- Close with X button

### Navigation
- Use tabs at the top: Chat, Commands, Modules, Metrics
- Scroll through message history
- Messages auto-scroll to latest

### Message Types
- **GENERATED** - AI-generated responses (green)
- **USER** - Your input (blue)
- **SYSTEM** - System notifications (orange)
- **VERIFIED** - Validated content (purple)
- **ATTEMPTED** - Command results (cyan)

### Troubleshooting
- If messages stack: Refresh the page
- If scrolling doesn't work: Check browser console
- If commands fail: Check backend is running on port 3002
- If Socket.IO disconnects: Backend may have restarted

### Testing
Run the included test scripts:
- `python systematic_ui_test.py` - Test backend endpoints
- `python complete_ui_validation.py` - Full UI validation

Both should show 100% pass rate.
