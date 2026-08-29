// simulation.js — 3 ambulances rescue civilians across 20 steps
import { GRID_ROWS, GRID_COLS, zoneGrid, roadEdges, primaryHospital, primaryDepot } from './cityData.js';

const AMB_COLORS = [0x3cff8c, 0xff6b3c, 0x44aaff];
const AMB_STARTS = [[1,5], [5,4], [8,8]];
const AMB_DEPOTS = [[1,4], [6,4], [9,8]];
const AMB_NAMES = ['Alpha', 'Bravo', 'Charlie'];

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
        this.stepInterval = 2.0;
        this.civiliansRescued = 0;
        this.floodCount = 0;
        this.blockedRoads = [];
        this.finished = false;

        this.civilians = this._pickCivilians();
        this.ambTasks = this._initTasks();

        this._bindButtons();
    }

    _initTasks() {
        const perAmb = Math.ceil(this.civilians.length / 3);
        return [
            { idx: 0, civs: this.civilians.slice(0, perAmb).map((_, i) => i), returning: false, done: false },
            { idx: 1, civs: this.civilians.slice(perAmb, perAmb * 2).map((_, i) => perAmb + i), returning: false, done: false },
            { idx: 2, civs: this.civilians.slice(perAmb * 2).map((_, i) => perAmb * 2 + i), returning: false, done: false },
        ];
    }

    _pickCivilians() {
        const civs = [];
        const occ = new Set([primaryHospital.join(','), primaryDepot.join(','), ...AMB_STARTS.map(a => a.join(','))]);
        const rng = this._rng(42);
        const residential = [];
        for (let r = 0; r < GRID_ROWS; r++) {
            for (let c = 0; c < GRID_COLS; c++) {
                if (!occ.has(`${r},${c}`) && zoneGrid[r][c] === 'Residential') {
                    residential.push([r, c]);
                }
            }
        }
        const shuffled = residential.slice();
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = Math.floor(rng() * (i + 1));
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }
        const count = Math.min(60, shuffled.length);
        for (let i = 0; i < count; i++) {
            civs.push(shuffled[i]);
        }
        return civs;
    }

    _rng(seed) { let s = seed; return () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; }; }

    _bindButtons() {
        if (!this.ui) return;
        this.ui.on('play', () => this.play());
        this.ui.on('pause', () => this.pause());
        this.ui.on('reset', () => this.reset());
    }

    play() {
        this.playing = true;
        if (this.step === 0 && !this.finished) { this.step = 1; this._runStep(); }
        if (this.ui) this.ui.showToast('Simulation started — 3 ambulances active', 'success');
    }

    pause() {
        this.playing = false;
        if (this.ui) this.ui.showToast('Paused', 'warning');
    }

    reset() {
        this.playing = false; this.step = 0; this.stepTimer = 0;
        this.civiliansRescued = 0; this.floodCount = 0; this.finished = false;
        this.blockedRoads = [];
        this.civilians = this._pickCivilians();
        this.ambTasks = this._initTasks();

        this.floods.clearAll(); this.pathViz.clearAll();
        this.vehicles.teleportTo(0, AMB_STARTS[0][0], AMB_STARTS[0][1]);
        this.vehicles.teleportTo(1, AMB_STARTS[1][0], AMB_STARTS[1][1]);
        this.vehicles.teleportTo(2, AMB_STARTS[2][0], AMB_STARTS[2][1]);

        if (this.ui) {
            this.ui.updateStep(0);
            this.ui.updateStats({ rescued: 0, floods: 0 });
            this.ui.addLogEntry('System', 'Reset — click Play to begin', 'system');
        }
        if (this.onCiviliansChanged) this.onCiviliansChanged(this.civilians);
    }

    _runStep() {
        if (this.step > this.totalSteps) {
            this._finishSimulation();
            return;
        }
        this.stepTimer = 0;

        this._doFlood();

        this.ambTasks.forEach((task, slot) => this._routeAmbulance(slot, task));

        if (this.step % 3 === 0 && this.blockedRoads.length > 0) this._doRecovery();

        if (this.ui) {
            this.ui.updateStep(this.step);
            this.ui.updateStats({ rescued: this.civiliansRescued, floods: this.floodCount });
        }
        this.step++;
    }

    _finishSimulation() {
        this.playing = false; this.finished = true;
        if (this.ui) {
            this.ui.showToast(`SIMULATION COMPLETE — ${this.civiliansRescued} civilians rescued!`, 'success');
            this.ui.addLogEntry('System', '=== ALL 20 STEPS COMPLETE ===', 'system');
        }
        this.pathViz.clearAll();
        this.ambTasks.forEach((task, slot) => {
            if (task.done) return;
            task.done = true;
            const depot = AMB_DEPOTS[slot];
            const curPos = this._getAmbGridPos(slot);
            const path = this._bfs(curPos, depot);
            if (path.length > 0) {
                this.pathViz.showPath(path, AMB_COLORS[slot], `amb${slot}_return`);
                this.vehicles.setPath(slot, path);
            }
            if (this.ui) {
                this.ui.showToast(`${AMB_NAMES[slot]} returning to depot`, 'info');
                this.ui.addLogEntry('RETURN', `${AMB_NAMES[slot]} returning to base at (${depot})`, 'system');
            }
        });
    }

    _getAmbGridPos(slot) {
        const amb = this.vehicles.ambulances[slot];
        const TILE_SIZE = 4;
        const offset = -(GRID_COLS * TILE_SIZE) / 2 + TILE_SIZE / 2;
        const col = Math.round((amb.mesh.position.x - offset) / TILE_SIZE);
        const row = Math.round((amb.mesh.position.z - offset) / TILE_SIZE);
        const cr = Math.max(0, Math.min(GRID_ROWS - 1, row));
        const cc = Math.max(0, Math.min(GRID_COLS - 1, col));
        return [cr, cc];
    }

    _doFlood() {
        const rng = this._rng(this.step * 7 + 13);
        const n = Math.min(2, Math.floor(rng() * 3));
        for (let i = 0; i < n; i++) {
            if (this.blockedRoads.length >= 10) return;
            const idx = Math.floor(rng() * roadEdges.length);
            const edge = roadEdges[idx];
            const key = `${edge[0][0]},${edge[0][1]}-${edge[1][0]},${edge[1][1]}`;
            if (!this.blockedRoads.find(b => b.key === key)) {
                this.blockedRoads.push({ key, edge: [...edge] });
                this.floods.addFlood(edge[0][0], edge[0][1], edge[1][0], edge[1][1], `s${this.step}f${i}`);
                this.floodCount++;
                if (this.ui) this.ui.addLogEntry('FLOOD', `Step ${this.step}: (${edge[0]}) <-> (${edge[1]}) BLOCKED`, 'flood');
            }
        }
    }

    _doRecovery() {
        const rec = this.blockedRoads.pop();
        if (rec) {
            const [a, b] = rec.edge;
            this.floods.removeFloodByEdge(a[0], a[1], b[0], b[1]);
            this.floodCount = Math.max(0, this.floodCount - 1);
            if (this.ui) this.ui.addLogEntry('RESTORE', `Step ${this.step}: (${a}) <-> (${b}) restored`, 'restore');
        }
    }

    _routeAmbulance(slot, task) {
        if (task.done) return;

        if (this.ambCivIdx[slot] >= task.civs.length) {
            if (!task.returning) {
                task.returning = true;
                const depot = AMB_DEPOTS[slot];
                const curPos = this._getAmbGridPos(slot);
                const path = this._bfs(curPos, depot);
                if (path.length > 0) {
                    this.pathViz.showPath(path, AMB_COLORS[slot], `amb${slot}_return_s${this.step}`);
                    this.vehicles.setPath(slot, path);
                    if (this.ui) {
                        this.ui.showToast(`${AMB_NAMES[slot]} all civilians rescued — returning to depot`, 'info');
                        this.ui.addLogEntry('RETURN', `${AMB_NAMES[slot]} returning to base at (${depot})`, 'system');
                    }
                }
            }
            return;
        }

        const civIdx = task.civs[this.ambCivIdx[slot]];
        if (civIdx >= this.civilians.length) { this.ambCivIdx[slot]++; return; }
        const civ = this.civilians[civIdx];

        const curPos = this._getAmbGridPos(slot);
        const path = this._bfs(curPos, civ);
        if (path.length === 0) { this.ambCivIdx[slot]++; return; }

        this.pathViz.showPath(path, AMB_COLORS[slot], `amb${slot}_s${this.step}`);
        this.vehicles.setPath(slot, path);
        this.civiliansRescued++;

        if (this.ui) {
            this.ui.addLogEntry('RESCUE', `${AMB_NAMES[slot]} -> civilian #${this.civiliansRescued} at (${civ}) [${path.length} steps]`, 'system');
            this.ui.showToast(`${AMB_NAMES[slot]} rescuing civilian ${this.civiliansRescued}`, 'info');
        }
        this.ambCivIdx[slot]++;
    }

    _bfs(start, goal) {
        if (start[0] === goal[0] && start[1] === goal[1]) return [start];
        const vis = new Set([start.join(',')]);
        const q = [[start]];
        while (q.length) {
            const p = q.shift(), cur = p[p.length - 1];
            for (const [dr, dc] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
                const nr = cur[0] + dr, nc = cur[1] + dc;
                if (nr < 0 || nr >= GRID_ROWS || nc < 0 || nc >= GRID_COLS) continue;
                if (vis.has(`${nr},${nc}`)) continue;
                if (this.blockedRoads.some(b => {
                    const [a, bE] = b.edge;
                    return (a[0] === cur[0] && a[1] === cur[1] && bE[0] === nr && bE[1] === nc) ||
                           (bE[0] === cur[0] && bE[1] === cur[1] && a[0] === nr && a[1] === nc);
                })) continue;
                vis.add(`${nr},${nc}`);
                const np = [...p, [nr, nc]];
                if (nr === goal[0] && nc === goal[1]) return np;
                q.push(np);
            }
        }
        return [];
    }

    update(delta) {
        if (!this.playing) return;
        this.stepTimer += delta;
        if (this.stepTimer >= this.stepInterval) this._runStep();
    }
}
