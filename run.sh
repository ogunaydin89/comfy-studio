#!/usr/bin/env bash
# ==============================================================================
# Comfy Studio - Standalone Desktop Launcher with Auto-Offload & Shutdown
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=5111
COMFY_PORT=8188
COMFY_SCRIPT="$SCRIPT_DIR/launch_engine.sh"
CHROME_PROFILE="/home/helin/.cache/comfy-studio-chrome"

echo "🎨 Initializing Comfy Studio..."

# 0. Clean shutdown handler
cleanup() {
    echo ""
    echo "🛑 Shutting down Comfy Studio & fully offloading from VRAM/RAM..."
    # 1. Unload models from VRAM
    curl -s -X POST "http://127.0.0.1:${COMFY_PORT}/free" \
        -H "Content-Type: application/json" \
        -d '{"unload_models": true, "free_memory": true}' >/dev/null 2>&1 || true
    
    # 2. Terminate ComfyUI backend process
    pkill -f "engine/main.py" 2>/dev/null || true
    
    # 3. Terminate Comfy Studio server
    if [ -n "${SERVER_PID:-}" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
    pkill -f "comfy-studio/app.py" 2>/dev/null || true
    
    echo "✨ All engines stopped. 100% VRAM & RAM freed to OS."
}
trap cleanup EXIT INT TERM

# 1. Check if ComfyUI is running; if not, launch it
if ! curl -s "http://127.0.0.1:${COMFY_PORT}/queue" >/dev/null 2>&1; then
    if [ -f "$COMFY_SCRIPT" ]; then
        echo "⚡ Launching ComfyUI backend (AMD RX 6650 XT)..."
        bash "$COMFY_SCRIPT" > "$SCRIPT_DIR/comfyui.log" 2>&1 &
        echo "⏳ Waiting for ComfyUI backend to initialize..."
        for i in {1..30}; do
            if curl -s "http://127.0.0.1:${COMFY_PORT}/queue" >/dev/null 2>&1; then
                echo "✅ ComfyUI backend ready!"
                break
            fi
            sleep 1
        done
    else
        echo "⚠️ ComfyUI script not found at $COMFY_SCRIPT."
    fi
fi

# 2. Check if Comfy Studio server is running
if ! curl -s "http://127.0.0.1:${PORT}/api/status" >/dev/null 2>&1; then
    echo "🚀 Launching Comfy Studio server on http://127.0.0.1:${PORT}..."
    python3 "$SCRIPT_DIR/app.py" &
    SERVER_PID=$!
    sleep 0.8
else
    SERVER_PID=""
fi

# 3. Open UI in isolated native Qt6 window (or fallback to Chrome/browser)
URL="http://127.0.0.1:${PORT}"
WINDOW_RUNNER="$SCRIPT_DIR/window.py"

if [ -f "$WINDOW_RUNNER" ] && [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    echo "🖥️ Running Comfy Studio in native isolated Qt6 window..."
    "$SCRIPT_DIR/.venv/bin/python" "$WINDOW_RUNNER" "$URL" "Comfy Studio" "$SCRIPT_DIR/icon.svg"
elif [ -x "/opt/google/chrome/google-chrome" ]; then
    echo "🖥️ Running Comfy Studio (closing window will completely offload and shut down)..."
    mkdir -p "$CHROME_PROFILE"
    /opt/google/chrome/google-chrome \
        --user-data-dir="$CHROME_PROFILE" \
        --app="$URL" \
        --no-first-run \
        --disable-default-apps \
        --disable-sync \
        "$@"
elif command -v xdg-open >/dev/null 2>&1; then
    echo "🖥️ Opening in default browser..."
    xdg-open "$URL"
    echo "Press Enter or Ctrl+C to shut down and offload..."
    read -r
else
    echo "Please open $URL in your web browser."
    echo "Press Enter or Ctrl+C to shut down and offload..."
    read -r
fi
