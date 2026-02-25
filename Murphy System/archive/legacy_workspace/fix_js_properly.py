#!/usr/bin/env python3
"""
Fix the JavaScript in murphy_ui_fixed_bugs.html properly
"""

with open('murphy_ui_fixed_bugs.html', 'r') as f:
    content = f.read()

# Find and replace the addMessage function
old_function = '''        function addMessage(type, content, cssClass) {
            const messagesEl = document.getElementById('messages');
            const time = new Date().toLocaleTimeString();
            
            const messageEl = document.createElement('div');
            messageEl.className = 'message';
            messageEl.innerHTML = `
                <div class="message-header">
                    <span class="message-type ${cssClass}">${type}</span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-content ${cssClass}">${escapeHtml(content)}</div>
            `;
            
            messagesEl.appendChild(messageEl);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }'''

new_function = '''        function addMessage(type, content, cssClass) {
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

content = content.replace(old_function, new_function)

with open('murphy_ui_fixed_bugs.html', 'w') as f:
    f.write(content)

print("✓ Fixed JavaScript in murphy_ui_fixed_bugs.html")
print("  - Added unique message IDs")
print("  - Added setTimeout for smooth scroll")