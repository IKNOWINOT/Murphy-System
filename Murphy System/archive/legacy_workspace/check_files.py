import os

# List all files
print("="*60)
print("FILES IN WORKSPACE")
print("="*60)

files = [f for f in os.listdir('.') if os.path.isfile(f)]
files.sort()

for f in files:
    size = os.path.getsize(f)
    print(f"{f:50} {size:>10} bytes")

print("\n" + "="*60)
print("POTENTIAL BACKEND FILES (.py)")
print("="*60)

py_files = [f for f in files if f.endswith('.py')]
for f in py_files:
    if 'backend' in f.lower() or 'app' in f.lower() or 'server' in f.lower() or 'main' in f.lower():
        size = os.path.getsize(f)
        print(f"→ {f:50} {size:>10} bytes")

print("\n" + "="*60)
print("POTENTIAL FRONTEND FILES (.html)")
print("="*60)

html_files = [f for f in files if f.endswith('.html')]
for f in html_files:
    if 'murphy' in f.lower() or 'index' in f.lower() or 'complete' in f.lower():
        size = os.path.getsize(f)
        print(f"→ {f:50} {size:>10} bytes")