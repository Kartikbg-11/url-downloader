#!/bin/bash
# URL Downloader Backend Startup Script

BACKEND_DIR="/home/z/my-project/mini-services/url-downloader-backend"
VENV_PYTHON="$BACKEND_DIR/venv/bin/python"
LOG_FILE="/tmp/backend.log"

cd "$BACKEND_DIR" || exit 1

# Start the server in the background
exec "$VENV_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
