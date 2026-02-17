# Agent Communication System - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MURPHY SYSTEM (17 Systems)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                   AGENT COMMUNICATION HUB (NEW)                       │ │
│  ├───────────────────────────────────────────────────────────────────────┤ │
│  │                                                                       │ │
│  │  ┌─────────────────┐      ┌─────────────────┐      ┌──────────────┐ │ │
│  │  │  Message        │      │  Task Review    │      │  Decision    │ │ │
│  │  │  Threading      │◄────►│  System         │◄────►│  Gates       │ │ │
│  │  └─────────────────┘      └─────────────────┘      └──────────────┘ │ │
│  │          │                         │                        │        │ │
│  │          │                         │                        │        │ │
│  │          ▼                         ▼                        ▼        │ │
│  │  ┌─────────────────┐      ┌─────────────────┐      ┌──────────────┐ │ │
│  │  │  Agent          │      │  Cost/Benefit   │      │  Clarifying  │ │ │
│  │  │  Inboxes        │      │  Analysis       │      │  Questions   │ │ │
│  │  └─────────────────┘      └─────────────────┘      └──────────────┘ │ │
│  │                                                                       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│                                      │                                      │
│         ┌────────────────────────────┼────────────────────────────┐        │
│         │                            │                            │        │
│         ▼                            ▼                            ▼        │
│  ┌─────────────┐            ┌─────────────┐            ┌─────────────┐   │
│  │  LIBRARIAN  │            │  LLM SYSTEM │            │  MONITORING │   │
│  │  SYSTEM     │            │  (16 keys)  │            │  SYSTEM     │   │
│  └─────────────┘            └─────────────┘            └─────────────┘   │
│         │                            │                            │        │
│         │                            │                            │        │
│         └────────────────────────────┴────────────────────────────┘        │
│                                      │                                      │
│                                      ▼                                      │
│                          ┌───────────────────────┐                         │
│                          │  Other Murphy Systems │                         │
│                          │  (14 more systems)    │                         │
│                          └───────────────────────┘                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Task Review Creation

```
1. USER REQUEST
   │
   │  "Write a comprehensive guide about AI automation"
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ POST /api/task/review/create                                │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ AgentCommunicationHub.create_task_review()                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: Generate LLM Response                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ LLM System                                         │    │
│  │ - Prompt: "As {role}, analyze: {request}"         │    │
│  │ - Response: 832 tokens                            │    │
│  │ - Model: Groq Llama 3.3 70B                       │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  Step 2: Get Librarian Interpretation                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Librarian System                                   │    │
│  │ - Analyzes request                                 │    │
│  │ - Suggests command chain                           │    │
│  │ - Calculates confidence: 50%                       │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  Step 3: Create Decision Gates                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Decision Gate System                               │    │
│  │ - Revenue Gate: 70% confidence                     │    │
│  │ - Info Source Gate: 80% confidence                 │    │
│  │ - Complexity Gate: 75% confidence                  │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  Step 4: Calculate Costs                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Cost Analysis System                               │    │
│  │ - Token Cost: 932 tokens @ $0.001 = $0.93          │    │
│  │ - Compute + API Cost: $7.50                        │    │
│  │ - Infra/Wear Estimate: $0.50                       │    │
│  │ - Total Execution Cost: $8.93                      │    │
│  │ - Revenue Potential: $500.00                       │    │
│  │ - Cost/Benefit: 56.0                               │    │
│  │ - Recommendation: Proceed                          │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  Step 5: Generate Clarifying Questions                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Question Generator                                 │    │
│  │ - Q1: Deliverable format? (+10%)                  │    │
│  │ - Q2: Target audience? (+10%)                     │    │
│  │ - Q3: Budget/timeline? (+15%)                     │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  Step 6: Determine Confidence Level                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Confidence Calculator                              │    │
│  │ - 50% confidence                                   │    │
│  │ - Level: RED (<70%)                                │    │
│  │ - Status: Requires human input                     │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  Step 7: Create Initial Message                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Message System                                     │    │
│  │ - From: System                                     │    │
│  │ - To: ContentCreator                               │    │
│  │ - Type: TASK_ASSIGNMENT                            │    │
│  │ - Requires Response: true                          │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ RETURN: Complete AgentTaskReview                            │
├─────────────────────────────────────────────────────────────┤
│ - LLM State                                                 │
│ - Librarian Interpretation                                  │
│ - Decision Gates (3)                                        │
│ - Cost Analysis                                             │
│ - Clarifying Questions (3)                                  │
│ - Confidence Level: RED                                     │
│ - Message Thread (1 message)                                │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow: Inter-Agent Communication

```
1. AGENT A SENDS MESSAGE
   │
   │  ContentCreator → Editor: "Review my draft"
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ POST /api/agent/message/send                                │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ AgentCommunicationHub.send_message()                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: Create Message Object                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ AgentMessage                                       │    │
│  │ - message_id: msg_1234567890                      │    │
│  │ - from_agent: ContentCreator                       │    │
│  │ - to_agent: Editor                                 │    │
│  │ - message_type: QUESTION                           │    │
│  │ - subject: "Review Request"                        │    │
│  │ - body: "Please review my draft..."               │    │
│  │ - thread_id: thread_msg_1234567890                │    │
│  │ - requires_response: true                          │    │
│  │ - timestamp: 2026-01-29T20:53:44                  │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  Step 2: Add to Thread                                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │ message_threads[thread_id].append(message)         │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  Step 3: Add to Recipient's Inbox                           │
│  ┌────────────────────────────────────────────────────┐    │
│  │ agent_inboxes['Editor'].append(message)            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ RETURN: Message sent successfully                           │
└─────────────────────────────────────────────────────────────┘
   │
   │
2. AGENT B CHECKS INBOX
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ GET /api/agent/inbox/Editor                                 │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ RETURN: List of messages in Editor's inbox                  │
│ - 1 message from ContentCreator                             │
│ - Requires response                                         │
└─────────────────────────────────────────────────────────────┘
   │
   │
3. AGENT B RESPONDS
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ POST /api/agent/message/send                                │
│ - from_agent: Editor                                        │
│ - to_agent: ContentCreator                                  │
│ - thread_id: thread_msg_1234567890 (same thread)           │
│ - message_type: ANSWER                                      │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ RESULT: Thread now has 2 messages                           │
│ - Message 1: ContentCreator → Editor (QUESTION)             │
│ - Message 2: Editor → ContentCreator (ANSWER)               │
└─────────────────────────────────────────────────────────────┘
```

## Confidence Level Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    CONFIDENCE LEVELS                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🟢 GREEN (95%+)                                            │
│  ├─ Status: Verified, ready to execute                     │
│  ├─ Action: Proceed automatically                          │
│  └─ Human Input: Not required                              │
│                                                             │
│  🟡 YELLOW (70-94%)                                         │
│  ├─ Status: Functional but needs clarification             │
│  ├─ Action: Ask questions first                            │
│  └─ Human Input: Optional but recommended                  │
│                                                             │
│  🔴 RED (<70%)                                              │
│  ├─ Status: Major information needed                       │
│  ├─ Action: Require human input                            │
│  └─ Human Input: Mandatory                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘

WORKFLOW:

Task Created (50% confidence)
   │
   │  🔴 RED - Requires human input
   │
   ▼
System Asks Clarifying Questions
   │
   │  Q1: "What is the deliverable format?"
   │  Q2: "Who is the target audience?"
   │  Q3: "What is the budget/timeline?"
   │
   ▼
User Answers Question 1
   │
   │  Answer: "PDF guide, 50-75 pages"
   │
   ▼
Confidence Increases (60%)
   │
   │  🔴 RED - Still needs more info
   │
   ▼
User Answers Question 2
   │
   │  Answer: "Small business owners"
   │
   ▼
Confidence Increases (70%)
   │
   │  🟡 YELLOW - Functional but clarify
   │
   ▼
User Answers Question 3
   │
   │  Answer: "$5000 budget, 2 weeks"
   │
   ▼
Confidence Increases (85%)
   │
   │  🟡 YELLOW - Can proceed with caution
   │
   ▼
System Generates Content
   │
   ▼
User Reviews Output
   │
   │  Feedback: "Excellent work!"
   │
   ▼
Confidence Increases (95%)
   │
   │  🟢 GREEN - Ready to deploy
   │
   ▼
Task Complete
```

## Decision Gates Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      DECISION GATES                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  GATE 1: REVENUE ANALYSIS                                   │
│  ┌───────────────────────────────────────────────────┐     │
│  │ Question: Does this generate revenue or cost      │     │
│  │           tokens only?                            │     │
│  │                                                   │     │
│  │ Options:                                          │     │
│  │  • Generates Revenue                              │     │
│  │  • Costs Tokens Only                              │     │
│  │  • Uncertain                                      │     │
│  │                                                   │     │
│  │ Confidence: 70%                                   │     │
│  │ Reasoning: Analyzing revenue potential based on   │     │
│  │            task type                              │     │
│  │                                                   │     │
│  │ Token Cost: 100 tokens                            │     │
│  │ Revenue Impact: $0.00                             │     │
│  └───────────────────────────────────────────────────┘     │
│                          │                                  │
│                          ▼                                  │
│  GATE 2: INFORMATION SOURCE                                 │
│  ┌───────────────────────────────────────────────────┐     │
│  │ Question: Where should information come from?     │     │
│  │                                                   │     │
│  │ Options:                                          │     │
│  │  • Generate with AI                               │     │
│  │  • Request from User                              │     │
│  │  • Hire External Service                          │     │
│  │                                                   │     │
│  │ Confidence: 80%                                   │     │
│  │ Reasoning: Determining optimal information source │     │
│  │                                                   │     │
│  │ Token Cost: 50 tokens                             │     │
│  │ Revenue Impact: $0.00                             │     │
│  └───────────────────────────────────────────────────┘     │
│                          │                                  │
│                          ▼                                  │
│  GATE 3: COMPLEXITY ANALYSIS                                │
│  ┌───────────────────────────────────────────────────┐     │
│  │ Question: What is the task complexity?            │     │
│  │                                                   │     │
│  │ Options:                                          │     │
│  │  • Simple (Single Agent)                          │     │
│  │  • Medium (Multiple Agents)                       │     │
│  │  • Complex (Sub-Agents Required)                  │     │
│  │                                                   │     │
│  │ Confidence: 75%                                   │     │
│  │ Reasoning: Assessing task complexity for resource │     │
│  │            allocation                             │     │
│  │                                                   │     │
│  │ Token Cost: 75 tokens                             │     │
│  │ Revenue Impact: $0.00                             │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Cost/Benefit Analysis Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  COST/BENEFIT ANALYSIS                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  INPUT: Task Request                                        │
│  │                                                          │
│  ├─► Calculate Execution Cost                             │
│  │   ├─ LLM tokens used: 832                               │
│  │   ├─ Librarian tokens: ~100                             │
│  │   ├─ Token cost: 932 tokens × $0.001 = $0.93           │
│  │   ├─ Compute/API cost: $7.50                            │
│  │   ├─ Infra/wear estimate: $0.50                         │
│  │   └─ Total execution cost: $8.93                        │
│  │                                                          │
│  ├─► Estimate Revenue Potential                            │
│  │   ├─ Check for revenue keywords                         │
│  │   ├─ Analyze task type                                  │
│  │   └─ Estimated revenue: $500.00                         │
│  │                                                          │
│  ├─► Calculate Cost/Benefit Ratio                          │
│  │   ├─ Revenue / Total Execution Cost                     │
│  │   ├─ $500.00 / $8.93                                    │
│  │   └─ Ratio: 56.0                                        │
│  │                                                          │
│  └─► Generate Recommendation                               │
│      ├─ If ratio > 1.0: "Proceed"                          │
│      ├─ If ratio < 1.0: "Review Required"                  │
│      └─ Result: "Proceed"                                  │
│                                                             │
│  OUTPUT: Cost Analysis Report                               │
│  ┌───────────────────────────────────────────────────┐     │
│  │ Total Execution Cost: $8.93                       │     │
│  │ Revenue Potential: $500.00                        │     │
│  │ Cost/Benefit Ratio: 56.0                          │     │
│  │ Recommendation: ✅  PROCEED                        │     │
│  │                                                   │     │
│  │ Reason: Revenue exceeds total execution cost      │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Integration with Murphy Systems

```
┌─────────────────────────────────────────────────────────────┐
│              AGENT COMMUNICATION INTEGRATION                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LLM SYSTEM (16-key rotation)                               │
│  ├─ Provides content generation                            │
│  ├─ Token usage tracking                                   │
│  └─ Math LLM for calculations                              │
│                                                             │
│  LIBRARIAN SYSTEM                                           │
│  ├─ Request interpretation                                 │
│  ├─ Command chain suggestions                              │
│  └─ Confidence scoring                                     │
│                                                             │
│  MONITORING SYSTEM                                          │
│  ├─ Tracks agent performance                               │
│  ├─ Logs all communications                                │
│  └─ Anomaly detection                                      │
│                                                             │
│  WORKFLOW ORCHESTRATOR                                      │
│  ├─ Manages task dependencies                              │
│  ├─ Schedules agent activities                             │
│  └─ Handles task handoffs                                  │
│                                                             │
│  DATABASE SYSTEM                                            │
│  ├─ Stores task reviews                                    │
│  ├─ Persists message threads                               │
│  └─ Maintains agent state                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Summary

The Agent Communication System is a comprehensive layer that sits on top of Murphy's existing systems, providing:

✅ **Complete Transparency**: Every decision is visible and explainable
✅ **Cost Awareness**: Token costs vs revenue for every action
✅ **Confidence-Based Workflow**: GREEN/YELLOW/RED indicators
✅ **Inter-Agent Communication**: Email-style messaging
✅ **Decision Gates**: Multiple checkpoints for critical choices
✅ **Two-Sided Review**: LLM + Librarian perspectives
✅ **Clarifying Questions**: System asks when uncertain

**Status: Production Ready** 🚀
