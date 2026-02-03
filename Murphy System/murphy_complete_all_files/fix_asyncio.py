#!/usr/bin/env python3
"""
Fix asyncio event loop issues in murphy_backend_complete.py
The issue is that the code creates new event loops when one already exists.
"""

import re

def fix_asyncio_issues():
    with open('murphy_backend_complete.py', 'r') as f:
        content = f.read()
    
    # Fix 1: Replace problematic event loop creation with a helper function
    fix_pattern = r'''import asyncio
        
        loop = asyncio\.new_event_loop\(\)
        asyncio\.set_event_loop\(loop\)
        
        try:
            (.*?)loop\.run_until_complete\((.*?)\)'''
    
    replacement = r'''import asyncio
        
        # Properly handle event loop
        try:
            loop = asyncio.get_running_loop()
            # If there's already a running loop, we can't use run_until_complete
            # Need to run async code differently
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, \2)
                \1result = future.result()
        except RuntimeError:
            # No running loop, create new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                \1loop.run_until_complete(\2)'''
    
    # This is getting complex. Let me use a simpler approach - just use asyncio.run()
    # which handles the event loop properly
    
    # Replace the problematic pattern
    content = re.sub(
        r'''import asyncio
        
        loop = asyncio\.new_event_loop\(\)
        asyncio\.set_event_loop\(loop\)
        
        try:
            response = loop\.run_until_complete\((.*?)\)''',
        r'''import asyncio
        
        try:
            response = asyncio.run(\1''',
        content,
        flags=re.DOTALL
    )
    
    # Remove the finally: loop.close() since asyncio.run() handles it
    content = re.sub(
        r'''finally:\s*loop\.close\(\)''',
        r'''except Exception as e:\n            logger.error(f"Async error: {e}")\n            raise''',
        content
    )
    
    with open('murphy_backend_complete.py', 'w') as f:
        f.write(content)
    
    print("✓ Fixed asyncio issues")

if __name__ == '__main__':
    fix_asyncio_issues()