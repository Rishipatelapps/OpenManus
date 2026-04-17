#!/bin/bash
# OpenManus Web Launcher
# This script starts the backend + frontend and opens the browser

cd "$(dirname "$0")"

# Kill any existing servers on these ports
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true

sleep 1

# Start backend in background
python3 simple_backend.py 0.0.0.0 8000 > /tmp/openmanus_backend.log 2>&1 &
BACKEND_PID=$!

# Start frontend in background
python3 -m http.server 5000 > /tmp/openmanus_frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait a moment for servers to start
sleep 2

# Open in browser
URL="http://localhost:5000/web-frontend.html"
if command -v xdg-open &> /dev/null; then
    xdg-open "$URL"
elif command -v open &> /dev/null; then
    open "$URL"
elif command -v firefox &> /dev/null; then
    firefox "$URL" &
elif command -v google-chrome &> /dev/null; then
    google-chrome "$URL" &
else
    echo "Please open $URL in your browser"
fi

# Keep the script running & show PIDs for cleanup
echo "OpenManus Web is running!"
echo "Backend PID: $BACKEND_PID (port 8000)"
echo "Frontend PID: $FRONTEND_PID (port 5000)"
echo ""
echo "To stop: kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop the servers"

# Trap Ctrl+C and cleanup
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# Wait for both processes
wait
