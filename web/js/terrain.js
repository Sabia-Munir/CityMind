// terrain.js — 3D terrain grid with ground tiles and roads
import * as THREE from 'three';
import { GRID_ROWS, GRID_COLS, zoneGrid, roadEdges, zoneColors } from './cityData.js';

const TILE_SIZE = 4;
const ROAD_WIDTH = 3.6;

export class CityTerrain {
    constructor(scene) {
        this.scene = scene;
        this.group = new THREE.Group();
        this.group.name = 'terrain';
        this.scene.add(this.group);
        this.tileMeshes = [];
        this.roadMeshes = [];
    }

    build() {
        this.buildGroundTiles();
        this.buildRoads();
    }

    buildGroundTiles() {
        const offset = new THREE.Vector3(
            -(GRID_COLS * TILE_SIZE) / 2 + TILE_SIZE / 2,
            0,
            -(GRID_ROWS * TILE_SIZE) / 2 + TILE_SIZE / 2
        );

        for (let row = 0; row < GRID_ROWS; row++) {
            for (let col = 0; col < GRID_COLS; col++) {
                const zone = zoneGrid[row][col];
                const colors = zoneColors[zone];

                // base ground tile
                const geo = new THREE.BoxGeometry(TILE_SIZE * 0.95, 0.15, TILE_SIZE * 0.95);
                const mat = new THREE.MeshStandardMaterial({
                    color: colors.top,
                    roughness: 0.85,
                    metalness: 0.05,
                });
                const tile = new THREE.Mesh(geo, mat);
                tile.position.set(
                    col * TILE_SIZE + offset.x,
                    0.075,
                    row * TILE_SIZE + offset.z
                );
                tile.receiveShadow = true;
                tile.castShadow = false;
                tile.userData = { row, col, zone };
                this.group.add(tile);
                this.tileMeshes.push(tile);
            }
        }
    }

    buildRoads() {
        const offset = new THREE.Vector3(
            -(GRID_COLS * TILE_SIZE) / 2 + TILE_SIZE / 2,
            0,
            -(GRID_ROWS * TILE_SIZE) / 2 + TILE_SIZE / 2
        );

        // create a set for quick edge lookup
        const edgeSet = new Set();
        roadEdges.forEach(([a, b]) => {
            const key1 = `${a[0]},${a[1]}-${b[0]},${b[1]}`;
            const key2 = `${b[0]},${b[1]}-${a[0]},${a[1]}`;
            edgeSet.add(key1);
            edgeSet.add(key2);
        });

        // draw road segments between connected tiles
        const roadMat = new THREE.MeshStandardMaterial({
            color: 0x505560,
            roughness: 0.7,
            metalness: 0.1,
        });

        const lineMat = new THREE.MeshStandardMaterial({
            color: 0xfff0a0,
            roughness: 0.5,
            metalness: 0.0,
        });

        for (let row = 0; row < GRID_ROWS; row++) {
            for (let col = 0; col < GRID_COLS; col++) {
                const cx = col * TILE_SIZE + offset.x;
                const cz = row * TILE_SIZE + offset.z;

                // right neighbor
                if (col + 1 < GRID_COLS) {
                    const key = `${row},${col}-${row},${col + 1}`;
                    if (edgeSet.has(key)) {
                        this._drawRoadSegment(cx, cz, cx + TILE_SIZE, cz, roadMat, lineMat);
                    }
                }

                // bottom neighbor
                if (row + 1 < GRID_ROWS) {
                    const key = `${row},${col}-${row + 1},${col}`;
                    if (edgeSet.has(key)) {
                        this._drawRoadSegment(cx, cz, cx, cz + TILE_SIZE, roadMat, lineMat);
                    }
                }
            }
        }
    }

    _drawRoadSegment(x1, z1, x2, z2, roadMat, lineMat) {
        const isHorizontal = Math.abs(z1 - z2) < 0.01;
        const length = Math.abs(isHorizontal ? (x2 - x1) : (z2 - z1));

        // road surface
        const roadGeo = isHorizontal
            ? new THREE.BoxGeometry(length + 0.5, 0.08, ROAD_WIDTH)
            : new THREE.BoxGeometry(ROAD_WIDTH, 0.08, length + 0.5);
        const road = new THREE.Mesh(roadGeo, roadMat);
        road.position.set((x1 + x2) / 2, 0.04, (z1 + z2) / 2);
        road.receiveShadow = true;
        road.castShadow = false;
        this.group.add(road);
        this.roadMeshes.push(road);

        // centre dashed line
        const dashLen = 0.4;
        const gapLen = 0.3;
        const totalDash = dashLen + gapLen;
        const numDashes = Math.floor(length / totalDash);

        for (let i = 0; i < numDashes; i++) {
            const startFrac = (i * totalDash) / length;
            const endFrac = Math.min((i * totalDash + dashLen) / length, 1);
            const dashLength = (endFrac - startFrac) * length;

            const dashGeo = isHorizontal
                ? new THREE.BoxGeometry(dashLength, 0.02, 0.08)
                : new THREE.BoxGeometry(0.08, 0.02, dashLength);

            const dash = new THREE.Mesh(dashGeo, lineMat);
            const t = startFrac + (endFrac - startFrac) / 2;
            dash.position.set(
                x1 + (x2 - x1) * t,
                0.09,
                z1 + (z2 - z1) * t
            );
            this.group.add(dash);
        }
    }

    // Convert grid (row, col) to 3D world position
    gridToWorld(row, col) {
        const offset = new THREE.Vector3(
            -(GRID_COLS * TILE_SIZE) / 2 + TILE_SIZE / 2,
            0,
            -(GRID_ROWS * TILE_SIZE) / 2 + TILE_SIZE / 2
        );
        return new THREE.Vector3(
            col * TILE_SIZE + offset.x,
            0,
            row * TILE_SIZE + offset.z
        );
    }
}
