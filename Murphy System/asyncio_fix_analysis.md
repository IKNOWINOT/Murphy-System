# Asyncio Event Loop Error Analysis

## Problem
Error: "Cannot run the event loop while another loop is running"

## Root Cause
The code is trying to create a new event loop and run it while Flask (which may have its own event loop) is already running.

## Current Code (WRONG):
```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    result = loop.run_until_complete(client.generate(prompt))
finally:
    loop.close()
```

## Best Practices for Asyncio in Sync Context:

### Option 1: Use asyncio.run() (Python 3.7+)
- Creates and manages event loop automatically
- Cleans up properly
- BUT: Still fails if another loop is running

### Option 2: Check for existing loop and use it
- Get current loop if exists
- Create new one only if needed
- Proper for mixed sync/async environments

### Option 3: Use nest_asyncio (BEST for Flask)
- Allows nested event loops
- Specifically designed for Jupyter/Flask/Django
- Patches asyncio to allow nesting

### Option 4: Make the whole function async (IDEAL)
- Convert sync wrapper to async
- Let caller handle event loop
- Most Pythonic approach

## Recommended Solution for Murphy:
Use nest_asyncio + proper loop detection

## Implementation:
1. Add nest_asyncio to requirements.txt
2. Apply patch at module level
3. Use try/except to get existing loop
4. Fallback to asyncio.run() if no loop exists
