# ACE-Step 1.5 for Windows — Enhanced Fork

An enhanced fork of [sdbds/ACE-Step-1.5-for-windows](https://github.com/sdbds/ACE-Step-1.5-for-windows) with a rebuilt UI experience, multi-adapter support, and quality-of-life improvements for music generation with [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5).

<img width="2062" height="952" alt="image" src="https://github.com/user-attachments/assets/6e682194-99f2-4267-b412-1b5198720b87" />

---

## ✨ New Features

> Full details and implementation notes in [FEATURES.md](FEATURES.md).

### 🧠 Advanced Guidance & Solvers
Total control over the generation pipeline with 7 unique mathematical guidance modes (APG, ADG, PAG, Plain CFG, CFG++, Dynamic CFG, Rescaled CFG) and 4 ODE solver algorithms (Euler, Heun, DPM++ 2M, RK4). Includes 40+ multilingual educational tooltips explaining every generation parameter.

### 🎛️ Advanced Multi-Adapter System
Load up to **4 LoRA/LoKr adapters simultaneously** with independent per-slot scale sliders and per-module-group scaling (Self-Attn, Cross-Attn, MLP). Uses weight-space merging for zero-hook inference. Per-adapter settings persist across sessions. Includes a built-in **file browser** for scanning and loading `.safetensors` files from a configurable folder.

### 🚀 One-Click Launcher
Double-click `LAUNCH.bat` → animated loading screen monitors all three services (Python API, Express backend, Vite frontend) and auto-redirects when ready. No manual terminal management required.

### 🔄 Hot-Swap Model Selector
Live model switching without restarting the server. The dropdown auto-discovers all installed checkpoints and shows a mismatch banner if the selected model differs from the loaded one.

### 💾 Persistent Settings
All generation settings (style, lyrics, BPM, model, adapter paths, scales, inference params) survive page refresh via localStorage. Toggle on/off in Settings.

### 🎵 Track List Improvements
- Full-width waveform visualizer with shared AudioContext and LRU cache
- Real-time generation progress (parsed from tqdm output)
- Queue system with per-job progress isolation
- Bulk delete all tracks
- Tracks maintain chronological order (no jumping on completion)

### ⏻ Simple Shutdown
Quit button in the sidebar gracefully shuts down all processes (Python API, Vite, Express, and their hosting terminal windows) with a single click.

---

## Upstream Features

All features from the upstream [sdbds/ACE-Step-1.5-for-windows](https://github.com/sdbds/ACE-Step-1.5-for-windows) are preserved:

- Complete style search with 936 styles synchronized from Suno's explorer
- Song parameter history — reuse any previous generation's settings
- Four-language localization (English, Chinese, Japanese, Korean)
- LoRA and LoKr training support with memory offloading optimization
- Basic single-adapter LoRA/LoKr loading

---

## 🔧 Setting up the Environment for Windows

Give unrestricted script access to PowerShell so venv can work:

- Open an administrator PowerShell window
- Type `Set-ExecutionPolicy Unrestricted` and answer A
- Close admin PowerShell window

## Installation

Clone the repo with `--recurse-submodules`:

```
git clone --recurse-submodules https://github.com/scragnog/ACE-Step-1.5-for-windows.git -b qinglong
```

> ⚠️ **MUST USE `--recurse-submodules`** — the UI is a git submodule.

### Install Dependencies

Run the following PowerShell script:
```powershell
./1、install-uv-qinglong.ps1
```

### (Optional) VS Studio 2022 for torch compile
Download from Microsoft official link:
https://aka.ms/vs/17/release/vs_community.exe

Install C++ desktop and language package with English (especially for Asian computers).

### FFMPEG

https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.0-latest-win64-gpl-shared-8.0.zip

Use the shared version for ffmpeg.

### Change Default Model
Copy `.env.sample` and rename to `.env`, then change the model name to your preference.

### Linux
1. First install PowerShell:
```bash
./0、install pwsh.sh
```
2. Then run the installation script using PowerShell:
```powershell
sudo pwsh ./1、install-uv-qinglong.ps1
```
Use `sudo pwsh` if you are on Linux without root user.

## Usage

### Option A: One-Click Launcher (Recommended)

Double-click **`LAUNCH.bat`** — this will:

1. Open a loading screen in your browser immediately
2. Install UI dependencies if needed
3. Start the Python API server and UI servers
4. Auto-redirect to the app once all services are ready

The loading screen shows real-time status for each service (Python API, Express backend, Vite frontend) and redirects automatically when everything is loaded.

> **Alternative:** `START.bat` does the same thing without the loading screen — it opens three separate command windows and launches the browser directly after a short delay.

### Option B: Manual Launch (PowerShell Scripts)

If you prefer to start services independently:

```powershell
# Terminal 1 — Start the Python API backend
3、run_server.ps1

# Terminal 2 — Start the UI (Express + Vite frontend)
4、run_npmgui.ps1
```

Then open http://localhost:3000 in your browser.

---

## Credits

- **ACE-Step 1.5** — [ace-step/ACE-Step-1.5](https://github.com/ace-step/ACE-Step-1.5) (original model & backend)
- **Windows integration** — [sdbds/ACE-Step-1.5-for-windows](https://github.com/sdbds/ACE-Step-1.5-for-windows) (upstream fork)
- **Frontend** — [fspecii/ace-step-ui](https://github.com/fspecii/ace-step-ui) (original UI)
