// simulation.js — step-by-step simulation controller
import { GRID_ROWS, GRID_COLS, zoneGrid, roadEdges, ambulancePositions, primaryHospital, primaryDepot } from './cityData.js';

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
        this.stepInterval = 2.0; // seconds per step
        this.civiliansRescued = 0;
        this.blockedRoads = [];
        this.currentPath = [];
        this.teamPos = [...primaryDepot];
        this.civilians = this._pickCivilians();
        this.civIndex = 0;
        this.floodCount = 0;

        this._bindButtons();
    }

    _pickCivilians() {
        const civilians = [];
        const occupied = new Set([
            primaryHospital.join(','), primaryDepot.join(','),
            ...ambulancePositions.map(a => a.join(','))
        ]);
        const rng = this._seededRandom(42);
        while (civilians.length < 6) {
            const r = Math.floor(rng() * GRID_ROWS);
            const c = Math.floor(rng() * GRID_COLS);
            const key = `${r},${c}`;
            if (!occupied.has(key) && zoneGrid[r][c] === 'Residential') {
                civilians.push([r, c]);
                occupied.add(key);
            }
        }
        return civilians;
    }

    _seededRandom(seed) {
        let s = seed;
        return () => {
            s = (s * 16807 + 0) % 2147483647;
            return (s - 1) / 2147483646;
        };
    }

    _bindButtons() {
        if (this.ui) {
            this.ui.on('play', () => this.play());
            this.ui.on('pause', () => this.pause());
            this.ui.on('reset', () => this.reset());
        }
    }

    play() {
        this.playing = true;
        if (this.step === 0) this.step = 1;
        this._runStep();
    }

    pause() {
        this.playing = false;
    }

    reset() {
        this.playing = false;
        this.step = 0;
        this.stepTimer = 0;
        this.civiliansRescued = 0;
        this.floodCount = 0;
        this.civIndex = 0;
        this.teamPos = [...primaryDepot];
        this.blockedRoads = [];
        this.currentPath = [];
        this.floods.clearAll();
        this.pathViz.clearAll();
        this.vehicles.teleportTo(0, primaryDepot[0], primaryDepot[1]);
        this.vehicles.teleportTo(1, ambulancePositions[1][0], ambulancePositions[1][1]);
        this.vehicles.teleportTo(2, ambulancePositions[2][0], ambulancePositions[2][1]);
        if (this.ui) {
            this.ui.updateStep(0);
            this.ui.updateStats({ rescued: 0, floods: 0 });
            this.ui.addLogEntry('System', 'Simulation reset', 'system');
            this.ui.showToast('Simulation reset', 'info');
        }
    }

    _runStep() {
        if (this.step > this.totalSteps) {
            this.playing = false;
            if (this.ui) this.ui.showToast('Simulation complete!', 'success');
            return;
        }

        this.stepTimer = 0;

        // 1) Flood event
        this._doFlood();

        // 2) Route to next civilian
        this._doRoute();

        // 3) Every 5 steps: update stats
        if (this.step % 5 === 0) {
            if (this.ui) this.ui.showToast(`Step ${this.step}: Risk scores refreshed`, 'info');
        }

        // 4) Every 3 steps: road recovery
        if (this.step % 3 === 0 && this.blockedRoads.length > 0) {
            this._doRecovery();
        }

        if (this.ui) {
            this.ui.updateStep(this.step);
            this.ui.updateStats({
                rescued: this.civiliansRescued,
                floods: this.floodCount,
            });
        }

        this.step++;
    }

    _doFlood() {
        if (this.blockedRoads.length >= roadEdges.length * 0.3) return;

        const rng = this._seededRandom(this.step * 7 + 13);
        const numFloods = Math.floor(rng() * 3);

        for (let i = 0; i < numFloods; i++) {
            const edgeIdx = Math.floor(rng() * roadEdges.length);
            const edge = roadEdges[edgeIdx];
            const key = `${edge[0][0]},${edge[0][1]}-${edge[1][0]},${edge[1][1]}`;

            if (!this.blockedRoads.find(b => b.key === key)) {
                this.blockedRoads.push({ key, edge: [...edge] });
                this.floods.addFlood(edge[0][0], edge[0][1], edge[1][0], edge[1][1], `step${this.step}_f${i}`);
                this.floodCount++;
                if (this.ui) {
                    this.ui.addLogEntry('Flood', `Road (${edge[0]}) ↔ (${edge[1]}) flooded`, 'flood');
                }
            }
        }
    }

    _doRecovery() {
        const recovered = this.blockedRoads.pop();
        if (recovered) {
            const [a, b] = recovered.edge;
            const fid = `step${this.step}_rec`;
            this.floods.removeFloodByEdge(a[0], a[1], b[0], b[1]);
            this.floodCount = Math.max(0, this.floodCount - 1);
            if (this.ui) {
                this.ui.addLogEntry('Restore', `Road (${a}) ↔ (${b}) restored`, 'restore');
            }
        }
    }

    _doRoute() {
        if (this.civIndex >= this.civilians.length) {
            if (this.ui) this.ui.showToast('All civilians rescued!', 'success');
            return;
        }

        const civ = this.civilians[this.civIndex];
        const path = this._bfsPath(this.teamPos, civ);

        if (path.length === 0) {
            if (this.ui) this.ui.addLogEntry('Route', `Cannot reach civilian at (${civ})`, 'risk');
            this.civIndex++;
            return;
        }

        this.currentPath = path;

        // show path
        const color = this.civIndex % 2 === 0 ? 0x3cff8c : 0xff6b3c;
        this.pathViz.showPath(path, color, `civ${this.civIndex}`);

        // move ambulance 0 along the path
        this.vehicles.setPath(0, path);

        // move team position to civilian
        this.teamPos = [...civ];
        this.civiliansRescued++;

        if (this.ui) {
            this.ui.addLogEntry('Route', `Team routing to civilian ${this.civiliansRescued} at (${civ}) — ${path.length} hops`, 'system');
            this.ui.showToast(`Rescuing civilian ${this.civiliansRescued}...`, 'info');
        }

        this.civIndex++;
    }

    _bfsPath(start, goal) {
        if (start[0] === goal[0] && start[1] === goal[1]) return [start];

        const visited = new Set([start.join(',')]);
        const queue = [[start]];

        while (queue.length > 0) {
            const pathSoFar = queue.shift();
            const current = pathSoFar[pathSoFar.length - 1];

            for (const [dr, dc] of [[0,1],[0,-1],[1,0],[-1,0]]) {
                const nr = current[0] + dr;
                const nc = current[1] + dc;
                const key = `${nr},${nc}`;

                if (nr < 0 || nr >= GRID_ROWS || nc < 0 || nc >= GRID_COLS) continue;
                if (visited.has(key)) continue;

                // check if road is blocked
                const blocked = this.blockedRoads.some(b => {
                    const [a, bEdge] = b.edge;
                    return (a[0] === current[0] && a[1] === current[1] && bEdge[0] === nr && bEdge[1] === nc) ||
                           (bEdge[0] === current[0] && bEdge[1] === current[1] && a[0] === nr && a[1] === nc);
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
