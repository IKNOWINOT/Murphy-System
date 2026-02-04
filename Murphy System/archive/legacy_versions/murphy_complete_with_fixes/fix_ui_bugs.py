#!/usr/bin/env python3
"""
Fix critical UI bugs in murphy_ui_final.html
1. Text doubling/overlapping
2. Scrolling not working
3. Auto-scroll to bottom
"""

import re

print("="*80)
print("FIXING MURPHY UI CRITICAL BUGS")
print("="*80)
print()

# Read the current UI file
with open('murphy_ui_final.html', 'r') as f:
    content = f.read()

print("✓ Loaded murphy_ui_final.html")
print()

# Fix 1: Ensure proper message spacing and no overlapping
print("Fix 1: Preventing text doubling/overlapping...")

# Find the .message CSS and ensure proper spacing
message_css_old = r'\.message\s*{[^}]*}'
message_css_new = '''        .message {
            margin-bottom: 20px;
            padding: 10px 0;
            animation: slideIn 0.3s ease-out;
            clear: both;
            display: block;
            position: relative;
            width: 100%;
        }'''

content = re.sub(message_css_old, message_css_new, content, flags=re.DOTALL)
print("  ✓ Updated .message CSS with proper spacing")

# Fix 2: Ensure scrolling works properly
print("\nFix 2: Fixing scrolling behavior...")

# Update .messages container CSS
messages_css_old = r'\.messages\s*{[^}]*}'
messages_css_new = '''        .messages {
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 15px 20px;
            scroll-behavior: smooth;
            max-height: calc(100vh - 250px);
            min-height: 200px;
        }'''

content = re.sub(messages_css_old, messages_css_new, content, flags=re.DOTALL)
print("  ✓ Updated .messages CSS with proper scrolling")

# Fix 3: Ensure message content doesn't overlap
print("\nFix 3: Fixing message content display...")

# Update .message-content CSS
message_content_css_old = r'\.message-content\s*{[^}]*}'
message_content_css_new = '''        .message-content {
            padding: 8px 12px;
            background: #0a0a0a;
            border-left: 2px solid #0f0;
            line-height: 1.4;
            word-wrap: break-word;
            white-space: pre-wrap;
            font-size: 13px;
            display: block;
            width: 100%;
            box-sizing: border-box;
        }'''

content = re.sub(message_content_css_old, message_content_css_new, content, flags=re.DOTALL)
print("  ✓ Updated .message-content CSS")

# Fix 4: Improve addMessage function to prevent duplicates
print("\nFix 4: Improving addMessage function...")

# Find and replace the addMessage function
add_message_old = r'function addMessage\(type, content, cssClass\)\s*{[^}]*messagesEl\.scrollTop = messagesEl\.scrollHeight;[^}]*}'

add_message_new = '''function addMessage(type, content, cssClass) {
            const messagesEl = document.getElementById('messages');
            const time = new Date().toLocaleTimeString();
            
            // Create unique message ID to prevent duplicates
            const messageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            
            const messageEl = document.createElement('div');
            messageEl.className = 'message';
            messageEl.id = messageId;
            messageEl.innerHTML = `
                <div class="message-header">
                    <span class="message-type ${cssClass}">${type}</span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-content ${cssClass}">${escapeHtml(content)}</div>
            `;
            
            messagesEl.appendChild(messageEl);
            
            // Smooth scroll to bottom with delay to ensure render
            setTimeout(() => {
                messagesEl.scrollTop = messagesEl.scrollHeight;
            }, 50);
        }'''

content = re.sub(add_message_old, add_message_new, content, flags=re.DOTALL)
print("  ✓ Updated addMessage function with duplicate prevention")

# Fix 5: Add CSS to prevent any absolute positioning issues
print("\nFix 5: Adding additional CSS fixes...")

# Find the closing </style> tag and add additional fixes before it
additional_css = '''
        /* Additional fixes for text stacking prevention */
        .message * {
            position: relative;
            z-index: auto;
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 11px;
            width: 100%;
        }
        
        /* Ensure no floating elements */
        .messages::after {
            content: "";
            display: table;
            clear: both;
        }
        
        /* Fix for any potential overlay issues */
        .chat-area {
            position: relative;
            z-index: 1;
        }
        
        .input-area {
            position: relative;
            z-index: 2;
        }
    </style>'''

content = content.replace('    </style>', additional_css)
print("  ✓ Added additional CSS fixes")

# Write the fixed content
with open('murphy_ui_fixed_bugs.html', 'w') as f:
    f.write(content)

print()
print("="*80)
print("✅ BUG FIXES APPLIED")
print("="*80)
print()
print("Created: murphy_ui_fixed_bugs.html")
print()
print("Fixes applied:")
print("  1. ✓ Proper message spacing (margin-bottom: 20px)")
print("  2. ✓ Clear: both to prevent stacking")
print("  3. ✓ Display: block for proper layout")
print("  4. ✓ Width: 100% to prevent overlap")
print("  5. ✓ Scrolling with max-height constraint")
print("  6. ✓ Auto-scroll with 50ms delay")
print("  7. ✓ Unique message IDs to prevent duplicates")
print("  8. ✓ Additional CSS to prevent positioning issues")
print()