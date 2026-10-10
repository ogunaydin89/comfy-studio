#!/usr/bin/env bash
# ==============================================================================
# Comfy Studio - Internal ComfyUI Engine Launcher (AMD ROCm 7.2 + SDXL)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
COMFY_DIR="$SCRIPT_DIR/engine"

# AMD ROCm / Navi 23 Hardware Optimizations
export HSA_OVERRIDE_GFX_VERSION=10.3.0
export HSA_ENABLE_SDMA=0
export HSA_ENABLE_INTERRUPT=0
export ROCR_VISIBLE_DEVICES=0
export MIOPEN_FIND_MODE=1
export PYTORCH_HIP_ALLOC_CONF="garbage_collection_threshold:0.6,max_split_size_mb:64"

# The Studio page is served from its own port, so its WebSocket to the engine
# carries a different Origin than the engine's Host. ComfyUI's default
# origin_only middleware answers that mismatch with 403, which is why CORS has
# to be enabled here at all -- but it is scoped to exactly that one origin
# instead of "*", so no other page can read the engine's history or stats.
STUDIO_ORIGIN="http://127.0.0.1:${COMFY_STUDIO_PORT:-5111}"

exec "$VENV_DIR/bin/python" "$COMFY_DIR/main.py" \
    --listen 127.0.0.1 \
    --port 8188 \
    --fp32-vae \
    --cpu-vae \
    --use-split-cross-attention \
    --reserve-vram 1.0 \
    --enable-cors-header "$STUDIO_ORIGIN" \
    --cache-lru 1 \
    "$@"
