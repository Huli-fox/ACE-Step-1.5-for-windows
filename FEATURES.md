# New Features

This document tracks all new features added on top of the upstream [sdbds/ACE-Step-1.5-for-windows](https://github.com/sdbds/ACE-Step-1.5-for-windows) (qinglong branch).

> **Workflow:** Each feature is developed on a dedicated branch (`feature/<name>`), committed, pushed to [scragnog/ACE-Step-1.5-for-windows](https://github.com/scragnog/ACE-Step-1.5-for-windows), and merged into the default branch (`qinglong`).

---

## One-Click Launcher

**Branch:** `feature/launch-system`  
**Status:** ✅ Merged

Single-click launch experience with a loading screen that waits for all services to be ready before opening the UI.

### What's included

| File | Description |
|------|-------------|
| `LAUNCH.bat` | One-click launcher — opens loading screen, starts API + UI servers |
| `START.bat` | Alternative launcher without loading screen |
| `loading.html` | Animated loading page with real-time service status checklist |

### How it works

1. `LAUNCH.bat` opens `loading.html` in the browser immediately
2. Starts the Python API server (`3、run_server.ps1`) and UI servers (`4、run_npmgui.ps1`) in the background
3. The loading page polls three services:
   - **Python API** — `/v1/models/status` (waits for `active_model` to be non-null)
   - **Express backend** — `localhost:3001/health`
   - **Vite frontend** — `localhost:3000`
4. Auto-redirects to the app once all three are confirmed ready

### API changes

- Added `GET /v1/models/status` endpoint to `acestep/api_server.py` (no auth required)
- `ace-step-ui/start.bat` checks `ACESTEP_NO_BROWSER` env var to avoid opening a duplicate browser tab

---

<!-- 
## [Next Feature Name]

**Branch:** `feature/...`  
**Status:** 🚧 In Progress / ✅ Merged

Brief description.

### What's included
- ...

### How it works
- ...
-->
