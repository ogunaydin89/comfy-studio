document.addEventListener("DOMContentLoaded", () => {
  const clientId = "cs_" + Math.random().toString(36).substring(2, 10);
  let ws = null;
  let activePromptId = null;
  let currentWidth = 768;
  let currentHeight = 1344;
  let currentRatio = "9:16";

  // Elements
  const backendStatus = document.getElementById("backendStatus");
  const vramText = document.getElementById("vramText");
  const checkpointSelect = document.getElementById("checkpointSelect");
  const promptInput = document.getElementById("promptInput");
  const btnClearPrompt = document.getElementById("btnClearPrompt");
  const negativePreset = document.getElementById("negativePreset");
  const negativePromptInput = document.getElementById("negativePromptInput");
  const ratioBtns = document.querySelectorAll(".ratio-btn");
  const resText = document.getElementById("resText");
  const stepsInput = document.getElementById("stepsInput");
  const stepsVal = document.getElementById("stepsVal");
  const cfgInput = document.getElementById("cfgInput");
  const cfgVal = document.getElementById("cfgVal");
  const samplerSelect = document.getElementById("samplerSelect");
  const schedulerSelect = document.getElementById("schedulerSelect");
  const seedRandom = document.getElementById("seedRandom");
  const seedInput = document.getElementById("seedInput");
  const btnGenerate = document.getElementById("btnGenerate");
  const btnGenerateText = document.getElementById("btnGenerateText");
  const progressOverlay = document.getElementById("progressOverlay");
  const progressStatus = document.getElementById("progressStatus");
  const progressBar = document.getElementById("progressBar");
  const progressMeta = document.getElementById("progressMeta");
  const shutdownOverlay = document.getElementById("shutdownOverlay");
  const mainImage = document.getElementById("mainImage");
  const placeholder = document.getElementById("placeholder");
  const imageMeta = document.getElementById("imageMeta");
  const btnCopyPrompt = document.getElementById("btnCopyPrompt");
  const btnDownload = document.getElementById("btnDownload");
  const btnOpenFolder = document.getElementById("btnOpenFolder");
  const btnUnload = document.getElementById("btnUnload");
  const btnQuit = document.getElementById("btnQuit");
  const galleryStrip = document.getElementById("galleryStrip");
  const galleryCount = document.getElementById("galleryCount");

  const NEGATIVE_PRESETS = {
    photo: "ugly, deformed, disfigured, poor anatomy, blurry, bad teeth, low quality, artifacts, watermark",
    anime: "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
    cinematic: "oversaturated, cartoon, illustration, drawing, 3d, render, CGI, grainy, text, watermark",
    custom: ""
  };

  // Init Negative Prompt
  negativePromptInput.value = NEGATIVE_PRESETS.photo;

  // Heartbeat loop - informs backend that UI is actively open
  function sendHeartbeat() {
    fetch("/api/heartbeat", { method: "POST" }).catch(() => {});
  }
  sendHeartbeat();
  setInterval(sendHeartbeat, 3000);

  // Setup WebSocket to ComfyUI for real-time progress
  function initWebSocket() {
    try {
      ws = new WebSocket(`ws://127.0.0.1:8188/ws?clientId=${clientId}`);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          handleComfyMessage(msg);
        } catch (e) {}
      };
      ws.onerror = () => {};
      ws.onclose = () => {
        setTimeout(initWebSocket, 3000);
      };
    } catch (e) {}
  }
  initWebSocket();

  function handleComfyMessage(msg) {
    if (!activePromptId) return;

    if (msg.type === "status") {
      const exec = msg.data.status.exec_info;
      if (exec && exec.queue_remaining > 0) {
        progressMeta.textContent = `Queue remaining: ${exec.queue_remaining}`;
      }
    } else if (msg.type === "execution_start") {
      if (msg.data.prompt_id === activePromptId) {
        progressStatus.textContent = "Pipeline executing...";
      }
    } else if (msg.type === "executing") {
      if (msg.data.prompt_id === activePromptId) {
        const node = msg.data.node;
        if (node === "3") {
          progressStatus.textContent = "Sampling on AMD RX 6650 XT...";
        } else if (node === "8") {
          progressStatus.textContent = "Decoding VAE on CPU...";
          progressBar.style.width = "95%";
        } else if (node === null) {
          progressStatus.textContent = "Finalizing image...";
          progressBar.style.width = "100%";
        }
      }
    } else if (msg.type === "progress") {
      if (msg.data.prompt_id === activePromptId) {
        const val = msg.data.value;
        const max = msg.data.max;
        const pct = Math.round((val / max) * 90);
        progressBar.style.width = `${pct}%`;
        progressStatus.textContent = `Sampling step ${val} / ${max}`;
      }
    } else if (msg.type === "executed") {
      if (msg.data.prompt_id === activePromptId && msg.data.output && msg.data.output.images) {
        const img = msg.data.output.images[0];
        saveAndDisplayImage(img);
      }
    }
  }

  // Check Backend Status & Available Checkpoints
  async function checkStatus() {
    try {
      const resp = await fetch("/api/status");
      const data = await resp.json();
      if (data.online) {
        backendStatus.classList.remove("offline");
        backendStatus.classList.add("online");
        backendStatus.querySelector(".status-text").textContent = "ComfyUI Active";

        if (data.devices && data.devices.length > 0) {
          const dev = data.devices[0];
          const freeMb = Math.round(dev.vram_free / (1024 * 1024));
          const totalMb = Math.round(dev.vram_total / (1024 * 1024));
          vramText.textContent = `RX 6650 XT: ${freeMb}MB / ${totalMb}MB`;
        }

        if (data.checkpoints && data.checkpoints.length > 0) {
          const currentVal = checkpointSelect.value;
          checkpointSelect.innerHTML = "";
          data.checkpoints.forEach((ckpt) => {
            const opt = document.createElement("option");
            opt.value = ckpt;
            opt.textContent = ckpt.replace(".safetensors", "");
            checkpointSelect.appendChild(opt);
          });
          if (data.checkpoints.includes(currentVal)) {
            checkpointSelect.value = currentVal;
          }
        }
      } else {
        backendStatus.classList.remove("online");
        backendStatus.classList.add("offline");
        backendStatus.querySelector(".status-text").textContent = "ComfyUI Offline";
        vramText.textContent = "Engine Offline";
      }
    } catch (e) {
      backendStatus.classList.remove("online");
      backendStatus.classList.add("offline");
      backendStatus.querySelector(".status-text").textContent = "Server Offline";
    }
  }

  checkStatus();
  setInterval(checkStatus, 6000);

  // Load Gallery
  async function loadGallery() {
    try {
      const resp = await fetch("/api/gallery");
      const data = await resp.json();
      galleryStrip.innerHTML = "";
      galleryCount.textContent = `${data.count} images`;

      if (data.images && data.images.length > 0) {
        data.images.forEach((img, idx) => {
          const thumb = document.createElement("div");
          thumb.className = "gallery-thumb" + (idx === 0 && !mainImage.classList.contains("hidden") ? " active" : "");
          thumb.title = img.name;
          const imageEl = document.createElement("img");
          imageEl.src = img.url;
          imageEl.loading = "lazy";
          thumb.appendChild(imageEl);
          thumb.addEventListener("click", () => {
            document.querySelectorAll(".gallery-thumb").forEach((t) => t.classList.remove("active"));
            thumb.classList.add("active");
            displayImage(img.url, img.name);
          });
          galleryStrip.appendChild(thumb);
        });
      }
    } catch (e) {}
  }
  loadGallery();

  function displayImage(url, title = "") {
    mainImage.src = url;
    mainImage.classList.remove("hidden");
    placeholder.classList.add("hidden");
    imageMeta.textContent = title;
    btnDownload.href = url;
    btnDownload.download = title || "artwork.png";
  }

  // Batch Mode Controls & State
  let isBatchRunning = false;
  let currentBatchIndex = 1;
  let totalBatches = 1;

  const batchCountInput = document.getElementById("batchCountInput");
  const batchCountVal = document.getElementById("batchCountVal");
  const batchInfinite = document.getElementById("batchInfinite");
  const batchCountGroup = document.getElementById("batchCountGroup");
  const btnStopBatch = document.getElementById("btnStopBatch");

  if (batchInfinite) {
    batchInfinite.addEventListener("change", () => {
      if (batchInfinite.checked) {
        batchCountGroup.style.opacity = "0.5";
        batchCountInput.disabled = true;
        batchCountVal.textContent = "∞ (Continuous Heater)";
      } else {
        batchCountGroup.style.opacity = "1";
        batchCountInput.disabled = false;
        batchCountVal.textContent = `${batchCountInput.value} image${batchCountInput.value > 1 ? "s" : ""}`;
      }
    });
  }

  if (batchCountInput) {
    batchCountInput.addEventListener("input", () => {
      if (!batchInfinite.checked) {
        batchCountVal.textContent = `${batchCountInput.value} image${batchCountInput.value > 1 ? "s" : ""}`;
      }
    });
  }

  async function saveAndDisplayImage(imgInfo) {
    try {
      const resp = await fetch("/api/save_image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: imgInfo.filename,
          subfolder: imgInfo.subfolder,
          type: imgInfo.type,
          model: checkpointSelect.value
        })
      });
      const data = await resp.json();
      if (data.success) {
        displayImage(data.url, data.filename);
        loadGallery();
      }
    } catch (e) {
      console.error("Failed to save image:", e);
    } finally {
      activePromptId = null;
      if (isBatchRunning && (batchInfinite.checked || currentBatchIndex < totalBatches)) {
        currentBatchIndex++;
        progressStatus.textContent = `Batch item saved. Starting #${currentBatchIndex}...`;
        setTimeout(triggerSingleGeneration, 400);
      } else {
        stopBatch();
      }
    }
  }

  function finishGeneration() {
    activePromptId = null;
    progressOverlay.classList.remove("active");
    btnGenerate.disabled = false;
    btnGenerateText.textContent = "Generate Image";
    btnStopBatch.classList.add("hidden");
  }

  function stopBatch() {
    isBatchRunning = false;
    finishGeneration();
    fetch("/api/interrupt", { method: "POST" }).catch(() => {});
  }

  btnStopBatch.addEventListener("click", () => {
    stopBatch();
  });

  // Aspect Ratio
  ratioBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      ratioBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentWidth = parseInt(btn.dataset.w);
      currentHeight = parseInt(btn.dataset.h);
      currentRatio = btn.dataset.ratio;
      resText.textContent = `${currentWidth} × ${currentHeight} px (${currentRatio})`;
    });
  });

  // Tag chips
  document.querySelectorAll(".tag-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const tag = chip.dataset.tag;
      if (!promptInput.value.trim()) {
        promptInput.value = tag;
      } else {
        promptInput.value = promptInput.value.trim().replace(/,\s*$/, "") + ", " + tag;
      }
      promptInput.focus();
    });
  });

  negativePreset.addEventListener("change", () => {
    const val = negativePreset.value;
    if (NEGATIVE_PRESETS[val] !== undefined && val !== "custom") {
      negativePromptInput.value = NEGATIVE_PRESETS[val];
    }
  });

  btnClearPrompt.addEventListener("click", () => {
    promptInput.value = "";
    promptInput.focus();
  });

  stepsInput.addEventListener("input", () => { stepsVal.textContent = stepsInput.value; });
  cfgInput.addEventListener("input", () => { cfgVal.textContent = parseFloat(cfgInput.value).toFixed(1); });

  seedRandom.addEventListener("change", () => {
    seedInput.disabled = seedRandom.checked;
    if (seedRandom.checked) {
      seedInput.value = "";
      seedInput.placeholder = "Random";
    } else {
      seedInput.value = Math.floor(Math.random() * 1000000000);
    }
  });

  // Generate Trigger with Batch Support
  async function triggerSingleGeneration() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      stopBatch();
      return;
    }

    btnGenerate.disabled = true;
    if (batchInfinite.checked || totalBatches > 1) {
      btnStopBatch.classList.remove("hidden");
      btnGenerateText.textContent = batchInfinite.checked 
        ? `Generating (#${currentBatchIndex} ∞)...` 
        : `Generating (${currentBatchIndex}/${totalBatches})...`;
    } else {
      btnGenerateText.textContent = "Generating...";
      btnStopBatch.classList.add("hidden");
    }

    progressOverlay.classList.add("active");
    progressBar.style.width = "5%";
    progressStatus.textContent = batchInfinite.checked
      ? `Queueing batch #${currentBatchIndex} (Heater Mode)...`
      : (totalBatches > 1 ? `Queueing batch ${currentBatchIndex} of ${totalBatches}...` : "Queueing prompt to ComfyUI...");
    progressMeta.textContent = `AMD ROCm 7.2 • RX 6650 XT`;

    const payload = {
      prompt: prompt,
      negative_prompt: negativePromptInput.value.trim(),
      checkpoint: checkpointSelect.value,
      width: currentWidth,
      height: currentHeight,
      steps: parseInt(stepsInput.value),
      cfg: parseFloat(cfgInput.value),
      sampler_name: samplerSelect.value,
      scheduler: schedulerSelect.value,
      seed: seedRandom.checked ? -1 : (parseInt(seedInput.value || -1) + (currentBatchIndex - 1)),
      client_id: clientId
    };

    try {
      const resp = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();

      if (data.success) {
        activePromptId = data.prompt_id;
        pollHistory(activePromptId);
      } else {
        alert("Failed to queue generation: " + (data.error || "Unknown error"));
        stopBatch();
      }
    } catch (e) {
      alert("Network error: " + e.message);
      stopBatch();
    }
  }

  btnGenerate.addEventListener("click", () => {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      promptInput.focus();
      return;
    }
    isBatchRunning = true;
    currentBatchIndex = 1;
    totalBatches = batchInfinite.checked ? Infinity : parseInt(batchCountInput.value);
    triggerSingleGeneration();
  });

  async function pollHistory(pId) {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      if (!activePromptId || activePromptId !== pId || attempts > 180) {
        clearInterval(interval);
        return;
      }

      try {
        const resp = await fetch(`/api/history/${pId}`);
        const data = await resp.json();
        if (data && data[pId] && data[pId].outputs && data[pId].outputs["9"]) {
          clearInterval(interval);
          const images = data[pId].outputs["9"].images;
          if (images && images.length > 0) {
            saveAndDisplayImage(images[0]);
          }
        }
      } catch (e) {}
    }, 1500);
  }

  btnOpenFolder.addEventListener("click", async () => {
    try { await fetch("/api/open_folder", { method: "POST" }); } catch (e) {}
  });

  // Purge / Free VRAM without quitting
  btnUnload.addEventListener("click", async () => {
    btnUnload.disabled = true;
    const prev = btnUnload.textContent;
    btnUnload.textContent = "Purging...";
    try {
      await fetch("/api/unload", { method: "POST" });
      setTimeout(checkStatus, 500);
    } catch (e) {}
    finally {
      btnUnload.disabled = false;
      btnUnload.textContent = prev;
    }
  });

  // Explicit Quit & Offload
  btnQuit.addEventListener("click", async () => {
    if (confirm("Shut down Comfy Studio, stop ComfyUI, and free all VRAM & RAM?")) {
      shutdownOverlay.classList.add("active");
      try {
        await fetch("/api/shutdown", { method: "POST" });
      } catch (e) {}
      setTimeout(() => {
        window.close();
      }, 1000);
    }
  });

  // Send Beacon on Tab/Window Unload
  window.addEventListener("beforeunload", () => {
    navigator.sendBeacon("/api/shutdown");
  });

  btnCopyPrompt.addEventListener("click", () => {
    if (promptInput.value) {
      navigator.clipboard.writeText(promptInput.value);
      const prev = btnCopyPrompt.textContent;
      btnCopyPrompt.textContent = "Copied!";
      setTimeout(() => { btnCopyPrompt.textContent = prev; }, 1500);
    }
  });
});
