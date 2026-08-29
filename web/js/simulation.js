// simulation.js — full 20-step simulation with 3 ambulances, floods, rescue
import { GRID_ROWS, GRID_COLS, zoneGrid, roadEdges, primaryHospital, primaryDepot } from './cityData.js';

const AMBULANCE_COLORS = [0x3cff8c, 0xff6b3c, 0x44aaff];

export class SimulationController {
    constructor(vehicles, pathViz, floods, heatmap, ui) {
        this.vehicles = vehicles;
        this.pathViz = pathViz;
        this.floods = floods;
        this.heatmap = heatmap;
        this.ui = ui;

        this.step = 0;
        this.totalSteps = 20;
        this.playing = false;
        this.stepTimer = 0;
        this.stepInterval = 3.0;
        this.civiliansRescued = 0;
        this.totalCivilians = 12;
        this.blockedRoads = [];
        this.floodCount = 0;

        this.civilians = this._pickCivilians();
        this.ambAssignments = [
            { ambIdx: 0, civIndices: [0, 1, 2, 3], startPos: [1, 4] },
            { ambIdx: 1, civIndices: [4, 5, 6, 7], startPos: [6, 4] },
            { ambIdx: 2, civIndices: [8, 9, 10, 11], startPos: [9, 8] },
        ];
        this.ambCurrentIdx = [0, 0, 0];
        this.ambTeamPos = this.ambAssignments.map(a => [...a.startPos]);

        this._bindButtons();
    }

    _pickCivilians() {
        const civs = [];
        const occupied = new Set([
            primaryHospital.join(','), primaryDepot.join(',')
        ]);
        const rng = this._seededRandom(42);
        while (civs.length < this.totalCivilians) {
            const r = Math.floor(rng() * GRID_ROWS);
            const c = Math.floor(rng() * GRID_COLS);
            const key = `${r},${c}`;
            if (!occupied.has(key) && zoneGrid[r][c] === 'Residential') {
                civs.push([r, c]);
                occupied.add(key);
            }
        }
        return civs;
    }

    _seededRandom(seed) {
        let s = seed;
        return () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; };
    }

    _bindButtons() {
        if (!this.ui) return;
        this.ui.on('play', () => this.play());
        this.ui.on('pause', () => this.pause());
        this.ui.on('reset', () => this.reset());
    }

    play() {
        this.playing = true;
        if (this.step === 0) {
            this.step = 1;
            this._runStep();
        }
        if (this.ui) this.ui.showToast('Simulation started', 'success');
    }

    pause() {
        this.playing = false;
        if (this.ui) this.ui.showToast('Simulation paused', 'warning');
    }

    reset() {
        this.playing = false;
        this.step = 0;
        this.stepTimer = 0;
        this.civiliansRescued = 0;
        this.floodCount = 0;
        this.blockedRoads = [];
        this.civilians = this._pickCivilians();
        this.ambCurrentIdx = [0, 0, 0];
        this.ambTeamPos = this.ambAssignments.map(a => [...a.startPos]);

        this.floods.clearAll();
        this.pathViz.clearAll();

        this.vehicles.teleportTo(0, 1, 4);
        this.vehicles.teleportTo(1, 6, 4);
        this.vehicles.teleportTo(2, 9, 8);

        if (this.ui) {
            this.ui.updateStep(0);
            this.ui.updateStats({ rescued: 0, floods: 0 });
            this.ui.addLogEntry('System', 'Simulation reset — ready', 'system');
        }
    }

    _runStep() {
        if (this.step > this.totalSteps) {
            this.playing = false;
            if (this.ui) this.ui.showToast('All 20 steps complete!', 'success');
            return;
        }
        this.stepTimer = 0;

        this._doFlood();

        this.ambAssignments.forEach((assignment, ambSlot) => {
            this._routeAmbulance(ambSlot, assignment);
        });

        if (this.step % 3 === 0 && this.blockedRoads.length > 0) {
            this._doRecovery();
        }

        if (this.ui) {
            this.ui.updateStep(this.step);
            this.ui.updateStats({ rescued: this.civiliansRescued, floods: this.floodCount });
        }

        this.step++;
    }

    _doFlood() {
        const rng = this._seededRandom(this.step * 7 + 13);
        const numFloods = Math.min(2, Math.floor(rng() * 3));

        for (let i = 0; i < numFloods; i++) {
            if (this.blockedRoads.length >= 12) return;
            const edgeIdx = Math.floor(rng() * roadEdges.length);
            const edge = roadEdges[edgeIdx];
            const key = `${edge[0][0]},${edge[0][1]}-${edge[1][0]},${edge[1][1]}`;
            if (!this.blockedRoads.find(b => b.key === key)) {
                this.blockedRoads.push({ key, edge: [...edge] });
                this.floods.addFlood(edge[0][0], edge[0][1], edge[1][0], edge[1][1], `s${this.step}f${i}`);
                this.floodCount++;
                if (this.ui) {
                    this.ui.addLogEntry('Flood', `Step ${this.step}: road (${edge[0]}) ↔ (${edge[1]}) flooded`, 'flood');
                }
            }
        }
    }

    _doRecovery() {
        const recovered = this.blockedRoads.pop();
        if (recovered) {
            const [a, b] = recovered.edge;
            this.floods.removeFloodByEdge(a[0], a[1], b[0], b[1]);
            this.floodCount = Math.max(0, this.floodCount - 1);
            if (this.ui) {
                this.ui.addLogEntry('Restore', `Step ${this.step}: road (${a}) ↔ (${b}) restored`, 'restore');
            }
        }
    }

    _routeAmbulance(ambSlot, assignment) {
        if (this.ambCurrentIdx[ambSlot] >= assignment.civIndices.length) return;

        const civIdx = assignment.civIndices[this.ambCurrentIdx[ambSlot]];
        if (civIdx >= this.civilians.length) return;
        const civ = this.civilians[civIdx];

        const path = this._bfsPath(this.ambTeamPos[ambSlot], civ);
        if (path.length === 0) {
            this.ambCurrentIdx[ambSlot]++;
            return;
        }

        const color = AMBULANCE_COLORS[ambSlot];
        this.pathViz.showPath(path, color, `amb${ambSlot}_s${this.step}`);

        this.vehicles.setPath(ambSlot, path);

        this.ambTeamPos[ambSlot] = [...civ];
        this.civiliansRescued++;

        if (this.ui) {
            const ambNames = ['Alpha', 'Bravo', 'Charlie'];
            this.ui.addLogEntry('Route',
                `Amb ${ambNames[ambSlot]} → civilian #${this.civiliansRescued} at (${civ}) [${path.length} hops]`,
                'system'
            );
        }

        this.ambCurrentIdx[ambSlot]++;
    }

    _bfsPath(start, goal) {
        if (start[0] === goal[0] && start[1] === goal[1]) return [start];
        const visited = new Set([start.join(',')]);
        const queue = [[start]];
        while (queue.length > 0) {
            const pathSoFar = queue.shift();
            const cur = pathSoFar[pathSoFar.length - 1];
            for (const [dr, dc] of [[0,1],[0,-1],[1,0],[-1,0]]) {
                const nr = cur[0] + dr, nc = cur[1] + dc;
                if (nr < 0 || nr >= GRID_ROWS || nc < 0 || nc >= GRID_COLS) continue;
                const key = `${nr},${nc}`;
                if (visited.has(key)) continue;
                const blocked = this.blockedRoads.some(b => {
                    const [a, bE] = b.edge;
                    return (a[0]===cur[0]&&a[1]===cur[1]&&bE[0]===nr&&bE[1]===nc) ||
                           (bE[0]===cur[0]&&bE[1]===cur[1]&&a[0]===nr&&a[1]===nc);
                });
                if (blocked) continue;
                visited.add(key);
                const newPath = [...pathSoFar, [nr, nc]];
                if (nr === goal[0] && nc === goal[1]) return newPath;
                queue.push(newPath);
            }
        }
        return [];
    }

    update(delta) {
        if (!this.playing) return;
        this.stepTimer += delta;
        if (this.stepTimer >= this.stepInterval) {
            this._runStep();
        }
    }
}
