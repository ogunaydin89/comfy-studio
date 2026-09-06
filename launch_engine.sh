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
export ROCR_VISIBLE_DEVICES=0
export MIOPEN_FIND_MODE=1
export PYTORCH_HIP_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"

exec "$VENV_DIR/bin/python" "$COMFY_DIR/main.py" \
    --listen 127.0.0.1 \
    --port 8188 \
    --fp32-vae \
    --cpu-vae \
    --use-split-cross-attention \
    --cache-lru 1 \
    "$@"
