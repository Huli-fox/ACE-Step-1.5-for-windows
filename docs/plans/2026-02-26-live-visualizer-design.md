# Live Music Visualizer — Design Document

## Goal

Repurpose the existing video-export visualization engine (10 presets, 13 effects, particles) into a **live, audio-reactive visualizer** that:

1. **Replaces the static cover art** in the Song Details sidebar when music is playing
2. **Renders a dimmed version behind the song list** as an ambient background (toggleable)
3. **Goes full-screen** with a minimal auto-hiding HUD (Winamp/MilkDrop style)

## Design Decisions

| Decision | Choice |
|---|---|
| Cover art ↔ visualizer | **Toggle** — cover art shown when stopped, smooth crossfade to visualizer when playing |
| Songlist background | **Same preset, dimmed** — renders behind track rows, toggleable in Settings |
| Preset selection | **Compact dropdown on canvas** — palette icon overlaid on the visualizer |
| Random mode | **Auto-cycle presets every ~30 seconds** — included as a "Random" option in the picker |
| Full-screen mode | **Canvas + minimal HUD** — song title, artist, play/pause/skip, fades out after inactivity, reappears on mouse move |

## Architecture

### Core: Shared Audio Analysis Service

The main player audio element (`App.tsx`) currently has no `AudioContext`. We need a **singleton service** that:

- Lazily creates an `AudioContext` + `AnalyserNode` on first visualizer activation
- Connects to the existing `HTMLAudioElement` via `createMediaElementSource()` (only once — this is a one-shot Web Audio API call)
- Exposes `getFrequencyData()` and `getTimeDomainData()` for any consumer
- Stores in React Context so both sidebar and songlist can share it

### Core: Extracted Visualization Renderer

The 10 drawing functions + effects + particles currently live inside `VideoGeneratorModal.tsx` as nested functions. We extract them into a **standalone module** that:

- Takes a canvas context, dimensions, frequency data, time, and config
- Returns nothing (draws directly to the canvas)
- Is importable by the sidebar visualizer, songlist background, full-screen view, AND the existing VideoGeneratorModal

### Components

```
AudioAnalysisContext          (new context — singleton AudioContext + AnalyserNode)
  │
  ├── LiveVisualizer          (new component — canvas + render loop + preset picker)
  │   ├── Used in RightSidebar (replaces cover art when playing)
  │   ├── Used in SongList     (dimmed background, when enabled)
  │   └── Used in FullscreenVisualizer (full-screen overlay)
  │
  ├── FullscreenVisualizer    (new component — portal, fullscreen API, HUD overlay)
  │
  └── visualizerEngine.ts     (new module — extracted draw functions from VideoGeneratorModal)
```

### Preset Picker UI

- Small palette icon (🎨) overlaid on bottom-right of the canvas
- On click: compact dropdown listing 10 presets + "Random" at the top
- Selection stored in `localStorage` and shared via context/state
- When "Random" is selected: timer rotates through presets every ~30 seconds

### Full-Screen HUD

- Triggered by a maximize icon on the visualizer canvas
- Uses `document.fullscreenElement` API on a portal container
- HUD overlay: song title, artist, progress bar, play/pause/next/prev
- HUD fades out after 3 seconds of mouse inactivity
- Mouse movement or click re-shows the HUD
- Escape or click-to-exit exits full-screen

### Settings Integration

Add to the existing `SettingsModal.tsx` under a "Visualizer" section:
- **Songlist background visualizer** — toggle on/off (default: off)
- Future: visualizer color customization could go here

## Data Flow

```
HTMLAudioElement (App.tsx audioRef) 
  → AudioContext.createMediaElementSource()
  → AnalyserNode
  → getByteFrequencyData() per frame
  → visualizerEngine.renderFrame(ctx, data, config)
  → Canvas (sidebar / songlist / fullscreen)
```

## Key Constraints

- `createMediaElementSource()` can only be called **once** per element — must be managed carefully
- The `AudioContext` must be created from a user gesture (browser autoplay policy) — we defer creation until the first play action
- Canvas rendering at 60fps is cheap for a single small canvas but may need throttling if both sidebar + songlist + fullscreen are all active simultaneously
- The extracted engine must remain backward-compatible with `VideoGeneratorModal`'s offline rendering pipeline
