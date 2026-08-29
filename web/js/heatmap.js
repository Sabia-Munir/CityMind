// heatmap.js — VERY prominent risk heatmap overlay
import * as THREE from 'three';
import { GRID_ROWS, GRID_COLS, zoneGrid } from './cityData.js';
const TILE_SIZE = 4;

export class HeatmapSystem {
    constructor(scene, terrain) {
        this.scene = scene;
        this.terrain = terrain;
        this.group = new THREE.Group();
        this.group.name = 'heatmap';
        this.group.visible = true;
        this.scene.add(this.group);
        this.riskPlanes = [];
        this._build();
    }

    _build() {
        const offset = new THREE.Vector3(
            -(GRID_COLS * TILE_SIZE) / 2 + TILE_SIZE / 2, 0,
            -(GRID_ROWS * TILE_SIZE) / 2 + TILE_SIZE / 2
        );

        for (let row = 0; row < GRID_ROWS; row++) {
            for (let col = 0; col < GRID_COLS; col++) {
                const zone = zoneGrid[row][col];
                const risk = { Residential: 0.3, Hospital: 0.1, School: 0.15, Industrial: 0.5, AmbulanceDepot: 0.1, PowerPlant: 0.4, Empty: 0.0 }[zone] || 0;
                const color = this._color(risk);

                // main overlay — BIG, visible
                const plane = new THREE.Mesh(
                    new THREE.PlaneGeometry(TILE_SIZE * 0.95, TILE_SIZE * 0.95),
                    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false })
                );
                plane.rotation.x = -Math.PI / 2;
                plane.position.set(col * TILE_SIZE + offset.x, 0.15, row * TILE_SIZE + offset.z);
                plane.name = `risk_${row}_${col}`;
                this.group.add(plane);

                // edge outline for extra visibility
                const edge = new THREE.Mesh(
                    new THREE.EdgesGeometry(new THREE.PlaneGeometry(TILE_SIZE * 0.95, TILE_SIZE * 0.95)),
                    new THREE.LineBasicMaterial({ color: this._edgeColor(risk), linewidth: 2 })
                );
                edge.rotation.x = -Math.PI / 2;
                edge.position.set(col * TILE_SIZE + offset.x, 0.16, row * TILE_SIZE + offset.z);
                this.group.add(edge);

                this.riskPlanes.push({ mesh: plane, edge, row, col, risk, phase: Math.random() * 6.28 });
            }
        }
    }

    _color(risk) {
        if (risk <= 0.2) return new THREE.Color(0x22cc44);
        if (risk <= 0.35) return new THREE.Color(0x88cc22);
        if (risk <= 0.5) return new THREE.Color(0xffaa00);
        if (risk <= 0.7) return new THREE.Color(0xff6600);
        return new THREE.Color(0xff2222);
    }

    _edgeColor(risk) {
        if (risk <= 0.3) return 0x33ff66;
        if (risk <= 0.5) return 0xffcc00;
        return 0xff4444;
    }

    updateRisk(row, col, newRisk) {
        const entry = this.riskPlanes.find(e => e.row === row && e.col === col);
        if (entry) { entry.risk = newRisk; entry.mesh.material.color.copy(this._color(newRisk)); }
    }

    update(t) {
        this.riskPlanes.forEach(e => {
            e.mesh.material.opacity = 0.45 + Math.sin(t * 1.5 + e.phase) * 0.15;
        });
    }
}
