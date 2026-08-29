// heatmap.js — risk heatmap overlay on buildings and ground
import * as THREE from 'three';
import { GRID_ROWS, GRID_COLS, zoneGrid } from './cityData.js';

const TILE_SIZE = 4;

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
        this.group.visible = true;
        this.scene.add(this.group);
        this.riskPlanes = [];
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
                const zone = zoneGrid[row][col];
                const initialRisk = this._getInitialRisk(zone);
                const color = this._riskToColor(initialRisk);

                // main risk plane — semi-transparent colored square
                const geo = new THREE.PlaneGeometry(TILE_SIZE * 0.92, TILE_SIZE * 0.92);
                const mat = new THREE.MeshBasicMaterial({
                    color: color,
                    transparent: true,
                    opacity: 0.4,
                    side: THREE.DoubleSide,
                    depthWrite: false,
                });
                const plane = new THREE.Mesh(geo, mat);
                plane.rotation.x = -Math.PI / 2;
                plane.position.set(
                    col * TILE_SIZE + offset.x,
                    0.12,
                    row * TILE_SIZE + offset.z
                );
                plane.name = `risk_${row}_${col}`;
                this.group.add(plane);
                this.riskPlanes.push({ mesh: plane, row, col, risk: initialRisk, phase: Math.random() * Math.PI * 2 });
            }
        }
    }

    _getInitialRisk(zone) {
        return { Residential: 0.3, Hospital: 0.1, School: 0.15, Industrial: 0.5, AmbulanceDepot: 0.1, PowerPlant: 0.4, Empty: 0.0 }[zone] || 0;
    }

    _riskToColor(risk) {
        if (risk <= 0.3) return RISK_COLORS.low.clone().lerp(RISK_COLORS.medium, risk / 0.3);
        if (risk <= 0.6) return RISK_COLORS.medium.clone().lerp(RISK_COLORS.high, (risk - 0.3) / 0.3);
        return RISK_COLORS.high.clone();
    }

    updateRisk(row, col, newRisk) {
        const entry = this.riskPlanes.find(e => e.row === row && e.col === col);
        if (entry) {
            entry.risk = newRisk;
            entry.mesh.material.color.copy(this._riskToColor(newRisk));
        }
    }

    update(elapsedTime) {
        this.riskPlanes.forEach(entry => {
            entry.mesh.material.opacity = 0.3 + Math.sin(elapsedTime * 1.5 + entry.phase) * 0.1;
        });
    }
}
