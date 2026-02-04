# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

#!/usr/bin/env python3
"""
Move addTerminalLog function to be defined earlier in DOMContentLoaded block.
"""

import re

# Read the file
with open('/workspace/murphy_complete_v2.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the addTerminalLog function (lines 4265-4282)
pattern = r"(        function addTerminalLog\(message, type = 'info'\) \{.*?terminalContent\.scrollTop = terminalContent\.scrollHeight;\s*\})"

match = re.search(pattern, content, re.DOTALL)
if not match:
    print("ERROR: Could not find addTerminalLog function")
    exit(1)

addTerminalLog_func = match.group(1)

# Remove the original function
content = re.sub(pattern, "", content, flags=re.DOTALL)

# Find where to insert it - after the ws variable definition (around line 1965)
# Look for: let ws = null;
insert_pattern = r"(let ws = null;)"
replacement = r"\1\n\n        // ============================================\n        // TERMINAL - Defined early for use throughout\n        // ============================================\n        \n" + addTerminalLog_func + "\n"

content = re.sub(insert_pattern, replacement, content, count=1)

# Write back
with open('/workspace/murphy_complete_v2.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Moved addTerminalLog function to be defined earlier")
print("✓ Function is now available for all other functions to call")