# CityMind 3D Web Frontend

Three.js-based 3D visualization of the CityMind urban emergency simulation.

## Quick Start

Open `web/index.html` in any modern browser. No server required.

## Controls

| Control | Action |
|---------|--------|
| **Play** button / **Space** | Start simulation |
| **Pause** button / **P** | Pause simulation |
| **Reset** button / **R** | Reset simulation |
| **1-7** keys | Switch camera views |
| **Mouse drag** | Orbit camera |
| **Scroll** | Zoom in/out |

## Camera Views

1. Aerial (top-down)
2. Perspective (default angled)
3. Street North
4. Street South
5. Street East
6. Street West
7. Close-up

## Features

- 3 ambulances (Alpha, Bravo, Charlie) rescuing 12 civilians
- BFS pathfinding along road network
- Flood events blocking roads
- Risk heatmap overlay
- Day/night cycle with street lamps
- Animated emergency lights on ambulances
- Event log with timestamps
- Speed control slider

## File Structure

```
web/
  index.html          — Main HTML with control panel
  style.css           — All styling
  js/
    main.js           — Scene setup and orchestration
    cityData.js       — City grid data (zones, roads, positions)
    terrain.js        — 3D ground tiles and roads
    buildings.js      — 7 building types (Hospital, School, etc.)
    lights.js         — Day/night cycle lighting
    camera.js         — 7 camera presets with smooth transitions
    vehicles.js       — 3D ambulance models with movement
    path.js           — Glowing path visualization
    flood.js          — Animated flood water effects
    heatmap.js        — Risk heatmap overlay
    simulation.js     — 20-step simulation controller
    civilians.js      — Civilian SOS markers
    ui.js             — Control panel event handling
```
