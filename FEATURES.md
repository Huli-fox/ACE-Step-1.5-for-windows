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

## Enhanced Model Selector

**Branch:** `qinglong`  
**Status:** ✅ Merged

Dynamic model discovery and hot-swap switching. The model dropdown auto-populates from all installed checkpoints and supports switching the active DiT model without restarting the server.

### What's included

| File | Description |
|------|-------------|
| `acestep/handler.py` | `switch_dit_model()` — hot-swaps DiT weights, handles LoRA unload, VRAM cleanup, attention fallback |
| `acestep/api_server.py` | `GET /v1/models/list` — scans `checkpoints/` for installed models; `POST /v1/models/switch` — triggers model swap |
| `ace-step-ui/server/src/routes/models.ts` | Express proxy routes for model list, status, and switch |
| `ace-step-ui/server/src/routes/generate.ts` | Updated proxy target to `/v1/models/list` |
| `ace-step-ui/services/api.ts` | `getModels()` / `switchModel()` frontend API methods |
| `ace-step-ui/components/CreatePanel.tsx` | Mismatch banner, switch button, dynamic dropdown |
| `LAUNCH.bat` | Added server TypeScript rebuild step before startup |

### How it works

1. On startup, the Python API scans `checkpoints/` for all `acestep-v15-*` directories
2. The frontend fetches the installed model list via `/api/generate/models`
3. If the selected model differs from the loaded model, an amber mismatch banner appears
4. Clicking "Switch" calls `POST /v1/models/switch` which hot-swaps the DiT model (unloads LoRA, frees VRAM, loads new weights)
5. A fallback list of the 6 default ACE-Step models is shown while the Python API starts

---

## Simple Shutdown

**Branch:** `feature/Simple-Shutdown`  
**Status:** ✅ Merged

Quit button in the sidebar that gracefully shuts down all ACE-Step processes (Python API, Vite frontend, Express backend, and their hosting terminal windows).

### What's included

| File | Description |
|------|-------------|
| `ace-step-ui/server/src/index.ts` | `POST /api/shutdown` — snapshots the process table via `Get-CimInstance`, walks the process tree to find ancestor shells, kills everything |
| `ace-step-ui/components/Sidebar.tsx` | Power icon quit button (red styling, appears at sidebar bottom) |
| `ace-step-ui/App.tsx` | ConfirmDialog wiring + "ACE-Step has shut down" overlay |

### How it works

1. Click the red **Quit** button at the bottom of the sidebar
2. A confirmation dialog appears — "Are you sure you wish to shut down ACE-Step?"
3. On confirm, `POST /api/shutdown` is called:
   - Snapshots the entire Windows process table in one `Get-CimInstance Win32_Process` call (~200ms)
   - Finds PIDs on ports 8001 (Python API) and 3000 (Vite) via `netstat`
   - Walks UP the process tree to find ancestor CMD/PowerShell/conhost windows
   - Kills all collected PIDs with `taskkill /F /T`
   - Express process exits last
4. Browser shows a "You may now close this tab" overlay

---

## Persistent Settings

**Branch:** `feature/Persistent-Settings`  
**Status:** ✅ Merged

Toggleable localStorage persistence for all generation settings. Disabled by default — once enabled in Settings, every parameter survives page refresh.

### What's included

| File | Description |
|------|-------------|
| `ace-step-ui/hooks/usePersistedState.ts` | `usePersistedState` hook — drop-in `useState` replacement with auto-persistence gated by `ace-persist-enabled` flag |
| `ace-step-ui/components/SettingsModal.tsx` | "Persistent Settings" toggle section with enable/disable switch |
| `ace-step-ui/components/CreatePanel.tsx` | ~35 useState calls converted to usePersistedState |

### How it works

1. Open **Settings** → toggle **"Remember my settings"** ON
2. All generation parameters (style, lyrics, BPM, model, LoRA path, inference settings, etc.) are now auto-saved to localStorage
3. Page refresh → all settings restored
4. Toggle OFF → all saved settings cleared, page reloads with defaults
5. Future features: use `usePersistedState('key', default)` instead of `useState(default)` — one-line change

---

## Track List Updates

**Branch:** `feature/Track-List-Updates`  
**Status:** ✅ Merged

A collection of track list UX improvements, bug fixes, and a new bulk-delete feature.

### What's included

| File | Description |
|------|-------------|
| `ace-step-ui/components/WaveformVisualizer.tsx` | Replaced upstream fixed-width bar rendering with dynamic spacing so the waveform fills the full progress bar width. Includes shared `AudioContext`, LRU cache (30 entries), and `AbortController` for proper cleanup. |
| `ace-step-ui/server/src/routes/generate.ts` | Fixed generation progress display — parses tqdm-style `progress_text` from the Python API. Added per-job queue detection so queued jobs don't leak the running job's progress. |
| `ace-step-ui/components/CreatePanel.tsx` | "Queue Next" button now uses i18n key instead of hardcoded English text. |
| `ace-step-ui/i18n/translations.ts` | Added `queueNext`, `deleteAllTracks`, `deleteAllTracksConfirm`, `allTracksDeleted`, `deleteAllFailed` keys for all 4 languages (en, zh, ja, ko). |
| `ace-step-ui/components/SongList.tsx` | Removed `createdAt` DESC sort from `listItems` so songs maintain their order from state. Added `onDeleteAll` prop with a trash icon button in the header bar. |
| `ace-step-ui/App.tsx` | Removed the `refreshSongsList` sort that caused completed songs to jump to the top. Completion now does in-place merge instead of full list reload. Added `handleDeleteAll` with confirmation dialog. |
| `ace-step-ui/server/src/routes/songs.ts` | Added `DELETE /api/songs/all` endpoint — deletes all user songs and associated audio/cover files from storage. |
| `ace-step-ui/services/api.ts` | Added `deleteAllSongs()` API client method. |
| `LAUNCH.bat`, `START.bat`, `ace-step-ui/start.bat`, `ace-step-ui/start-all.bat` | Added `/min` flag to all `start` commands so spawned terminal windows launch minimized. |

### Changes in detail

- **Waveform alignment** — Bars now fill the entire progress bar width using dynamic step calculation instead of fixed `barWidth=2, gap=1`.
- **Generation progress** — The Express backend now parses tqdm output (`14%|##5| 27/200 [00:06<00:42, 4.10steps/s]`) to extract percentage, ETA, and step count.
- **Queue progress bleed fix** — The Python API maps both `queued` and `running` to status code `0` and shares a global `log_buffer.last_message`. The Express status handler now checks the per-job `stage` field in the result data to detect queued jobs and returns `status: 'queued'` with `progress: 0` instead of leaking the running job's tqdm output.
- **Track reordering fix** — Two sorts were causing completed songs to jump to the top: one in `refreshSongsList` (App.tsx) and one in `listItems` (SongList.tsx). Both removed. Completion now does an in-place merge that preserves existing order.
- **Delete All Tracks** — Trash icon button in the track list header (next to Select/Filter). Shows a confirmation dialog with the count of tracks. Calls `DELETE /api/songs/all` which deletes all audio/cover files from storage and removes all DB rows.
- **Minimized windows** — All spawned terminal windows (Python API, Express, Vite) now launch minimized via `/min` flag.

---

## Advanced Multi-Adapter System

**Branch:** `feature/advanced-adapters`  
**Status:** 🚧 In Progress

Slot-based multi-adapter loading (up to 4 simultaneous LoRA/LoKr adapters) with per-slot scaling and per-module-group scaling (Self-Attn, Cross-Attn, MLP). Uses weight-space merging approach. Existing basic single-adapter UI is preserved — the advanced system is behind an opt-in "Advanced" checkbox.

### What's included

| File | Description |
|------|-------------|
| `acestep/core/generation/handler/lora/advanced_adapter_mixin.py` | **[NEW]** `AdvancedAdapterMixin` — delta extraction, weight-space merging (`base + Σ(scale × group_scale × delta)`), slot management |
| `acestep/core/generation/handler/lora_manager.py` | Import + export `AdvancedAdapterMixin` |
| `acestep/handler.py` | Added `AdvancedAdapterMixin` to MRO, init state (`_adapter_slots`, `_next_slot_id`, `_merged_dirty`, `lora_group_scales`) |
| `acestep/api_server.py` | 3 new endpoints, updated `load`/`unload` for slot param, new request models |
| `ace-step-ui/server/src/routes/lora.ts` | 3 new routes: `GET /list-files` (folder scanner), `POST /group-scales`, `POST /slot-group-scales` |
| `ace-step-ui/services/api.ts` | `listLoraFiles()`, `setGroupScales()`, `setSlotGroupScales()`, updated `loadLora`/`unloadLora` for slot support |
| `ace-step-ui/components/CreatePanel.tsx` | Advanced toggle, folder browser, slot cards with per-slot scale + expandable per-group sliders |

### How it works

1. Open the **LoRA** panel and check **Advanced (Multi-Adapter)**
2. Enter an adapter folder path → click **Scan** → available `.safetensors` files appear
3. Click **Load** on any adapter → it's loaded into a slot, delta extracted via weight-space merging
4. Each slot card shows: adapter name, type badge (LoRA/LoKr), overall scale slider (0–2)
5. Expand **Groups** on a slot → independent Self-Attn, Cross-Attn, MLP sliders (0–2)
6. Load additional adapters (up to 4) — all merge simultaneously: `decoder = base + Σ(slot_scale × group_scale × delta)`
7. Per-adapter group scale settings are persisted in localStorage by adapter filename
8. Uncheck "Advanced" → original basic single-adapter UI appears unchanged

### Architecture note

Basic mode uses PEFT runtime hooks (existing). Advanced mode uses **weight-space merging**: backs up base decoder to CPU (~1.5GB), extracts each adapter as a delta, applies `base + Σ(scaled deltas)` at inference. Re-merge takes ~1s on scale change.

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

