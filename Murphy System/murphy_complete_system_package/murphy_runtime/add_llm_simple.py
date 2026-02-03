# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

#!/usr/bin/env python3
"""
Add LLM integration before SERVER STARTUP section.
"""

# Read the file
with open('/workspace/murphy_backend_complete.py', 'r') as f:
    lines = f.readlines()

# Find the SERVER STARTUP section
insert_index = None
for i, line in enumerate(lines):
    if "# SERVER STARTUP" in line:
        insert_index = i
        break

if insert_index is None:
    print("Could not find SERVER STARTUP section")
    exit(1)

# Insert LLM integration before SERVER STARTUP
llm_code = """# ============================================================================
# LLM SYSTEM INTEGRATION
# ============================================================================

try:
    # Initialize LLM Manager (starts in demo mode)
    llm_manager = LLMManager(groq_api_keys=[])  # Empty keys = demo mode
    LLM_AVAILABLE = True
    logger.info("LLM Manager initialized (demo mode)")
except Exception as e:
    logger.error(f"Failed to initialize LLM Manager: {e}")
    LLM_AVAILABLE = False
    llm_manager = None

"""

lines.insert(insert_index, llm_code)

# Write back
with open('/workspace/murphy_backend_complete.py', 'w') as f:
    f.writelines(lines)

print(f"✓ LLM integration added at line {insert_index}")