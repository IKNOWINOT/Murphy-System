import sys
path = sys.argv[1]
# Read from stdin
data = sys.stdin.read()
with open(path, "w", encoding="utf-8") as f:
    f.write(data)
print("OK: wrote", len(data), "chars to", path)

