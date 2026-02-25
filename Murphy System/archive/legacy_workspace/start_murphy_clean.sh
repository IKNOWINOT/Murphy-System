#!/bin/bash

# Kill all existing processes
echo "Stopping all existing Murphy processes..."
pkill -9 -f "python.*http.server" 2>/dev/null
pkill -9 -f "murphy_backend" 2>/dev/null
sleep 3

# Verify all processes are stopped
echo "Verifying cleanup..."
ps aux | grep -E "(murphy|backend|http.server)" | grep -v grep
if [ $? -eq 0 ]; then
    echo "Warning: Some processes still running"
    ps aux | grep -E "(murphy|backend|http.server)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
    sleep 2
fi

# Start backend
echo "Starting Murphy Backend on port 3002..."
cd /workspace
nohup python3 murphy_backend_complete.py > /tmp/murphy_backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to initialize
sleep 5

# Check if backend started
if ps -p $BACKEND_PID > /dev/null; then
    echo "✓ Backend started successfully"
    curl -s http://localhost:3002/api/status | head -5
else
    echo "✗ Backend failed to start"
    tail -20 /tmp/murphy_backend.log
    exit 1
fi

# Start frontend on port 8000 (clean port)
echo "Starting Frontend on port 8000..."
nohup python3 -m http.server 8000 > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

sleep 2

# Check if frontend started
if ps -p $FRONTEND_PID > /dev/null; then
    echo "✓ Frontend started successfully"
else
    echo "✗ Frontend failed to start"
    tail -20 /tmp/frontend.log
    exit 1
fi

echo ""
echo "=========================================="
echo "Murphy System Started Successfully!"
echo "=========================================="
echo "Backend PID: $BACKEND_PID (Port 3002)"
echo "Frontend PID: $FRONTEND_PID (Port 8000)"
echo ""
echo "Access the system at:"
echo "https://8000-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai/murphy_complete_v2.html"
echo ""
echo "Check logs:"
echo "  Backend: tail -f /tmp/murphy_backend.log"
echo "  Frontend: tail -f /tmp/frontend.log"
echo "=========================================="