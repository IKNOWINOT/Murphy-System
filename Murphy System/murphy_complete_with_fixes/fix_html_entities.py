# Fix HTML entities in murphy_complete_integrated.py
with open('murphy_complete_integrated.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix lines with HTML entities
fixed_lines = []
fixed_count = 0
for i, line in enumerate(lines, 1):
    original = line
    line = line.replace('&quot;', '"')
    line = line.replace('&amp;', '&')
    line = line.replace('&lt;', '<')
    line = line.replace('&gt;', '>')
    if line != original:
        fixed_count += 1
        print(f"Fixed line {i}")
    fixed_lines.append(line)

with open('murphy_complete_integrated.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print(f"\nTotal lines fixed: {fixed_count}")

# Verify
import py_compile
try:
    py_compile.compile('murphy_complete_integrated.py', doraise=True)
    print("✓ File compiles successfully!")
except SyntaxError as e:
    print(f"✗ Still has syntax error at line {e.lineno}: {e.msg}")