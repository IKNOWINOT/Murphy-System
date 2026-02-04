# Murphy System - Critical Fixes TODO

## Issues Identified

1. ❌ **LLM Generation Failing** - "Error: Generation failed" for all natural language
2. ❌ **Commands Going to Shell** - `/test`, `/generate`, `/initialize` treated as shell commands
3. ❌ **No Natural Language Responses** - Should use Librarian for conversational responses
4. ❌ **Tabs/Buttons Not Working** - UI navigation broken
5. ❌ **Missing Favicon** - 404 error for favicon.ico
6. ❌ **Database System Offline** - "database": false in status

## Section 1: Fix LLM Generation (CRITICAL)

### 1.1 Check Groq API Keys
- [x] Verify groq_keys.txt has valid API keys ✅
- [x] Test LLM endpoint directly ✅
- [x] Fixed missing aiohttp dependency ✅
- [x] Fixed missing groq_client.py module ✅

### 1.2 Fix Natural Language Processing
- [ ] Natural language should route to LLM, not show "Error: Generation failed"
- [ ] Implement proper error handling with user-friendly messages
- [ ] Add fallback to Librarian when LLM fails

### 1.3 Test LLM Integration
- [ ] Test: "how ya doing?" should get conversational response
- [ ] Test: "can you automate my business?" should trigger business automation flow
- [ ] Test: "how do i use groq?" should explain Groq setup

## Section 2: Fix Command Routing

### 2.1 Stop Unknown Commands Going to Shell
- [ ] `/test` should return "Unknown command" not shell error
- [ ] `/generate` should route to LLM generation endpoint
- [ ] `/initialize` should route to system initialization

### 2.2 Implement Command Registry
- [ ] Create whitelist of valid commands
- [ ] Return helpful error for unknown commands
- [ ] Suggest similar commands using Librarian

### 2.3 Fix Command Endpoints
- [ ] Map `/generate <prompt>` to `/api/llm/generate`
- [ ] Map `/initialize` to system initialization
- [ ] Add `/ask <question>` for Librarian queries

## Section 3: Natural Language Interface

### 3.1 Implement Conversational Flow
- [ ] Natural language → LLM for response generation
- [ ] Use Librarian to understand intent
- [ ] Generate helpful, conversational responses

### 3.2 Add Context Awareness
- [ ] Remember conversation history
- [ ] Use context for better responses
- [ ] Maintain user preferences

### 3.3 Implement Examples
- [ ] Show what Murphy can do through examples
- [ ] Demonstrate workflows visually
- [ ] Provide interactive tutorials

## Section 4: Fix UI Navigation

### 4.1 Fix Tabs
- [ ] Check tab click handlers
- [ ] Verify tab content switching
- [ ] Test: Chat, Commands, Modules, Metrics tabs

### 4.2 Fix Buttons
- [ ] Check command sidebar buttons
- [ ] Verify button click handlers
- [ ] Test all clickable elements

### 4.3 Add Visual Feedback
- [ ] Active tab highlighting
- [ ] Button hover states
- [ ] Loading indicators

## Section 5: Database & Systems

### 5.1 Fix Database Connection
- [ ] Check database configuration
- [ ] Initialize database if needed
- [ ] Verify database connectivity

### 5.2 System Health Check
- [ ] All systems should be "true" in status
- [ ] Fix any offline systems
- [ ] Add system recovery mechanisms

## Section 6: Polish & UX

### 6.1 Add Favicon
- [ ] Create favicon.ico
- [ ] Add to server static files
- [ ] Test favicon loads

### 6.2 Improve Error Messages
- [ ] Replace "Error: Generation failed" with helpful messages
- [ ] Explain what went wrong
- [ ] Suggest next steps

### 6.3 Add Help System
- [ ] Interactive help for new users
- [ ] Command suggestions
- [ ] Example workflows

## Section 7: Testing

### 7.1 Test Natural Language
- [ ] "how ya doing?" → conversational response
- [ ] "can you automate my business?" → business automation flow
- [ ] "how do i use groq?" → setup instructions

### 7.2 Test Commands
- [ ] `/status` → system status (working ✓)
- [ ] `/help` → command list (working ✓)
- [ ] `/librarian` → Librarian query (working ✓)
- [ ] `/generate <prompt>` → LLM generation
- [ ] `/health` → health check (working ✓)

### 7.3 Test UI
- [ ] All tabs switch correctly
- [ ] All buttons work
- [ ] Scrolling works (fixed ✓)
- [ ] No console errors

## Priority Order

1. **IMMEDIATE**: Fix LLM generation (Section 1)
2. **HIGH**: Fix command routing (Section 2)
3. **HIGH**: Natural language interface (Section 3)
4. **MEDIUM**: Fix UI navigation (Section 4)
5. **MEDIUM**: Database & systems (Section 5)
6. **LOW**: Polish & UX (Section 6)
7. **FINAL**: Comprehensive testing (Section 7)