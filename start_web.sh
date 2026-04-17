#!/bin/bash

set -e

echo "🚀 Starting OpenManus Web Interface..."
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Start the backend server
echo "📡 Starting OpenManus Backend Server on http://localhost:8000..."
python simple_backend.py 0.0.0.0 8000 &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend to start..."
sleep 3

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Failed to start backend server"
    exit 1
fi

echo ""
echo "✅ OpenManus is running!"
echo ""
echo "🌐 Frontend available at: http://localhost:5000"
echo "📡 Backend API at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the servers"
echo ""

# Open browser if available
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:5000" &
elif command -v open &> /dev/null; then
    open "http://localhost:5000" &
fi

# Simple HTTP server for frontend on port 5000
echo "🌍 Starting Frontend Server..."
python3 -m http.server 5000 --directory . &
FRONTEND_PID=$!

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
