#!/bin/bash
# URL Downloader Backend - Persistent Startup Script
# This script keeps the backend running

BACKEND_DIR="/home/z/my-project/mini-services/url-downloader-backend"
VENV_PYTHON="$BACKEND_DIR/venv/bin/python"
PID_FILE="/tmp/backend.pid"
LOG_FILE="/tmp/backend.log"

cd "$BACKEND_DIR" || exit 1

# Function to cleanup on exit
cleanup() {
    echo "Shutting down backend..."
    if [ -f "$PID_FILE" ]; then
        kill "$(cat $PID_FILE)" 2>/dev/null
        rm -f "$PID_FILE"
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start the server
echo "Starting URL Downloader Backend..."
"$VENV_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
PID=$!
echo $PID > "$PID_FILE"
echo "Backend started with PID: $PID"

# Keep script running
wait $PID
