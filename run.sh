#!/usr/bin/env bash
# ==============================================================================
# Comfy Studio - Standalone Desktop Launcher
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=5111
COMFY_PORT=8188
COMFY_SCRIPT="/home/helin/Local Ai Production/scripts/run_comfyui.sh"

echo "🎨 Starting Comfy Studio..."

# 1. Check if ComfyUI is running; if not, launch it
if ! curl -s "http://127.0.0.1:${COMFY_PORT}/system_stats" >/dev/null 2>&1; then
    if [ -f "$COMFY_SCRIPT" ]; then
        echo "⚡ ComfyUI is not running. Launching ComfyUI backend in background..."
        bash "$COMFY_SCRIPT" >/dev/null 2>&1 &
        echo "⏳ Waiting for ComfyUI backend to initialize..."
        for i in {1..30}; do
            if curl -s "http://127.0.0.1:${COMFY_PORT}/system_stats" >/dev/null 2>&1; then
                echo "✅ ComfyUI backend connected!"
                break
            fi
            sleep 1
        done
    else
        echo "⚠️ ComfyUI script not found at $COMFY_SCRIPT. Please ensure ComfyUI is running."
    fi
fi

# 2. Check if Comfy Studio server is running
if ! curl -s "http://127.0.0.1:${PORT}/api/status" >/dev/null 2>&1; then
    echo "🚀 Launching Comfy Studio server on http://127.0.0.1:${PORT}..."
    python3 "$SCRIPT_DIR/app.py" &
    SERVER_PID=$!
    sleep 0.8
else
    echo "ℹ️ Comfy Studio server already active on port ${PORT}."
fi

# 3. Open UI in standalone App mode
URL="http://127.0.0.1:${PORT}"
if [ -x "/opt/google/chrome/google-chrome" ]; then
    echo "🖥️ Opening Chrome App window..."
    exec /opt/google/chrome/google-chrome --app="$URL" "$@"
elif command -v xdg-open >/dev/null 2>&1; then
    exec xdg-open "$URL"
else
    echo "Please open $URL in your web browser."
fi
