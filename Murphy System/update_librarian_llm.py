#!/usr/bin/env python3
"""
Update librarian commands to use new LLM API endpoints.
"""

# Read the file
with open('/workspace/murphy_complete_v2.html', 'r') as f:
    content = f.read()

# Replace the overview case - using the /api/librarian/overview URL as marker
old_marker = "fetch(`${API_BASE}/api/librarian/overview`)"
new_code = """fetch(`${API_BASE}/api/llm/generate`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ prompt: 'What is the system overview?' })
                        })"""

content = content.replace(old_marker, new_code)

# Now update the response handling for overview
# Find and replace the data parsing section
old_handling = """addTerminalLog('\\u2713 Librarian System Overview:', 'success');
                        addTerminalLog(`  Total Interactions: ${data.total_interactions}`, 'info');
                        if (data.intent_distribution && Object.keys(data.intent_distribution).length > 0) {
                            addTerminalLog('  Intent Distribution:', 'info');
                            Object.entries(data.intent_distribution).forEach(([intent, count]) => {
                                addTerminalLog(`    \\u2022 ${intent}: ${count}`, 'info');
                            });
                        }
                        addTerminalLog('  Knowledge Base:', 'info');
                        addTerminalLog(`    \\u2022 Commands: ${data.knowledge_base_size.commands}`, 'info');
                        addTerminalLog(`    \\u2022 Concepts: ${data.knowledge_base_size.concepts}`, 'info');
                        addTerminalLog(`    \\u2022 Workflows: ${data.knowledge_base_size.workflows}`, 'info');"""

new_handling = """if (data.success && data.response) {
                            addTerminalLog('\\u2713 System Overview:', 'success');
                            addTerminalLog(`  Provider: ${data.provider}`, 'info');
                            if (data.demo_mode) {
                                addTerminalLog('  Mode: Demo (simulated)', 'warning');
                            }
                            // Format the response nicely
                            const lines = data.response.split('\\n');
                            lines.forEach(line => {
                                addTerminalLog(`  ${line}`, 'info');
                            });
                        } else {
                            addTerminalLog(`\\u2717 Failed: ${data.error}`, 'error');
                        }"""

content = content.replace(old_handling, new_handling)

# Write back
with open('/workspace/murphy_complete_v2.html', 'w') as f:
    f.write(content)

print("✓ Updated librarian commands to use LLM API")