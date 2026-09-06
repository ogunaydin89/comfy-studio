#!/usr/bin/env python3
"""
Comfy Studio - Desktop Image Generation Studio
Zero-dependency Python backend interfacing with ComfyUI REST & WebSocket API.
Includes automatic lifecycle management and full VRAM/RAM offloading on exit.
"""

import http.server
import json
import mimetypes
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

PORT = int(os.environ.get("COMFY_STUDIO_PORT", 5111))
COMFY_HOST = os.environ.get("COMFY_HOST", "127.0.0.1:8188")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
OUTPUT_DIR = os.path.expanduser("~/Pictures/AI_Generations")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Lifecycle Watchdog
last_heartbeat = time.time()
has_received_heartbeat = False
server_instance = None

def offload_and_kill_comfy():
    """Completely offloads models from VRAM/RAM and shuts down ComfyUI."""
    print("🛑 Offloading ComfyUI models from VRAM and RAM...")
    try:
        req = urllib.request.Request(
            f"http://{COMFY_HOST}/free",
            data=json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass
    except Exception:
        pass

    print("🛑 Terminating ComfyUI backend process...")
    try:
        subprocess.run(["pkill", "-f", "engine/main.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def watchdog_loop():
    """Shuts down if no browser window has pinged heartbeat in 10 seconds."""
    global last_heartbeat, has_received_heartbeat, server_instance
    while True:
        time.sleep(2)
        if has_received_heartbeat:
            elapsed = time.time() - last_heartbeat
            if elapsed > 10:
                print(f"⚠️ No active browser connection for {elapsed:.1f}s. Initiating auto-shutdown & offload...")
                offload_and_kill_comfy()
                if server_instance:
                    threading.Thread(target=server_instance.shutdown).start()
                break

class StudioHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {format % args}\n")
        sys.stdout.flush()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html")
        elif path.startswith("/static/"):
            rel_path = path[8:]
            target = os.path.join(STATIC_DIR, rel_path)
            self.serve_file(target)
        elif path == "/api/status":
            self.handle_api_status()
        elif path == "/api/gallery":
            self.handle_api_gallery()
        elif path.startswith("/api/image/"):
            filename = urllib.parse.unquote(path[11:])
            target = os.path.join(OUTPUT_DIR, filename)
            self.serve_file(target)
        elif path.startswith("/api/history/"):
            prompt_id = path[13:]
            self.proxy_comfy(f"/history/{prompt_id}")
        elif path == "/api/queue":
            self.proxy_comfy("/queue")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/heartbeat":
            self.handle_heartbeat()
        elif path == "/api/generate":
            self.handle_api_generate()
        elif path == "/api/start_comfyui":
            self.handle_start_comfyui()
        elif path == "/api/open_folder":
            self.handle_open_folder()
        elif path == "/api/save_image":
            self.handle_save_image()
        elif path == "/api/unload":
            self.handle_unload()
        elif path == "/api/shutdown":
            self.handle_shutdown()
        else:
            self.send_error(404, "Not Found")

    def handle_heartbeat(self):
        global last_heartbeat, has_received_heartbeat
        last_heartbeat = time.time()
        has_received_heartbeat = True
        self.send_json({"ok": True, "time": last_heartbeat})

    def handle_unload(self):
        """Unloads all models from VRAM without shutting down server."""
        try:
            req = urllib.request.Request(
                f"http://{COMFY_HOST}/free",
                data=json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.send_json({"success": True, "message": "VRAM and models offloaded."})
        except Exception as e:
            self.send_json({"error": str(e), "success": False}, status_code=500)

    def handle_shutdown(self):
        """Clean shutdown: offloads models, terminates ComfyUI, exits Studio."""
        self.send_json({"success": True, "message": "Shutting down ComfyUI and Studio..."})
        def perform_exit():
            time.sleep(0.5)
            offload_and_kill_comfy()
            print("✨ Shutdown complete. All memory freed.")
            os._exit(0)
        threading.Thread(target=perform_exit).start()

    def serve_file(self, filepath, content_type=None):
        if not os.path.isfile(filepath):
            self.send_error(404, f"File not found: {os.path.basename(filepath)}")
            return
        
        if not content_type:
            content_type, _ = mimetypes.guess_type(filepath)
            if not content_type:
                content_type = "application/octet-stream"

        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def send_json(self, data, status_code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def proxy_comfy(self, endpoint):
        target_url = f"http://{COMFY_HOST}{endpoint}"
        try:
            req = urllib.request.Request(target_url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                content_type = resp.headers.get("Content-Type", "application/json")
                self.send_response(resp.status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_json({"error": f"ComfyUI request failed: {e}", "online": False}, status_code=502)

    def handle_api_status(self):
        status = {
            "online": False,
            "host": COMFY_HOST,
            "checkpoints": [],
            "samplers": [],
            "schedulers": [],
            "system": {},
            "devices": []
        }
        try:
            stats_url = f"http://{COMFY_HOST}/system_stats"
            with urllib.request.urlopen(stats_url, timeout=3) as resp:
                stats = json.loads(resp.read().decode("utf-8"))
                status["online"] = True
                status["system"] = stats.get("system", {})
                status["devices"] = stats.get("devices", [])
        except Exception:
            try:
                queue_url = f"http://{COMFY_HOST}/queue"
                with urllib.request.urlopen(queue_url, timeout=2) as resp:
                    status["online"] = True
            except Exception:
                self.send_json(status)
                return

        try:
            ckpt_url = f"http://{COMFY_HOST}/object_info/CheckpointLoaderSimple"
            with urllib.request.urlopen(ckpt_url, timeout=3) as resp:
                info = json.loads(resp.read().decode("utf-8"))
                status["checkpoints"] = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        except Exception:
            pass

        try:
            sampler_url = f"http://{COMFY_HOST}/object_info/KSampler"
            with urllib.request.urlopen(sampler_url, timeout=3) as resp:
                info = json.loads(resp.read().decode("utf-8"))
                status["samplers"] = info["KSampler"]["input"]["required"]["sampler_name"][0]
                status["schedulers"] = info["KSampler"]["input"]["required"]["scheduler"][0]
        except Exception:
            pass

        self.send_json(status)

    def handle_start_comfyui(self):
        script_path = os.path.join(BASE_DIR, "launch_engine.sh")
        if not os.path.isfile(script_path):
            self.send_json({"error": f"Launch script not found at {script_path}"}, status_code=404)
            return

        try:
            subprocess.Popen(["bash", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            self.send_json({"message": "ComfyUI launch command dispatched", "success": True})
        except Exception as e:
            self.send_json({"error": str(e), "success": False}, status_code=500)

    def handle_open_folder(self):
        try:
            subprocess.Popen(["xdg-open", OUTPUT_DIR], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.send_json({"success": True, "path": OUTPUT_DIR})
        except Exception as e:
            self.send_json({"error": str(e)}, status_code=500)

    def handle_api_gallery(self):
        files = []
        try:
            for entry in os.scandir(OUTPUT_DIR):
                if entry.is_file() and entry.name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    stat = entry.stat()
                    files.append({
                        "name": entry.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "url": f"/api/image/{urllib.parse.quote(entry.name)}"
                    })
            files.sort(key=lambda x: x["mtime"], reverse=True)
        except Exception as e:
            self.send_json({"error": str(e), "images": []}, status_code=500)
            return

        self.send_json({"images": files, "count": len(files), "directory": OUTPUT_DIR})

    def handle_api_generate(self):
        payload = self.read_json_body()
        prompt_text = payload.get("prompt", "a beautiful scenic landscape, masterpiece, 8k")
        negative_text = payload.get("negative_prompt", "ugly, deformed, disfigured, blurry, low quality")
        ckpt_name = payload.get("checkpoint", "RealVisXL_V5.0_fp16.safetensors")
        width = int(payload.get("width", 1024))
        height = int(payload.get("height", 1024))
        steps = int(payload.get("steps", 25))
        cfg = float(payload.get("cfg", 7.0))
        sampler_name = payload.get("sampler_name", "euler")
        scheduler = payload.get("scheduler", "normal")
        seed = int(payload.get("seed", -1))
        if seed == -1:
            seed = int(time.time() * 1000) % 1000000000
        client_id = payload.get("client_id", str(uuid.uuid4()))
        prompt_id = str(uuid.uuid4())

        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": cfg,
                    "denoise": 1.0,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "seed": seed,
                    "steps": steps
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": ckpt_name
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": height,
                    "width": width
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": prompt_text
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": negative_text
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "ComfyStudio",
                    "images": ["8", 0]
                }
            }
        }

        queue_payload = json.dumps({
            "prompt": workflow,
            "client_id": client_id,
            "prompt_id": prompt_id
        }).encode("utf-8")

        req = urllib.request.Request(
            f"http://{COMFY_HOST}/prompt",
            data=queue_payload,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                self.send_json({
                    "success": True,
                    "prompt_id": prompt_id,
                    "client_id": client_id,
                    "seed": seed,
                    "response": resp_data
                })
        except Exception as e:
            self.send_json({"error": f"Failed to queue prompt: {e}", "success": False}, status_code=500)

    def handle_save_image(self):
        payload = self.read_json_body()
        comfy_filename = payload.get("filename")
        subfolder = payload.get("subfolder", "")
        folder_type = payload.get("type", "output")
        model_name = payload.get("model", "sdxl")
        
        if not comfy_filename:
            self.send_json({"error": "Missing filename"}, status_code=400)
            return

        params = urllib.parse.urlencode({
            "filename": comfy_filename,
            "subfolder": subfolder,
            "type": folder_type
        })
        comfy_view_url = f"http://{COMFY_HOST}/view?{params}"

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        clean_model = model_name.split(".")[0].replace("_fp16", "").replace("-", "_")
        local_filename = f"Studio_{timestamp}_{clean_model}.png"
        local_path = os.path.join(OUTPUT_DIR, local_filename)

        try:
            with urllib.request.urlopen(comfy_view_url, timeout=30) as resp:
                with open(local_path, "wb") as f:
                    shutil.copyfileobj(resp, f)
            
            self.send_json({
                "success": True,
                "filename": local_filename,
                "path": local_path,
                "url": f"/api/image/{urllib.parse.quote(local_filename)}"
            })
        except Exception as e:
            self.send_json({"error": f"Failed to save image: {e}", "success": False}, status_code=500)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

def run():
    global server_instance
    server_address = ("127.0.0.1", PORT)
    server_instance = ThreadedHTTPServer(server_address, StudioHandler)
    
    # Start auto-shutdown watchdog thread
    wd = threading.Thread(target=watchdog_loop, daemon=True)
    wd.start()

    print(f"==================================================")
    print(f"  🎨 Comfy Studio running at http://127.0.0.1:{PORT}")
    print(f"  📁 Output Directory: {OUTPUT_DIR}")
    print(f"  🔌 Target ComfyUI:   http://{COMFY_HOST}")
    print(f"  🛡️ Auto-offload:    Enabled on window/app close")
    print(f"==================================================")
    try:
        server_instance.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Comfy Studio...")
        offload_and_kill_comfy()
        server_instance.shutdown()

if __name__ == "__main__":
    run()
