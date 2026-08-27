// heatmap.js — risk heatmap overlay on buildings and ground
import * as THREE from 'three';
import { GRID_ROWS, GRID_COLS, zoneGrid } from './cityData.js';

const TILE_SIZE = 4;

// risk index ranges from 0.0 to 1.0
// Low: 0.0-0.3 (green), Medium: 0.3-0.6 (amber), High: 0.6-1.0 (red)

const RISK_COLORS = {
    low:    new THREE.Color(0x3ccc5c),
    medium: new THREE.Color(0xffbe3c),
    high:   new THREE.Color(0xff3c3c),
};

export class HeatmapSystem {
    constructor(scene, terrain) {
        this.scene = scene;
        this.terrain = terrain;
        this.group = new THREE.Group();
        this.group.name = 'heatmap';
        this.group.visible = false; // hidden by default
        this.scene.add(this.group);
        this.riskPlanes = [];
        this.pulseTime = 0;
        this._buildOverlay();
    }

    _buildOverlay() {
        const offset = new THREE.Vector3(
            -(GRID_COLS * TILE_SIZE) / 2 + TILE_SIZE / 2,
            0,
            -(GRID_ROWS * TILE_SIZE) / 2 + TILE_SIZE / 2
        );

        for (let row = 0; row < GRID_ROWS; row++) {
            for (let col = 0; col < GRID_COLS; col++) {
                // initial risk from zone type
                const zone = zoneGrid[row][col];
                const initialRisk = this._getInitialRisk(zone);

                const geo = new THREE.PlaneGeometry(TILE_SIZE * 0.85, TILE_SIZE * 0.85);
                const color = this._riskToColor(initialRisk);
                const mat = new THREE.MeshBasicMaterial({
                    color: color,
                    transparent: true,
                    opacity: 0.35,
                    side: THREE.DoubleSide,
                    depthWrite: false,
                });
                const plane = new THREE.Mesh(geo, mat);
                plane.rotation.x = -Math.PI / 2;
                plane.position.set(
                    col * TILE_SIZE + offset.x,
                    0.2,
                    row * TILE_SIZE + offset.z
                );
                plane.name = `risk_${row}_${col}`;
                this.group.add(plane);
                this.riskPlanes.push({
                    mesh: plane,
                    row,
                    col,
                    risk: initialRisk,
                    phase: Math.random() * Math.PI * 2,
                });
            }
        }
    }

    _getInitialRisk(zone) {
        const risks = {
            Residential: 0.3,
            Hospital: 0.1,
            School: 0.15,
            Industrial: 0.5,
            AmbulanceDepot: 0.1,
            PowerPlant: 0.4,
            Empty: 0.0,
        };
        return risks[zone] || 0;
    }

    _riskToColor(risk) {
        if (risk <= 0.3) {
            return RISK_COLORS.low.clone().lerp(RISK_COLORS.medium, risk / 0.3);
        } else if (risk <= 0.6) {
            return RISK_COLORS.medium.clone().lerp(RISK_COLORS.high, (risk - 0.3) / 0.3);
        } else {
            return RISK_COLORS.high.clone();
        }
    }

    updateRisk(row, col, newRisk) {
        const entry = this.riskPlanes.find(e => e.row === row && e.col === col);
        if (entry) {
            entry.risk = newRisk;
            entry.mesh.material.color.copy(this._riskToColor(newRisk));
        }
    }

    update(elapsedTime) {
        this.pulseTime = elapsedTime;

        this.riskPlanes.forEach(entry => {
            const pulse = 0.25 + Math.sin(elapsedTime * 1.5 + entry.phase) * 0.1;
            entry.mesh.material.opacity = pulse;
        });
    }
}
