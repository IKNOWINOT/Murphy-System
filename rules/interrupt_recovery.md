# Interrupt Recovery Rule
# Activated automatically on every session start and after any automation fires

## The Problem
Gmail fires 150+ times/day. Every trigger hijacks the active conversation context.
When I return from handling an automation, I must recalibrate to what I was doing before.

## Recovery Protocol

### On EVERY automation trigger (before handling):
1. Check <conversation_context> and recent messages — what was the last user task?
2. Note the active session work (e.g. "patching Murphy MFGC dispatch pipeline")
3. Handle the automation MINIMALLY — triage only, no deep dives unless truly urgent
4. After handling: explicitly restate the active task in my reply so the user knows I'm back on it

### Triage rules for Gmail automation:
- PATH 1 (Murphy asks Steve): HANDLE IT — this is real work
- PATH 2 (founder directive): LOG IT — one line, no context switch
- PATH 3 (verification): LOG IT — one line, no context switch  
- Everything else (promo, newsletter, notification): SKIP — one line max, no tools

### After returning from interrupt:
End my automation response with:
"↩ Returning to: [what I was doing before this fired]"

Only omit this if the automation required actual work (PATH 1).

## Active Work State
This is updated by the session when a long task is in progress.
Check memory.md entry ### 50+ for current Murphy system work state.
