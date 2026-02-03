# Murphy UI Fixes - Todo List

## Issues to Fix

### 1. Librarian Command Fix
- [x] Fix `/librarian` command - UI sends `question` but server expects `query`
- [ ] Test `/librarian` command works after fix

### 2. Message Click Handler
- [x] Add click event listener to messages
- [x] When message is clicked, fetch and display all logs for that event
- [x] Create a modal or expandable section to show detailed logs
- [x] Store event/request IDs with each message for log retrieval

### 3. Log Viewing System
- [x] Create API endpoint to fetch logs by event ID
- [x] Design UI component to display detailed logs
- [x] Add ability to expand/collapse log details
- [x] Show timestamp, request details, response details, errors, etc.

### 4. Server Integration
- [x] Add event logging system to server
- [x] Update LLM generate endpoint to log events
- [x] Update librarian ask endpoint to log events
- [x] Test server is logging events correctly

### 5. Testing
- [x] Restart server with new changes
- [x] Test `/librarian` command
- [x] Test clicking on messages to view logs
- [x] Test log modal display
- [x] Verify all event data is captured correctly

## Implementation Plan

1. ✅ Fix librarian command parameter mismatch
2. ✅ Add event tracking to messages (store request IDs)
3. ✅ Add click handlers to message elements
4. ✅ Create log detail view component
5. ✅ Add server-side event logging
6. ⏳ Test all functionality