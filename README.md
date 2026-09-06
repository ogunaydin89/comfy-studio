# 🎨 Comfy Studio

> A sleek, high-performance, dark-mode desktop studio interface for image generation powered by ComfyUI and SDXL.

Comfy Studio provides an intuitive, distraction-free creative workspace. It bypasses the complexity of spaghetti node graphs while preserving 100% of ComfyUI's underlying raw inference speed, hardware offloading, and modular checkpoint management.

---

## ✨ Features

- **🚀 Zero-Dependency UI Layer**: Written entirely in Python standard library + modern HTML5/CSS3/ES6. No bloated node modules, no Electron, zero extra pip packages required for the studio itself.
- **⚡ Native App Wrapper**: Runs as an ultra-responsive standalone desktop application via Chrome App mode (`--app=...`) or any modern web browser.
- **📊 Real-time Hardware Telemetry**: Live VRAM allocation counter (tuned for AMD Radeon RX 6650 XT Navi 23 / ROCm 7.2) and engine health monitoring.
- **🔄 Seamless Model Swapping**: Directly lists and switches between loaded checkpoints (`RealVisXL`, `AnimagineXL`, `DynaVisionXL`, and custom safetensors).
- **📐 Aspect Ratio Presets**:
  - `9:16` (896 × 1600) — YouTube Shorts, TikTok, Instagram Reels.
  - `1:1` (1024 × 1024) — High-detail Square.
  - `16:9` (1344 × 768) — Cinematic Widescreen.
  - `4:5` (896 × 1120) — Social Portrait.
- **⏱️ Live Progress Feedback**: Real-time step-by-step progress tracking via ComfyUI WebSocket (`ws://127.0.0.1:8188/ws`).
- **🖼️ Built-in Output Gallery**: Instant access to previous generations with quick clipboard copy, direct download, and one-click opening in Dolphin / file manager.

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
For 8GB VRAM cards like the AMD Radeon RX 6650 XT, launch ComfyUI with:
```bash
export HSA_OVERRIDE_GFX_VERSION=10.3.0
export MIOPEN_FIND_MODE=1
export PYTORCH_HIP_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
python main.py --listen 127.0.0.1 --port 8188 --cpu-vae --use-split-cross-attention --cache-lru 1
```
- **`--cpu-vae`**: Keeps SDXL UNet diffusion 100% on the GPU while offloading the final single VAE decode pass to the CPU to avoid 8GB VRAM OOM.
- **`--cache-lru 1`**: Prevents multi-model switching from thrashing system RAM.

---

## 📦 Codeberg Git Setup

```bash
git init
git add .
git commit -m "feat: initial commit of Comfy Studio"
git remote add origin https://codeberg.org/helinesca/comfy-studio.git
git branch -M main
git push -u origin main
```

---

## 📄 License

MIT © [helinesca](https://codeberg.org/helinesca)
