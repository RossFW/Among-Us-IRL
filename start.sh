#!/bin/bash
cd "$(dirname "$0")"

# Kill any existing server on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null

# Activate virtual environment
source venv/bin/activate

# Get local IP for phone access
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "Check your WiFi settings")

echo ""
echo "========================================"
echo "      Among Us IRL - Server"
echo "========================================"
echo ""
echo "Access URLs:"
echo "  Computer:  http://localhost:8000"
echo "  Phone:     http://$LOCAL_IP:8000"
echo ""
echo "For game day (external access):"
echo "  Run in new terminal: cloudflared tunnel --url http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"
echo ""

# Start the server
uvicorn server.main:app --host 0.0.0.0 --port 8000
