# Murphy System Architecture & Demo Plan

## Current System Status

### API Keys Available
**Total: 17 API Keys**

**Groq Keys (16 total):**
1. Murphy System: `REDACTED_GROQ_KEY_PLACEHOLDER`
2. Murphy System 1: `REDACTED_GROQ_KEY_PLACEHOLDER`
3. Murphy System 2: `REDACTED_GROQ_KEY_PLACEHOLDER`
4. Murphy System 3: `REDACTED_GROQ_KEY_PLACEHOLDER`
5. Murphy System 4: `REDACTED_GROQ_KEY_PLACEHOLDER`
6. Murphy System 5: `REDACTED_GROQ_KEY_PLACEHOLDER`
7. Murphy System 6: `REDACTED_GROQ_KEY_PLACEHOLDER`
8. Murphy System 7: `REDACTED_GROQ_KEY_PLACEHOLDER`
9. Murphy System 8: `REDACTED_GROQ_KEY_PLACEHOLDER`
10. Murphy System 9: `REDACTED_GROQ_KEY_PLACEHOLDER`
11. Murphy System 10: `REDACTED_GROQ_KEY_PLACEHOLDER`
12. Murphy System 11: `REDACTED_GROQ_KEY_PLACEHOLDER`
13. Murphy System 12: `REDACTED_GROQ_KEY_PLACEHOLDER`
14. Murphy System 13: `REDACTED_GROQ_KEY_PLACEHOLDER`
15. Murphy System 14: `REDACTED_GROQ_KEY_PLACEHOLDER`
16. Murphy System 15: `REDACTED_GROQ_KEY_PLACEHOLDER`

**Aristotle Key (1 total - Math LLM):**
- Aristotle: `REDACTED_ARISTOTLE_KEY_PLACEHOLDER`

### Current Problem
❌ **Only 9 keys loaded** from `groq_keys.txt` 
❌ **No key rotation** - only first key used
❌ **No Aristotle integration** for mathematical tasks
❌ **No revolving call mechanism**

## Architecture Plan

### Phase 1: Fix LLM Provider (Immediate)
**Goal: Enable proper key rotation and Aristotle integration**

1. **Update `groq_keys.txt`** with all 16 keys
2. **Create `aristotle_key.txt`** for math LLM
3. **Enhance LLM Provider** to:
   - Load all 16 Groq keys
   - Load 1 Aristotle key
   - Implement revolving key rotation (round-robin)
   - Auto-detect mathematical tasks → route to Aristotle
   - Track key usage statistics
   - Handle rate limits gracefully

4. **New LLM Manager Features:**
   ```
   - Key rotation: 1 → 2 → 3 → ... → 16 → 1 (revolving)
   - Math detection: Analyze prompt for math keywords
   - Auto-routing: Math → Aristotle, General → Groq
   - Usage tracking: How many calls per key
   - Failover: If key fails, try next key
   ```

### Phase 2: Integration with Enhanced Runtime (High Priority)
**Goal: Runtime uses all available capacity**

1. **Update Runtime Orchestrator** to:
   - Use 16 Groq keys for general agents
   - Use Aristotle for math-heavy tasks
   - Scale agent count based on available keys
   - Manage rate limits per key
   - Distribute load across all keys

2. **Capacity Calculation:**
   ```
   Free LLM scenario (Groq):
   - 16 keys × rate limits = maximum parallel capacity
   - Default: 16 parallel agents possible
   
   With Aristotle:
   - Math tasks: 1 parallel
   - General tasks: 16 parallel
   ```

3. **Agent Assignment:**
   ```
   Task Analysis:
   - If math-heavy → assign to Aristotle + general agents
   - If general → distribute across 16 Groq keys
   - Load balancing: Round-robin key assignment
   ```

### Phase 3: Demo Creation (Current Focus)
**Goal: Showcase capabilities with real API calls**

## Demo Plan

### Demo 1: Key Rotation Verification
**Test:** Verify all 16 keys work and rotate properly

```python
# Make 20 consecutive calls
# Should cycle through keys 1-16, then 1-4 again
# Track which key used for each call
```

**Expected Output:**
```
Call 1: Key 1 (Murphy System)
Call 2: Key 2 (Murphy System 1)
...
Call 16: Key 15 (Murphy System 15)
Call 17: Key 1 (Murphy System) - rotation complete
...
```

### Demo 2: Math Task Routing
**Test:** Verify mathematical tasks go to Aristotle

```python
# Task 1: "Calculate ROI of AI investment" → Aristotle
# Task 2: "Write marketing copy" → Groq (rotating)
# Task 3: "Solve differential equation" → Aristotle
# Task 4: "Generate blog post" → Groq (rotating)
```

**Expected Output:**
```
Task 1: Aristotle (math detected)
Task 2: Groq Key 1 (general task)
Task 3: Aristotle (math detected)
Task 4: Groq Key 2 (general task)
```

### Demo 3: Enhanced Runtime with All Keys
**Test:** Generate content using full capacity

```python
# Request: "Create a comprehensive business plan"
# Should use multiple agents in parallel
# Each agent gets different key
# Maximum parallelization
```

**Expected Output:**
```
Agent 1: Groq Key 1 (Market Research)
Agent 2: Groq Key 2 (Financial Analysis) - Aristotle subtask
Agent 3: Groq Key 3 (Operations Plan)
Agent 4: Groq Key 4 (Marketing Strategy)
...
Up to 16 parallel agents
```

### Demo 4: Book Generation with All Keys
**Test:** Generate a complete book using maximum parallelization

```python
# Request: "Write a book about AI automation"
# 9 chapters written in parallel
# Each chapter on different key
# 2 extra keys for research and editing
```

**Expected Output:**
```
Chapter 1: Groq Key 1 (Introduction)
Chapter 2: Groq Key 2 (Fundamentals)
...
Chapter 9: Groq Key 9 (Future)
Research: Groq Key 10
Editor: Groq Key 11
Quality Review: Groq Key 12
All in parallel - fastest possible generation
```

## Implementation Plan

### Step 1: Fix Key Loading (Immediate)
- [ ] Create `all_groq_keys.txt` with all 16 keys
- [ ] Create `aristotle_key.txt` with Aristotle key
- [ ] Update LLM provider to load both files

### Step 2: Implement Key Rotation (Critical)
- [ ] Add round-robin rotation logic
- [ ] Track current key index
- [ ] Rotate on each call
- [ ] Add key usage statistics

### Step 3: Add Math Detection (High Priority)
- [ ] Implement math keyword detection
- [ ] Route math tasks to Aristotle
- [ ] Fallback to Groq if Aristotle fails

### Step 4: Enhanced Runtime Integration (High Priority)
- [ ] Update Runtime to use all keys
- [ ] Implement per-key rate limiting
- [ ] Add load balancing
- [ ] Track per-key usage

### Step 5: Demo Scripts (Current)
- [ ] Demo 1: Key rotation verification
- [ ] Demo 2: Math task routing
- [ ] Demo 3: Enhanced runtime
- [ ] Demo 4: Book generation

### Step 6: Documentation (After)
- [ ] Update API documentation
- [ ] Create key rotation guide
- [ ] Document math routing
- [ ] Add runtime capacity guide

## Current System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Murphy System                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │     Enhanced Runtime Orchestrator                 │  │
│  │  - Dynamic agent generation                       │  │
│  │  - Collective mind coordination                   │  │
│  │  - Parallel execution                             │  │
│  │  - Currently: Not using all keys                  │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │     LLM Manager (NEEDS FIX)                       │  │
│  │  - Currently: Only loads 9 keys                  │  │
│  │  - No rotation                                   │  │
│  │  - No Aristotle integration                      │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │     API Keys (17 total)                           │  │
│  │  - Groq: 16 keys (only 9 loaded)                 │  │
│  │  - Aristotle: 1 key (not integrated)             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Target Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Murphy System                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │     Enhanced Runtime Orchestrator                 │  │
│  │  - Dynamic agent generation                       │  │
│  │  - Collective mind coordination                   │  │
│  │  - Parallel execution (up to 16 agents)           │  │
│  │  - Per-key rate limiting                          │  │
│  │  - Load balancing across all keys                 │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │     Enhanced LLM Manager (TO BUILD)               │  │
│  │  - Loads all 17 keys                             │  │
│  │  - Revolving key rotation (1→2→...→16→1)         │  │
│  │  - Math detection → Aristotle routing            │  │
│  │  - Usage tracking per key                         │  │
│  │  - Failover handling                             │  │
│  │  - Rate limit management                         │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │     API Keys (17 total)                           │  │
│  │  - Groq: 16 keys (all loaded & rotating)         │  │
│  │  - Aristotle: 1 key (math routing)               │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Next Steps

**Immediate (Now):**
1. Create enhanced LLM provider with rotation
2. Load all 17 keys
3. Run demo to verify rotation
4. Test math routing

**High Priority:**
5. Integrate with Enhanced Runtime
6. Scale to 16 parallel agents
7. Test with real tasks

**After Demo:**
8. Update documentation
9. Add monitoring endpoints
10. Optimize performance

## Success Criteria

✅ All 17 keys loaded and accessible
✅ Key rotation working (round-robin)
✅ Math tasks routed to Aristotle
✅ General tasks distributed across 16 Groq keys
✅ Runtime can use all 16 keys for parallel execution
✅ Demo showcases full capacity
✅ Usage statistics tracked per key