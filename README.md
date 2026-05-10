# CityMind — Urban Intelligence System

An AI-powered city simulation system that uses 5 distinct AI techniques to
manage emergency response, road infrastructure, ambulance deployment, and
crime risk prediction across a 10×10 city grid.

## Requirements

```bash
pip install pygame networkx scikit-learn numpy
```

## How to Run

### Visual Interface (Recommended for demo)
```bash
python ui.py
```
Opens an interactive 3D isometric view. Use PLAY/PAUSE/STEP buttons.
Toggle overlays: Roads | Ambulance Coverage | Crime Risk Heatmap.

### Headless Console Simulation
```bash
python main.py
```
Runs the full 20-step simulation and prints all decisions to the console.

## What Each Challenge Does

| # | File | Algorithm | Purpose |
|---|------|-----------|---------|
| 1 | `challenge1_csp.py` | CSP + Backtracking + MRV + Forward Checking | Assign types (Hospital, Residential, etc.) to all 100 grid cells |
| 2 | `challenge2_mst.py` | Kruskal's MST + Redundancy Edge | Build the cheapest road network; guarantee 2 independent hospital-depot paths |
| 3 | `challenge3_ga.py` | Genetic Algorithm | Place 3 ambulances to minimise worst-case response time |
| 4 | `challenge4_astar.py` | A* Search | Route medical team to all civilians; reroute in real time when roads flood |
| 5 | `challenge5_ml.py` | K-Means + Random Forest | Predict crime risk per neighbourhood; feed scores into routing cost |

## Simulation Step Sequence (each of 20 steps)

```
Step 1 — Flood:         0-2 random roads are blocked (excluding hospital-depot edge)
Step 2 — Route (A*):    Team navigates to all 6 civilians nearest-first;
                         reroutes automatically if a road floods mid-journey
Step 3 — Every 5 steps: ML refreshes risk scores → GA repositions ambulances
Step 4 — Every 3 steps: 0-1 flooded roads unblocked (flood waters recede)
```

## Project Structure

```
main.py              — Headless simulation runner (authoritative step logic)
ui.py                — Pygame visual interface (mirrors main.py step logic)
city_graph.py        — Shared CityGraph data structure used by all modules
challenge1_csp.py    — CSP city layout planner
challenge2_mst.py    — MST road network builder
challenge3_ga.py     — GA ambulance placement
challenge4_astar.py  — A* emergency router
challenge5_ml.py     — ML crime risk pipeline
```

## Shared City Graph

All five challenges read from and write to **one shared `CityGraph` object**.
- Challenge 1 sets location types (Hospital, Residential, Industrial, …)
- Challenge 2 sets road edges and base costs
- Challenge 5 writes `risk_index` per node
- Challenge 3 & 4 read `effective_cost = base_cost × (1 + (risk_u + risk_v)/2)`

Any change in one module is immediately visible to all others.