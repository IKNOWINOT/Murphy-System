# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

#!/usr/bin/env python3
"""
Add error handling to WebSocket event handlers to prevent initialization failures.
"""

import re

# Read the file
with open('/workspace/murphy_complete_v2.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to find WebSocket event handlers calling addTerminalLog
# We'll wrap them in try-catch blocks with function existence checks

# Find all occurrences of addTerminalLog in window.socket.on handlers
pattern = r"(window\.socket\.on\('([^']+)', function\([^)]*\) \{(?:[^}]|}[^}])*?)(addTerminalLog\([^)]+\))"

def wrap_with_error_handling(match):
    prefix = match.group(1)
    call = match.group(3)
    
    # Wrap the addTerminalLog call with error handling
    wrapped = f"""{prefix}
                try {{
                    if (typeof addTerminalLog === 'function') {{
                        {call}
                    }} else {{
                        console.log('WebSocket event: {match.group(2)}');
                    }}
                }} catch (error) {{
                    console.log('WebSocket event error:', error);
                }}"""
    
    return wrapped

# Replace all occurrences
content = re.sub(pattern, wrap_with_error_handling, content)

# Write back
with open('/workspace/murphy_complete_v2.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Added error handling to WebSocket event handlers")