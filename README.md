# 🎨 Comfy Studio

> A sleek, high-performance, dark-mode desktop studio interface for image generation powered by ComfyUI and SDXL.

Comfy Studio provides an intuitive, distraction-free creative workspace. It bypasses the complexity of spaghetti node graphs while preserving 100% of ComfyUI's underlying raw inference speed, hardware offloading, and modular checkpoint management.

---

## ✨ Features

- **🚀 Zero-Dependency Server Layer**: The studio backend is written entirely in the Python standard library + modern HTML5/CSS3/ES6. No node modules, no Electron, no pip dependencies for the server itself.
- **⚡ Native Qt6 Window**: Runs as a standalone desktop application in an isolated `QWebEngineView` (`window.py`) served from the project's own `.venv` — no Google Chrome dependency. A browser or Chrome app-mode fallback remains in `run.sh` if PyQt6 is unavailable.
  - Closing: the in-page quit button cannot close a top-level `QWebEngineView` window by itself, so `window.py` runs a backend-liveness watchdog (`QTimer` polling `/api/status`) and closes the window once the backend stops.
- **📊 Real-time Hardware Telemetry**: Live VRAM allocation counter (tuned for AMD Radeon RX 6650 XT Navi 23 / ROCm 7.2) and engine health monitoring.
- **🔄 Seamless Model Swapping**: Directly lists and switches between loaded checkpoints (`RealVisXL`, `AnimagineXL`, `DynaVisionXL`, and custom safetensors).
- **📐 Aspect Ratio Presets** — the three SDXL-native resolutions verified stable on 8GB VRAM:
  - `9:16` (768 × 1344) — YouTube Shorts, TikTok, Instagram Reels.
  - `1:1` (1024 × 1024) — High-detail Square.
  - `16:9` (1344 × 768) — Cinematic Widescreen.
- **⏱️ Live Progress Feedback**: Real-time step-by-step progress tracking via ComfyUI WebSocket (`ws://127.0.0.1:8188/ws`).
- **🖼️ Built-in Output Gallery**: Instant access to previous generations with quick clipboard copy, direct download, and one-click opening in Dolphin / file manager.
- **🔁 Batch & Infinite Mode**: Batches of 1–100 images or an infinite loop, cancellable at any time via `/api/interrupt`. Finished images are *moved* (not copied) from ComfyUI's `engine/output/` to `~/Pictures/AI_Generations/`, so `engine/output/` stays empty in normal use.

---

## 📦 Requirements

| Layer | Needs |
| :--- | :--- |
| Server (`app.py`) | Python 3.9+ standard library only — nothing to install |
| Native window (`window.py`) | `PyQt6`, `PyQt6-WebEngine` (listed in `requirements.txt`) |
| Inference engine (`engine/`) | The vendored ComfyUI's own stack, pinned in `comfyui_requirements_freeze.txt` |

`run.sh` prefers the native window and falls back to Chrome app-mode, then to
`xdg-open`, so a venv without the two Qt packages still runs — just not as the
standalone desktop app.

---

## 🚀 Quick Start

### 1. Launch Studio
```bash
./run.sh
```
*The launcher automatically verifies if ComfyUI is active on `127.0.0.1:8188`, launches it if needed, and opens the native Studio window.*

### 2. Manual Server Execution
```bash
python3 app.py
```
Then navigate to `http://127.0.0.1:5111`.

---

## 🛠️ Configuration & Architecture

| Setting | Default Value | Description |
| :--- | :--- | :--- |
| `COMFY_STUDIO_PORT` | `5111` | Port for the Comfy Studio HTTP server |
| `COMFY_HOST` | `127.0.0.1:8188` | Address of the target ComfyUI backend |
| Output Directory | `~/Pictures/AI_Generations/` | Destination for completed rendered images |

### Hardware Optimization Notes (AMD ROCm / Navi 23)

`launch_engine.sh` is the canonical, tested configuration for the AMD Radeon
RX 6650 XT — the values below are reproduced from it, and it is what `run.sh`
actually executes:

```bash
export HSA_OVERRIDE_GFX_VERSION=10.3.0
export HSA_ENABLE_SDMA=0
export HSA_ENABLE_INTERRUPT=0
export ROCR_VISIBLE_DEVICES=0
export MIOPEN_FIND_MODE=1
export PYTORCH_HIP_ALLOC_CONF="garbage_collection_threshold:0.6,max_split_size_mb:64"

python engine/main.py --listen 127.0.0.1 --port 8188 \
    --fp32-vae --cpu-vae --use-split-cross-attention \
    --reserve-vram 1.0 --enable-cors-header "http://127.0.0.1:5111" --cache-lru 1
```

- **`--cpu-vae` / `--fp32-vae`**: Keeps SDXL UNet diffusion 100% on the GPU while
  offloading the final VAE decode pass to the CPU in fp32, avoiding 8GB VRAM OOM.
- **`--reserve-vram 1.0`**: Non-square resolutions run this card right at the VRAM
  ceiling. Without headroom the driver corrupts output silently rather than raising
  an OOM error.
- **`--cache-lru 1`**: Prevents multi-model switching from thrashing system RAM.
- **`--enable-cors-header "http://127.0.0.1:5111"`**: The Studio page is served on
  its own port, so its progress WebSocket reaches the engine with an `Origin` that
  does not match the engine's `Host`. ComfyUI's default `origin_only` middleware
  answers that mismatch with `403`, so CORS must be enabled — but it is scoped to
  exactly the Studio's origin rather than `*`, which keeps any other page in any
  local browser from reading the engine's history, queue or system stats.

#### ⚠️ Settings that silently corrupt output on this card

These produce noise or garbled images rather than a clean error, so they are easy
to misdiagnose. Do not "optimize" them back:

- **`HSA_ENABLE_INTERRUPT=1`** — makes the driver signal GPU-kernel completion
  before VRAM writes have actually landed. Must stay `0`.
- **`PYTORCH_HIP_ALLOC_CONF=expandable_segments:True`** — combined with this card's
  tight 8GB budget it corrupts less-common resolutions (notably 9:16 portrait).
  Use the `garbage_collection_threshold:0.6,max_split_size_mb:64` pair above.

---

## 🔒 Local Attack Surface

The Studio server binds to loopback only, and additionally:

- **Paths are contained.** Every `/static/` and `/api/image/` request resolves
  through `safe_join()`, which rejects anything landing outside its base
  directory — including percent-encoded traversal (`%2e%2e%2f`).
- **The `Host` header is checked** against `127.0.0.1`/`localhost`/`[::1]` on the
  Studio's own port, so a hostname that merely resolves to `127.0.0.1` (DNS
  rebinding) cannot reach these endpoints.
- **Writes require a same-origin JSON request.** Every `POST` must carry
  `Content-Type: application/json` — which cannot be sent cross-origin without a
  CORS preflight this server never answers — and any request arriving with
  `Sec-Fetch-Site: cross-site` is refused. Responses carry no
  `Access-Control-Allow-Origin`, so no other page can read them either.
- **Orphaned engine output is reclaimed at startup.** Saving into
  `~/Pictures/AI_Generations` is driven by the page, so a render that finishes
  after the window closes used to be stranded in `engine/output/`. That directory
  is now swept on launch, which is what keeps it empty as documented above.

---

## 📦 GitHub Git Setup

```bash
git init
git add .
git commit -m "feat: initial commit of Comfy Studio"
git remote add origin https://github.com/ogunaydin89/comfy-studio.git
git branch -M main
git push -u origin main
```

---

## 📄 License

MIT © Ogün Aydın ([ogunaydin89](https://github.com/ogunaydin89))

This project uses **PyQt6**, which is licensed under GPL-3.0 and is installed separately with pip (it is never included in this repository). The code here is MIT; a packaged build that bundles PyQt6 (e.g. an .exe or AppImage) must be distributed under GPL-3.0.
