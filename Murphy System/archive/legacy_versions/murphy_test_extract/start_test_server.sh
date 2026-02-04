#!/bin/bash
# Start Murphy System backend server for testing

cd /workspace/murphy_test_extract
echo "Starting Murphy System Backend Server..."
python murphy_complete_backend.py &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
echo "Server running on port 6666"
echo "Press Ctrl+C to stop"

wait $BACKEND_PID