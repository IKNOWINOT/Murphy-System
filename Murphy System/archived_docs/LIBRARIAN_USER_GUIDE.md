# 🧙 Murphy System Librarian - User Guide

## What is the Librarian?

The Librarian is Murphy's intelligent guide that understands natural language and helps you navigate the system. Think of it as your personal assistant that knows everything about Murphy System and can guide you through any task.

---

## Quick Start

### Opening the Librarian

**Method 1: Terminal Command**
```bash
murphy> /librarian
```

**Method 2: With a Question**
```bash
murphy> /librarian ask How do I get started?
```

**Method 3: Quick Actions**
Once the panel is open, use the quick action buttons:
- 📖 **Guide Me** - Get step-by-step guidance
- 🔍 **Search Knowledge** - Find commands and concepts
- 📜 **View History** - See past conversations
- 📊 **System Overview** - Get statistics

---

## Understanding the Interface

### Librarian Panel Layout

```
┌─────────────────────────────────────────────────┐
│ 🧙 Librarian - Intelligent Guide            [×] │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ Conversation Area                       │   │
│  │                                         │   │
│  │ 👤 You: How do I create a document?    │   │
│  │                                         │   │
│  │ 🧙 Librarian: Let's create that        │   │
│  │    together! Here's the workflow...    │   │
│  │                                         │   │
│  │    💡 Suggested Commands:              │   │
│  │    [/document create] [/document...]   │   │
│  │                                         │   │
│  │    📋 Document Creation Workflow:      │   │
│  │    1. /document create <type>          │   │
│  │    2. /document magnify <domain>       │   │
│  │    3. /document solidify               │   │
│  │                                         │   │
│  │    ❓ Follow-up Questions:             │   │
│  │    • What type of document?            │   │
│  │    • Which domains to include?         │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ Ask me anything...              [Send]  │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  [📖 Guide Me] [🔍 Search] [📜 History] [📊 Stats] │
└─────────────────────────────────────────────────┘
```

### Message Components

**User Messages** (Blue border)
```
👤 You                                    10:30 AM
How do I create a document?
```

**Librarian Messages** (Green border)
```
🧙 Librarian                              10:30 AM
Let's create that together! Here's the workflow...

[CREATION] 87%  ← Intent badge and confidence

💡 Suggested Commands:
[/document create <type>]  ← Click to execute

📋 Document Creation Workflow:
1. /document create <type> - Create initial document
2. /document magnify <domain> - Add domain expertise
3. /document solidify - Prepare for generation

❓ Follow-up Questions:
• What type of document would you like to create?  ← Click to ask
• Which domains should I include?
```

---

## Common Use Cases

### 1. Getting Started

**Question:** "How do I get started with Murphy?"

**Librarian Response:**
- Intent: GUIDANCE
- Suggests: `/initialize`, `/help`, `/status`
- Workflow: System Initialization (4 steps)
- Follow-ups: "What type of project?", "Any constraints?"

### 2. Creating Documents

**Question:** "I need to create a business proposal"

**Librarian Response:**
- Intent: CREATION
- Suggests: `/document create proposal`
- Workflow: Document Creation (4 steps)
- Follow-ups: "Which domains?", "Any specific requirements?"

### 3. Understanding Concepts

**Question:** "What is a swarm?"

**Librarian Response:**
- Intent: LEARNING
- Suggests: `/help swarm`, `/swarm status`
- Explanation: "A swarm is parallel execution of tasks by multiple agents"
- Follow-ups: "Want to see examples?", "Should I explain swarm types?"

### 4. Troubleshooting

**Question:** "My agent isn't working"

**Librarian Response:**
- Intent: TROUBLESHOOTING
- Suggests: `/status`, `/org agents`, `/llm status`
- Workflow: Troubleshooting steps
- Follow-ups: "What error?", "When did it start?"

### 5. Analyzing Data

**Question:** "Analyze the business domain"

**Librarian Response:**
- Intent: ANALYSIS
- Suggests: `/domain analyze`, `/domain impact`
- Workflow: Analysis Workflow (4 steps)
- Follow-ups: "Which domains?", "Detailed report?"

### 6. Exploring Options

**Question:** "What can I do with states?"

**Librarian Response:**
- Intent: EXPLORATION
- Suggests: `/state list`, `/help state`
- Explanation: States can evolve, regenerate, rollback
- Follow-ups: "Want to see examples?", "Try creating one?"

---

## Intent Categories Explained

### 🔍 QUERY
**When to use:** You want information or status
**Examples:**
- "Show me the system status"
- "List all agents"
- "What domains are available?"

**Librarian provides:**
- Relevant commands to get information
- Links to documentation
- Current system state

### ⚡ ACTION
**When to use:** You want to execute something
**Examples:**
- "Initialize the system"
- "Create a new state"
- "Run a swarm"

**Librarian provides:**
- Exact commands to execute
- Prerequisites to check
- Expected outcomes

### 🧭 GUIDANCE
**When to use:** You need help deciding
**Examples:**
- "What should I do next?"
- "Which domain should I use?"
- "How do I approach this?"

**Librarian provides:**
- Step-by-step guidance
- Decision frameworks
- Recommendations based on context

### 📚 LEARNING
**When to use:** You want to understand something
**Examples:**
- "What is a gate?"
- "How does the swarm system work?"
- "Explain living documents"

**Librarian provides:**
- Clear explanations
- Related concepts
- Examples and tutorials

### 🎨 CREATION
**When to use:** You want to create something
**Examples:**
- "Create a document"
- "Design a new workflow"
- "Build a proposal"

**Librarian provides:**
- Creation workflows
- Template options
- Domain suggestions

### 📊 ANALYSIS
**When to use:** You want analysis or insights
**Examples:**
- "Analyze the domain coverage"
- "Compare these options"
- "Evaluate the constraints"

**Librarian provides:**
- Analysis commands
- Metrics to consider
- Reporting options

### 🔧 TROUBLESHOOTING
**When to use:** Something isn't working
**Examples:**
- "This is broken"
- "I'm getting an error"
- "Why isn't this working?"

**Librarian provides:**
- Diagnostic commands
- Common solutions
- Escalation paths

### 🗺️ EXPLORATION
**When to use:** You want to discover options
**Examples:**
- "What are my options?"
- "Show me what's possible"
- "I want to explore features"

**Librarian provides:**
- Feature overviews
- Capability demonstrations
- Exploration paths

---

## Tips for Best Results

### 1. Be Specific
❌ "Help"
✅ "How do I create a business proposal?"

### 2. Provide Context
❌ "Create something"
✅ "Create a technical specification for a web application"

### 3. Ask Follow-ups
The Librarian suggests follow-up questions - click them to continue the conversation naturally.

### 4. Use Suggested Commands
Click the command chips to execute them directly in the terminal.

### 5. Check Confidence
- 🟢 90-100%: Very High - Trust the suggestion
- 🟡 75-89%: High - Good suggestion
- 🟠 60-74%: Medium - Consider alternatives
- 🔴 40-59%: Low - May need clarification
- ⚫ <40%: Very Low - Ask differently

---

## Terminal Commands Reference

### Basic Commands
```bash
/librarian                    # Open panel
/librarian ask <question>     # Ask a question
/librarian guide              # Get guidance
```

### Search & Discovery
```bash
/librarian search <query>     # Search knowledge base
/librarian search state       # Find info about states
/librarian search swarm       # Find info about swarms
```

### History & Stats
```bash
/librarian transcripts        # View conversation history
/librarian overview           # Get system statistics
```

---

## Keyboard Shortcuts

**In Librarian Panel:**
- `Enter` - Send message
- `Esc` - Close panel
- `↑` / `↓` - Navigate command history (in terminal)

**In Terminal:**
- `/librarian` + `Enter` - Open Librarian
- Type question and press `Enter` - Ask directly

---

## Examples by Task

### Starting a New Project
```
You: "I'm starting a new project, what should I do first?"

Librarian:
  Intent: GUIDANCE (92%)
  
  Here's how to get started:
  
  1. /initialize - Set up the system
  2. /domain list - See available domains
  3. /constraint add <type> - Add project constraints
  4. /org chart - Review organizational structure
  
  Follow-up: What type of project are you working on?
```

### Creating Documentation
```
You: "Create technical documentation"

Librarian:
  Intent: CREATION (88%)
  
  Let's create technical documentation:
  
  Commands:
  • /document create specification
  • /document magnify engineering
  • /document solidify
  
  Workflow:
  1. Create initial document
  2. Add engineering domain expertise
  3. Prepare for generation
  4. Generate with ANALYTICAL swarm
  
  Follow-up: What system are you documenting?
```

### Troubleshooting Issues
```
You: "The swarm isn't executing"

Librarian:
  Intent: TROUBLESHOOTING (85%)
  
  Let's troubleshoot the swarm:
  
  Diagnostic Commands:
  • /status - Check system status
  • /swarm status - Check swarm state
  • /llm status - Check LLM availability
  
  Common Issues:
  1. LLM not connected
  2. Insufficient resources
  3. Invalid swarm configuration
  
  Follow-up: What error message are you seeing?
```

---

## Advanced Features

### Context Awareness
The Librarian remembers your conversation and provides context-aware suggestions.

### Entity Extraction
Automatically identifies:
- **Domains:** business, engineering, financial, etc.
- **Artifacts:** documents, reports, proposals, etc.
- **Actions:** create, analyze, review, etc.
- **Components:** agents, states, gates, swarms, etc.

### Workflow Suggestions
For complex tasks, the Librarian suggests complete workflows with multiple steps.

### Learning from Feedback
The system tracks which suggestions you use and improves over time.

---

## Troubleshooting the Librarian

### Panel Won't Open
```bash
# Check if server is running
murphy> /status

# Try reopening
murphy> /librarian
```

### Slow Responses
- Check internet connection
- Verify LLM status: `/llm status`
- Try simpler questions

### Unclear Suggestions
- Provide more context
- Be more specific
- Use follow-up questions

### Commands Not Working
- Check command syntax
- Verify system is initialized
- Try `/help <command>` for details

---

## Best Practices

### ✅ Do
- Ask natural questions
- Provide context when needed
- Use suggested commands
- Follow up for clarification
- Check confidence levels

### ❌ Don't
- Use overly complex sentences
- Ask multiple questions at once
- Ignore confidence indicators
- Skip initialization steps
- Forget to provide context

---

## Getting Help

### In the Librarian
```
You: "help"
Librarian: Shows available commands and features
```

### In the Terminal
```bash
murphy> /help librarian
murphy> /librarian overview
```

### Quick Reference
- **Intent Categories:** 8 types (QUERY, ACTION, GUIDANCE, etc.)
- **Confidence Levels:** 5 levels (VERY_HIGH to VERY_LOW)
- **Commands:** 6 librarian commands
- **Knowledge Base:** 14 commands, 7 concepts, 3 workflows

---

## Summary

The Librarian is your intelligent guide through Murphy System. It:
- ✅ Understands natural language
- ✅ Provides contextual suggestions
- ✅ Guides you through workflows
- ✅ Learns from your interactions
- ✅ Helps you discover features
- ✅ Troubleshoots issues
- ✅ Answers questions instantly

**Start using it now:**
```bash
murphy> /librarian
```

**Ask your first question:**
```
"How do I get started with Murphy System?"
```

---

**Need more help?** Type `/librarian guide` for interactive guidance!