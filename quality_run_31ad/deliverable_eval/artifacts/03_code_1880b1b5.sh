```bash
#!/bin/bash

# Check if directory path is provided
if [ -z "$1" ]; then
  echo "Error: Directory path is required"
  exit 1
fi

# Set directory path and manifest file
DIR_PATH="$1"
MANIFEST_FILE="/tmp/log_manifest.txt"

# Find and gzip log files older than 7 days
find "$DIR_PATH" -type f -name "*.log" -mtime +7 -print0 | while IFS= read -r -d '' file; do
  # Gzip file
  gzip -f "$file"
  # Append to manifest file
  echo "${file}.gz" >> "$MANIFEST_FILE"
done
```