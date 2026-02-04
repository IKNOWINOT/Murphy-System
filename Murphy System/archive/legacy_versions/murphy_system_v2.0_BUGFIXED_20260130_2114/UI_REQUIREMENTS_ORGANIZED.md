# Murphy System UI - Requirements Document

## VISUAL BUG IDENTIFIED IN SCREENSHOT
Looking at the screenshot, I can see the text doubling issue at the bottom of the chat area where "GENERATED" message text appears to be overlapping/stacking.

---

## 1. CRITICAL BUG FIXES (Priority: IMMEDIATE)

### Bug 1.1: Text Doubling/Overlapping in Chat Area
**Location:** Bottom left region of chat window
**Issue:** Text appears doubled up and unreadable (visible in screenshot)
**Root Cause:** Likely CSS issue with message stacking or z-index
**Fix Required:**
- Review CSS for `.message` class
- Ensure `clear: both` and `display: block` are applied
- Check for duplicate message rendering in JavaScript
- Verify no absolute positioning conflicts

### Bug 1.2: Chat Scrolling Not Working
**Issue:** Cannot scroll through chat history
**Expected Behavior:** 
- Chat should scroll vertically
- Auto-scroll to bottom on new messages
- User can scroll up to view history
- Last message (user prompt or system response) should remain visible at bottom
**Fix Required:**
- Verify `overflow-y: auto` on `.messages` container
- Ensure `max-height` is set correctly
- Add `scrollTop = scrollHeight` after new messages
- Test scroll behavior with 20+ messages

---

## 2. NEW FEATURES - DETAILED SPECIFICATIONS

### Feature 2.1: Chat Tab Enhancement
**Current State:** Basic chat interface
**Required Changes:**

#### 2.1.1 Multi-User Chat
**Purpose:** Enable communication between users on same business profile/network
**Backend Connection:** 
- Check if `/api/agent/message/send` and `/api/agent/inbox/<agent_name>` can be adapted
- May need new endpoint: `/api/chat/users/send` and `/api/chat/users/messages`

**UI Components:**
- Chat message list (human-to-human)
- User presence indicators
- Message threading

#### 2.1.2 Agent Communication Filter
**Purpose:** View agent-to-agent communications separately
**Backend Connection:** 
- Use existing `/api/agent/message/send` and `/api/agent/thread/<thread_id>`
- Filter by message type

**UI Components:**
- Toggle switch: "Show Agent Communications"
- When ON: Display agent-to-agent messages
- When OFF: Display only human messages
- Visual distinction between message types

**Questions:**
1. Should agent communications be in same chat window or separate panel?
2. Do we need real-time updates via Socket.IO for multi-user chat?
3. What authentication/user identification system exists?

---

### Feature 2.2: Library Terminal Tab (NEW)
**Purpose:** Guided workflow for creating complex commands via Librarian
**Backend Connection:** 
- `/api/librarian/ask` - Initial request
- `/api/librarian/generate-command` - Command generation
- `/api/librarian/suggest-commands` - Suggestions
- `/api/pipeline/explode` - Expand scope (Magnify)
- `/api/pipeline/block/verify` - Solidify action

**Workflow Steps:**

#### Step 1: Initial Request
- User clicks "Library Terminal" tab
- Prompt appears: "What would you like to do?"
- Large text area for detailed request
- "Submit" button

#### Step 2: Magnify Process (3 iterations)
- "Magnify" button appears
- Each click expands scope beyond initial detail
- Shows progressive expansion in UI
- Backend calls `/api/pipeline/explode` with increasing depth

#### Step 3: Solidify
- "Solidify" button appears after 3 magnifications
- Backend calls `/api/pipeline/block/verify` with action="SOLIDIFY"
- Librarian analyzes:
  - Available sensors
  - Dynamic information settings
  - User's budget constraints
  - May generate code if needed
  - May create reasoning gate/sensor agents

#### Step 4: Dual Panel Display
**Left Panel: LLM Processing View**
- Shows Librarian's reasoning
- Natural language explanation
- Questions being considered
- Confidence levels

**Right Panel: Command Preview**
- Exact command that will be sent to Murphy Terminal
- Syntax highlighted
- Editable before execution
- "Execute" button

#### Step 5: Clarifying Questions
- If Librarian needs more info, displays questions
- User answers in dialog
- Process continues

#### Step 6: Insufficient Information Handler
- If cannot proceed, shows: "This cannot be done with the information we have. Would you like us to generate closest ballparks?"
- User chooses: "Yes, generate ballparks" or "No, I'll provide more info"

#### Step 7: Liability Documentation
- All confirmations logged
- Process log created
- Delivered with all deliverables
- Stored via `/api/librarian/deliverable/communicate`

**Questions:**
1. Should Magnify depth be configurable (not always 3)?
2. Where should process logs be stored in database?
3. Should we create new endpoint `/api/librarian/magnify` or use existing pipeline endpoints?

---

### Feature 2.3: Librarian Agent (Project Documentation)
**Purpose:** Monitor all activities and maintain project documentation
**Backend Connection:**
- `/api/llm/status` - Status monitoring
- `/api/llm/usage` - Usage tracking
- `/api/monitoring/health` - System health
- May need new: `/api/librarian/project-log`

**Functionality:**
- Monitors all granular agent activities
- Monitors all human activities
- Generates spreadsheet logs
- Creates graphs/visualizations
- Acts as project's memory

**UI Components:**
- "Project Log" button in sidebar
- Opens modal with:
  - Activity timeline
  - Agent activity graphs
  - Human activity logs
  - Export to spreadsheet button
  - Filter by date/agent/activity type

**Questions:**
1. Should this be a separate tab or modal?
2. What format for spreadsheet export (CSV, Excel)?
3. Real-time updates or refresh button?

---

### Feature 2.4: Murphy Terminal Tab (Reorder)
**Current State:** Exists but needs to be second tab
**Required Changes:**
- Move "Murphy Terminal" to position 2 (after Chat)
- Tab order: Chat → Murphy Terminal → Commands → Modules → Metrics

**Purpose:** Advanced command interface for power users
**Functionality:**
- Direct command input
- Command history (up/down arrows)
- Auto-completion
- Typing `/librarian` opens Library Terminal workflow
- All slash commands work here

**Backend Connection:**
- `/api/command/execute` - Execute commands
- `/api/librarian/suggest-commands` - Auto-complete

**Questions:**
1. Should command history persist across sessions?
2. Should we add command aliases (shortcuts)?

---

### Feature 2.5: Modules Tab Enhancement
**Current State:** Non-functional buttons
**Required Changes:** Make interactive module toggles

**Backend Connection:**
- Need new endpoints:
  - `GET /api/modules/list` - Get all modules and their states
  - `POST /api/modules/toggle` - Enable/disable module
  - `GET /api/modules/status` - Get module status

**UI Components:**
- List of all 21 modules
- Toggle switch for each
- Status indicator (enabled/disabled)
- Description of what each module does
- Dependencies warning (e.g., "Disabling X will affect Y")

**Module List (from backend):**
1. agent_communication
2. artifact_download
3. artifacts
4. automation
5. autonomous_bd
6. business
7. commands
8. database
9. dynamic_projection_gates
10. enhanced_gates
11. generative_gates
12. learning
13. librarian
14. librarian_integration
15. llm
16. monitoring
17. payment_verification
18. production
19. shadow_agents
20. swarm
21. workflow

**Questions:**
1. Should module states persist in database?
2. Should disabling a module require confirmation?
3. What happens to running tasks when module is disabled?

---

### Feature 2.6: Low Confidence Command System
**Purpose:** Handle uncertain commands with human oversight
**Backend Connection:**
- `/api/gates/generate` - Generate confidence gates
- `/api/task/review/create` - Create review task
- `/api/task/review/<task_id>/answer` - Submit answer
- Org chart info from `/api/pipeline/org-chart`

**Workflow:**

#### Step 1: Confidence Scoring
- Every command gets confidence score (0-100%)
- Threshold: <70% = Low Confidence

#### Step 2: Human-in-the-Loop
- Modal appears: "This command has low confidence (XX%). Please confirm:"
- Shows command details
- Shows why confidence is low
- User options: "Confirm" / "Cancel" / "Modify"

#### Step 3: Inadequate Response Handler
- If user confirmation doesn't increase confidence
- System asks follow-up questions
- If still low confidence after 3 attempts:

#### Step 4: Escalation
- Retrieve org chart via `/api/pipeline/org-chart`
- Identify supervisor based on user's role
- Create escalation task via `/api/task/review/create`
- Notify supervisor
- Log escalation

#### Step 5: Documentation
- All steps logged
- Stored with process documentation
- Accessible via `/api/task/review/<task_id>`

**Questions:**
1. Should confidence threshold be configurable per user?
2. How to handle escalations when no supervisor exists?
3. Should we create new endpoint `/api/command/confidence` or use gates?

---

### Feature 2.7: Org Chart Tab (NEW)
**Purpose:** Configure shadow agents based on organizational structure
**Backend Connection:**
- `/api/pipeline/org-chart` - Get/create org chart
- `/api/shadow_agents/*` - Shadow agent configuration
- May need new: `/api/orgchart/configure-agent`

**UI Components:**

#### Main View: Org Chart Visualization
- Visual tree/hierarchy display
- Nodes represent roles/positions
- Click node to configure

#### Configuration Panel (when node clicked):
**Left Side: Role Information**
- Role title
- Responsibilities
- Required knowledge domains
- Current agent assigned (if any)

**Right Side: Shadow Agent Configuration**
- "Create Shadow Agent" button
- Agent name input
- Knowledge domains (checkboxes):
  - Technical knowledge
  - Business processes
  - Industry-specific info
  - Company policies
  - Project history
- Granularity level slider (1-10)
- "Save Configuration" button

#### Agent Behavior Settings:
- Autonomy level
- Decision-making authority
- Escalation rules
- Communication preferences

**Questions:**
1. Should org chart be created automatically or manually?
2. Can one shadow agent serve multiple roles?
3. How to handle org chart changes (promotions, departures)?

---

### Feature 2.8: Enhanced Message Interaction (Clickable Messages)
**Current State:** Messages are static, non-interactive
**Required Changes:** Make all system messages clickable

**Backend Connection:**
- `/api/monitoring/health` - System status
- `/api/gates/sensors/status` - Sensor information
- `/api/agent/inbox/<agent_name>` - Agent thoughts
- `/api/llm/status` - LLM status

**Message Types to Make Interactive:**

#### SYSTEM Messages
Example: "Connected to Murphy System"
**On Click, Show Modal With:**
- Connection details (timestamp, IP, session ID)
- System health metrics
- Active modules list
- Resource usage (RAM, CPU)
- Visual: Connection status graph

#### SYSTEM Messages (Processing)
Example: "Processing: '/help'"
**On Click, Show Modal With:**
- Command being processed
- Processing pipeline stages
- Current stage indicator
- Estimated completion time
- Visual: Pipeline flow diagram

#### VERIFIED Messages
Example: "System initialized successfully"
**On Click, Show Modal With:**
- What was verified
- Verification criteria
- Confidence score
- Verification timestamp
- Visual: Checkmark animation with details

#### GENERATED Messages
Example: "Welcome Corey! I'm ready to help..."
**On Click, Show Modal With:**
- Which agent generated it
- Agent's current state
- Agent's "thoughts" (reasoning)
- Confidence in response
- Alternative responses considered
- Visual: Agent avatar with thought bubble

**Modal Structure:**
```
┌─────────────────────────────────────────┐
│ [Message Type] - [Timestamp]        [X] │
├─────────────────────────────────────────┤
│                                         │
│  Original Message:                      │
│  [Message text]                         │
│                                         │
│  Why This Occurred:                     │
│  [Explanation]                          │
│                                         │
│  System Status:                         │
│  [Visual graphic/chart]                 │
│                                         │
│  Sensor Information:                    │
│  [Per-agent sensor data]                │
│                                         │
│  Agent Thoughts: (if applicable)        │
│  [Agent reasoning]                      │
│                                         │
└─────────────────────────────────────────┘
```

**Questions:**
1. Should modal data be fetched on-demand or cached?
2. Should we show historical data (previous states)?
3. How much detail in "agent thoughts"?

---

### Feature 2.9: Commands Tab Enhancement
**Current State:** Non-functional
**Required Changes:** Display comprehensive, dynamic command list

**Backend Connection:**
- `/api/status` - Get command list (currently returns 61 commands)
- `/api/modules/status` - Get enabled modules (when implemented)

**UI Components:**

#### Command List Display
- Organized by category (11 modules)
- Each command shows:
  - Command name (e.g., `/help`)
  - Description
  - Module it belongs to
  - Status (available/unavailable based on module toggle)
  - Click to copy to clipboard
  - Click to execute

#### Dynamic Filtering
- Filter by module
- Filter by availability
- Search box
- Sort by: name, module, frequency of use

#### Command Details (on click)
- Full description
- Parameters required
- Example usage
- Related commands
- "Execute" button

**Command Categories (from backend):**
1. artifacts (7 commands)
2. business (7 commands)
3. database (5 commands)
4. learning (4 commands)
5. librarian (5 commands)
6. llm (4 commands)
7. monitoring (6 commands)
8. production (5 commands)
9. shadow_agents (7 commands)
10. swarm (5 commands)
11. workflow (6 commands)

**Total: 61 commands**

**Questions:**
1. Should we show all 91 HTTP endpoints or just the 61 registered commands?
2. Should command usage statistics be tracked?
3. Should we add "favorite" commands feature?

---

## 3. USER INTERACTION FLOWS

### Flow 3.1: New User Onboarding
```
1. User opens Murphy System
2. Onboarding modal appears
3. User enters: Name, Business Type, Goal
4. System initializes
5. Welcome message in Chat tab
6. Tooltip tour of interface (optional)
7. Suggested first actions
```

### Flow 3.2: Creating Command via Library Terminal
```
1. User clicks "Library Terminal" tab
2. Prompt: "What would you like to do?"
3. User types detailed request
4. User clicks "Magnify" (3x)
   - Scope expands each time
   - Shows progressive detail
5. User clicks "Solidify"
6. Librarian analyzes and shows:
   - Left panel: LLM reasoning
   - Right panel: Generated command
7. If questions needed:
   - Librarian asks
   - User answers
   - Process continues
8. User reviews command
9. User clicks "Execute"
10. Command runs in Murphy Terminal
11. Results shown in Chat
12. Process log saved
```

### Flow 3.3: Handling Low Confidence Command
```
1. User enters command
2. System calculates confidence: 65% (LOW)
3. Modal appears: "Low confidence warning"
4. User sees:
   - Command details
   - Why confidence is low
   - Options: Confirm/Cancel/Modify
5. User clicks "Confirm"
6. System asks follow-up questions
7. User answers
8. Confidence still low (68%)
9. System escalates:
   - Retrieves org chart
   - Identifies supervisor
   - Creates review task
   - Notifies supervisor
10. Supervisor reviews and approves
11. Command executes
12. All steps logged
```

### Flow 3.4: Configuring Shadow Agent via Org Chart
```
1. User clicks "Org Chart" tab
2. Org chart displays visually
3. User clicks their role node
4. Configuration panel opens
5. User clicks "Create Shadow Agent"
6. User configures:
   - Agent name
   - Knowledge domains (checkboxes)
   - Granularity level
   - Behavior settings
7. User clicks "Save Configuration"
8. System creates shadow agent
9. Agent appears in org chart
10. Agent begins monitoring/learning
```

### Flow 3.5: Viewing Message Details
```
1. User sees message in Chat
2. User clicks message
3. Modal opens showing:
   - Original message
   - Why it occurred
   - System status graphic
   - Sensor information
   - Agent thoughts (if applicable)
4. User reviews information
5. User closes modal
6. Returns to Chat
```

---

## 4. PRIORITY RECOMMENDATIONS

### Phase 1: Critical Fixes (Week 1)
**Priority: IMMEDIATE**
1. Fix text doubling bug in chat
2. Fix chat scrolling
3. Ensure auto-scroll to bottom works

### Phase 2: Core Functionality (Week 2-3)
**Priority: HIGH**
1. Implement Library Terminal tab with full workflow
2. Make Modules tab functional with toggles
3. Reorder tabs (Chat → Murphy Terminal → Commands → Modules → Metrics)
4. Implement clickable messages with detail modals

### Phase 3: Enhanced Features (Week 4-5)
**Priority: MEDIUM**
1. Implement multi-user chat
2. Add agent communication filter
3. Implement Commands tab with dynamic list
4. Add Low Confidence Command System

### Phase 4: Advanced Features (Week 6-8)
**Priority: MEDIUM-LOW**
1. Implement Org Chart tab
2. Implement Librarian Agent (project documentation)
3. Add command history and auto-complete
4. Add usage statistics and analytics

---

## 5. BACKEND REQUIREMENTS ASSESSMENT

### Existing Endpoints That Can Be Used:
✅ `/api/librarian/ask` - Library Terminal requests
✅ `/api/librarian/generate-command` - Command generation
✅ `/api/pipeline/explode` - Magnify functionality
✅ `/api/pipeline/block/verify` - Solidify functionality
✅ `/api/agent/message/send` - Agent communications
✅ `/api/agent/inbox/<agent_name>` - Agent messages
✅ `/api/gates/generate` - Confidence scoring
✅ `/api/task/review/create` - Escalations
✅ `/api/pipeline/org-chart` - Org chart data
✅ `/api/status` - Command list (61 commands)
✅ `/api/monitoring/health` - System status
✅ `/api/llm/status` - LLM status

### New Endpoints Needed:
❓ `/api/modules/list` - Get all modules
❓ `/api/modules/toggle` - Enable/disable modules
❓ `/api/modules/status` - Module status
❓ `/api/chat/users/send` - Multi-user chat (if not using agent endpoints)
❓ `/api/chat/users/messages` - Get user messages
❓ `/api/librarian/project-log` - Project documentation
❓ `/api/command/confidence` - Get command confidence (or use gates)
❓ `/api/message/details/<message_id>` - Get message details for modal

### Questions for Backend Integration:
1. Can `/api/agent/message/send` be used for human-to-human chat or need separate endpoint?
2. Should module states be stored in database or in-memory?
3. Where should process logs be stored (database table? file system?)?
4. Should we create dedicated confidence endpoint or use existing gates system?
5. How to identify and authenticate users for multi-user chat?

---

## 6. DESIGN PRESERVATION NOTES

**MAINTAIN CURRENT VISUAL DESIGN:**
- ✅ Terminal-style aesthetic (black background, green text)
- ✅ Murphy's Law subtitle banner
- ✅ Header with logo and stats
- ✅ Tab navigation style
- ✅ Command sidebar appearance
- ✅ Input field and SUBMIT button style
- ✅ Message color coding (SYSTEM, VERIFIED, GENERATED, USER)
- ✅ Monospace font (Courier New)
- ✅ Green accent colors
- ✅ Overall layout and spacing

**ONLY CHANGE:**
- Functionality (make things work)
- Add new tabs (Library Terminal, Org Chart)
- Make messages clickable
- Add modals for details
- Fix bugs

---

## 7. TESTING REQUIREMENTS

### Test 7.1: Bug Fixes
- [ ] Text no longer doubles/overlaps
- [ ] Chat scrolls smoothly
- [ ] Auto-scroll to bottom works
- [ ] Can scroll up to view history
- [ ] Last message stays visible

### Test 7.2: Library Terminal
- [ ] Tab appears and is clickable
- [ ] Initial prompt displays
- [ ] Magnify button works (3 iterations)
- [ ] Solidify button works
- [ ] Dual panels display correctly
- [ ] Clarifying questions appear when needed
- [ ] Insufficient info handler works
- [ ] Process log is created and saved

### Test 7.3: Modules Tab
- [ ] All 21 modules listed
- [ ] Toggle switches work
- [ ] Module states persist
- [ ] Disabling module affects command availability
- [ ] Dependencies warning shows when needed

### Test 7.4: Clickable Messages
- [ ] All message types are clickable
- [ ] Modal opens with correct data
- [ ] System status displays
- [ ] Sensor information shows
- [ ] Agent thoughts display (when applicable)
- [ ] Modal closes properly

### Test 7.5: Commands Tab
- [ ] All 61 commands listed
- [ ] Commands organized by category
- [ ] Filter by module works
- [ ] Search works
- [ ] Click to copy works
- [ ] Click to execute works
- [ ] Dynamic updates based on module toggles

---

## 8. DOCUMENTATION REQUIREMENTS

### User Documentation Needed:
1. Library Terminal User Guide
2. Org Chart Configuration Guide
3. Module Toggle Guide
4. Low Confidence Command Handling Guide
5. Message Interaction Guide
6. Multi-User Chat Guide

### Developer Documentation Needed:
1. New API Endpoints Specification
2. Frontend-Backend Integration Guide
3. Message Detail Modal Implementation
4. Module Toggle System Architecture
5. Confidence Scoring Algorithm

---

## SUMMARY

This requirements document organizes all requested features into:
- **1 Critical Bug** (text doubling, scrolling)
- **9 New Features** (detailed specifications)
- **5 User Flows** (step-by-step interactions)
- **4 Priority Phases** (implementation timeline)
- **Backend Assessment** (existing vs. needed endpoints)
- **Design Preservation** (maintain current look)
- **Testing Requirements** (verification checklist)

**Next Steps:**
1. Confirm backend endpoints availability
2. Answer outstanding questions
3. Prioritize features
4. Begin Phase 1 implementation (bug fixes)