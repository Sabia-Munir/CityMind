// ui.js — control panel interactions, event log, and toast notifications
import { GRID_ROWS, GRID_COLS, zoneGrid } from './cityData.js';

export class UIController {
    constructor() {
        this.logEntries = document.getElementById('log-entries');
        this.toastContainer = document.getElementById('toast-container');
        this.stepDisplay = document.getElementById('step-num');
        this.callbacks = {};
        this._bindControls();
        this.addLogEntry('System', 'CityMind 3D initialized', 'system');
    }

    _bindControls() {
        // simulation buttons
        document.getElementById('btn-play')?.addEventListener('click', () => {
            this._fire('play');
        });
        document.getElementById('btn-pause')?.addEventListener('click', () => {
            this._fire('pause');
        });
        document.getElementById('btn-reset')?.addEventListener('click', () => {
            this._fire('reset');
        });

        // camera view buttons
        document.querySelectorAll('.btn-view').forEach(btn => {
            btn.addEventListener('click', () => {
                const view = btn.dataset.view;
                this._fire('camera', view);
            });
        });

        // overlay toggles
        document.getElementById('toggle-paths')?.addEventListener('change', (e) => {
            this._fire('togglePaths', e.target.checked);
        });
        document.getElementById('toggle-floods')?.addEventListener('change', (e) => {
            this._fire('toggleFloods', e.target.checked);
        });
        document.getElementById('toggle-risk')?.addEventListener('change', (e) => {
            this._fire('toggleRisk', e.target.checked);
        });
        document.getElementById('toggle-vehicles')?.addEventListener('change', (e) => {
            this._fire('toggleVehicles', e.target.checked);
        });
    }

    on(event, callback) {
        if (!this.callbacks[event]) this.callbacks[event] = [];
        this.callbacks[event].push(callback);
    }

    _fire(event, ...args) {
        (this.callbacks[event] || []).forEach(cb => cb(...args));
    }

    updateStep(step) {
        if (this.stepDisplay) this.stepDisplay.textContent = step;
    }

    updateStats(stats) {
        if (stats.ambulances !== undefined) {
            document.getElementById('stat-amb').textContent = stats.ambulances;
        }
        if (stats.rescued !== undefined) {
            document.getElementById('stat-rescued').textContent = stats.rescued;
        }
        if (stats.floods !== undefined) {
            document.getElementById('stat-floods').textContent = stats.floods;
        }
        if (stats.risk !== undefined) {
            document.getElementById('stat-risk').textContent = stats.risk;
        }
    }

    addLogEntry(category, message, type = 'system') {
        if (!this.logEntries) return;
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.innerHTML = `<span class="log-${type}">[${category}]</span> ${message}`;
        this.logEntries.appendChild(entry);
        this.logEntries.scrollTop = this.logEntries.scrollHeight;
    }

    showToast(message, type = 'info') {
        if (!this.toastContainer) return;
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        this.toastContainer.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }
}
