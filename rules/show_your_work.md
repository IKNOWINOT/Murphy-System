# Show Your Work — MANDATORY

## Rule: Every deploy/build/multi-step task MUST include:

1. **Before each attempt:** One line saying what you're trying and why
2. **On failure:** What broke, why it broke, what you're changing
3. **On success:** The live URL + HTTP status as PROOF. No URL = not done.
4. **Max 2 silent retries** before surfacing the error to the user

## Deploy proof format (required every time):
```
✅ DEPLOYED: https://[url]
HTTP [status] · [response time]ms · [what it serves]
```

## No exceptions:
- Backend functions → live URL required
- File uploads → CDN URL required  
- SSH deploys → curl proof required
- Email sends → delivery confirmation required

## Context note:
The ISOLATE_INTERNAL_FAILURE pattern in Deno functions is caused by embedding
large HTML strings (>5KB) as template literals inside the function body.
FIX: Upload HTML to CDN via upload_file, deploy a tiny Deno.serve() fetch-proxy.
That pattern is locked in — use it for all HTML-serving backend functions.
