#!/bin/bash
# OpenManus Web Launcher for macOS
# Double-click this file to start OpenManus Web Interface.
#
# SETUP: Edit the OPENMANUS_DIR path below to point at your local OpenManus
# installation, then right-click > Open (once) to allow unsigned scripts.

OPENMANUS_DIR="$HOME/OpenManus"

cd "$OPENMANUS_DIR" || {
    osascript -e "display alert \"OpenManus not found\" message \"Edit OpenManus.command and set OPENMANUS_DIR to your local install path.\""
    exit 1
}

# Kill anything already on our ports
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5000 | xargs kill -9 2>/dev/null

# Start backend
python3 simple_backend.py 127.0.0.1 8000 > /tmp/openmanus_backend.log 2>&1 &
BACKEND_PID=$!

# Start frontend static server
python3 -m http.server 5000 > /tmp/openmanus_frontend.log 2>&1 &
FRONTEND_PID=$!

sleep 2

# Open browser
open "http://localhost:5000/web-frontend.html"

echo ""
echo "  🤖 OpenManus Web is running"
echo ""
echo "  Frontend: http://localhost:5000/web-frontend.html"
echo "  Backend:  http://localhost:8000/health"
echo ""
echo "  Close this Terminal window to stop."
echo ""

# Keep terminal open and clean up on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM
wait
