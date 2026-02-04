# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

#!/usr/bin/env python3
"""
Add LLM integration to murphy_backend_complete.py safely.
"""

# Read the file
with open('/workspace/murphy_backend_complete.py', 'r') as f:
    content = f.read()

# Find the location to insert LLM integration
# After: logger.error(f"\u2717 Failed to initialize artifact systems: {e}")
# Before: # ============================================================================
#     SHADOW AGENT SYSTEM INTEGRATION

insert_marker = "logger.error(f&quot;\\u2717 Failed to initialize artifact systems: {e}&quot;)"
shadow_marker = "# ============================================================================\n# SHADOW AGENT SYSTEM INTEGRATION"

llm_integration = """

# ============================================================================
# LLM SYSTEM INTEGRATION
# ============================================================================

try:
    # Initialize LLM Manager (starts in demo mode)
    llm_manager = LLMManager(groq_api_keys=[])  # Empty keys = demo mode
    LLM_AVAILABLE = True
    logger.info("\\u2713 LLM Manager initialized (demo mode)")
except Exception as e:
    logger.error(f"\\u2717 Failed to initialize LLM Manager: {e}")
    LLM_AVAILABLE = False
    llm_manager = None

"""

# Insert the LLM integration
if insert_marker in content and shadow_marker in content:
    # Find the position of the shadow marker
    shadow_pos = content.find(shadow_marker)
    
    # Insert before the shadow marker
    content = content[:shadow_pos] + llm_integration + content[shadow_pos:]
    
    # Write back
    with open('/workspace/murphy_backend_complete.py', 'w') as f:
        f.write(content)
    
    print("✓ LLM integration added successfully")
else:
    print("✗ Could not find insertion markers")
    print(f"Insert marker found: {insert_marker in content}")
    print(f"Shadow marker found: {shadow_marker in content}")