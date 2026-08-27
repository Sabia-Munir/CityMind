// buildings.js — procedural 3D building models for each zone type
import * as THREE from 'three';
import { GRID_ROWS, GRID_COLS, zoneGrid, zoneColors, buildingHeights } from './cityData.js';

const TILE_SIZE = 4;

export class CityBuildings {
    constructor(scene, terrain) {
        this.scene = scene;
        this.terrain = terrain;
        this.group = new THREE.Group();
        this.group.name = 'buildings';
        this.scene.add(this.group);
        this.buildingMeshes = [];
    }

    build() {
        for (let row = 0; row < GRID_ROWS; row++) {
            for (let col = 0; col < GRID_COLS; col++) {
                const zone = zoneGrid[row][col];
                const pos = this.terrain.gridToWorld(row, col);

                switch (zone) {
                    case 'Hospital':      this._createHospital(pos); break;
                    case 'School':        this._createSchool(pos); break;
                    case 'PowerPlant':    this._createPowerPlant(pos); break;
                    case 'AmbulanceDepot':this._createAmbulanceDepot(pos); break;
                    case 'Industrial':    this._createIndustrial(pos); break;
                    case 'Residential':   this._createResidential(pos); break;
                    case 'Empty':         this._createPark(pos); break;
                }
            }
        }
    }

    // ─── Hospital ─────────────────────────────────────────────────────────
    _createHospital(pos) {
        const group = new THREE.Group();
        const s = zoneColors.Hospital;

        // main building body
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(2.8, 2.8, 2.8),
            new THREE.MeshStandardMaterial({ color: 0xf0f0f0, roughness: 0.4, metalness: 0.1 })
        );
        body.position.y = 1.55;
        body.castShadow = true;
        body.receiveShadow = true;
        group.add(body);

        // roof
        const roof = new THREE.Mesh(
            new THREE.BoxGeometry(3.0, 0.2, 3.0),
            new THREE.MeshStandardMaterial({ color: s.side, roughness: 0.5 })
        );
        roof.position.y = 3.05;
        roof.castShadow = true;
        group.add(roof);

        // red cross on front
        const crossH = new THREE.Mesh(
            new THREE.BoxGeometry(0.8, 0.2, 0.05),
            new THREE.MeshStandardMaterial({ color: 0xff2020, emissive: 0xff0000, emissiveIntensity: 0.3 })
        );
        crossH.position.set(0, 2.4, 1.43);
        group.add(crossH);

        const crossV = new THREE.Mesh(
            new THREE.BoxGeometry(0.2, 0.8, 0.05),
            new THREE.MeshStandardMaterial({ color: 0xff2020, emissive: 0xff0000, emissiveIntensity: 0.3 })
        );
        crossV.position.set(0, 2.4, 1.43);
        group.add(crossV);

        // windows
        this._addWindows(group, 2.8, 2.8, 0xf0f0f0);

        // entrance
        const entrance = new THREE.Mesh(
            new THREE.BoxGeometry(0.8, 1.0, 0.15),
            new THREE.MeshStandardMaterial({ color: 0x4488cc })
        );
        entrance.position.set(0, 0.65, 1.48);
        group.add(entrance);

        group.position.set(pos.x, pos.y, pos.z);
        this.group.add(group);
        this.buildingMeshes.push(group);
    }

    // ─── School ───────────────────────────────────────────────────────────
    _createSchool(pos) {
        const group = new THREE.Group();
        const s = zoneColors.School;

        // main building
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(3.0, 2.2, 2.5),
            new THREE.MeshStandardMaterial({ color: 0xfff8dc, roughness: 0.6 })
        );
        body.position.y = 1.25;
        body.castShadow = true;
        body.receiveShadow = true;
        group.add(body);

        // roof
        const roof = new THREE.Mesh(
            new THREE.BoxGeometry(3.2, 0.25, 2.7),
            new THREE.MeshStandardMaterial({ color: 0x8b4513 })
        );
        roof.position.y = 2.48;
        roof.castShadow = true;
        group.add(roof);

        // bell tower
        const tower = new THREE.Mesh(
            new THREE.BoxGeometry(0.6, 1.2, 0.6),
            new THREE.MeshStandardMaterial({ color: 0xfff8dc })
        );
        tower.position.set(0, 3.2, 0);
        tower.castShadow = true;
        group.add(tower);

        // tower roof (pyramid)
        const towerRoof = new THREE.Mesh(
            new THREE.ConeGeometry(0.5, 0.6, 4),
            new THREE.MeshStandardMaterial({ color: 0x8b4513 })
        );
        towerRoof.position.set(0, 4.1, 0);
        towerRoof.rotation.y = Math.PI / 4;
        towerRoof.castShadow = true;
        group.add(towerRoof);

        // flag pole
        const pole = new THREE.Mesh(
            new THREE.CylinderGeometry(0.03, 0.03, 0.8),
            new THREE.MeshStandardMaterial({ color: 0x888888 })
        );
        pole.position.set(0, 4.8, 0);
        group.add(pole);

        // flag
        const flag = new THREE.Mesh(
            new THREE.BoxGeometry(0.4, 0.25, 0.02),
            new THREE.MeshStandardMaterial({ color: 0xff4444 })
        );
        flag.position.set(0.22, 5.05, 0);
        group.add(flag);

        // windows
        this._addWindows(group, 3.0, 2.2, 0xfff8dc);

        group.position.set(pos.x, pos.y, pos.z);
        this.group.add(group);
        this.buildingMeshes.push(group);
    }

    // ─── Power Plant ──────────────────────────────────────────────────────
    _createPowerPlant(pos) {
        const group = new THREE.Group();
        const s = zoneColors.PowerPlant;

        // main building
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(2.8, 3.0, 2.8),
            new THREE.MeshStandardMaterial({ color: 0x999999, roughness: 0.7, metalness: 0.3 })
        );
        body.position.y = 1.65;
        body.castShadow = true;
        body.receiveShadow = true;
        group.add(body);

        // cooling tower 1
        const tower1 = new THREE.Mesh(
            new THREE.CylinderGeometry(0.5, 0.7, 2.0, 12),
            new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 0.6 })
        );
        tower1.position.set(-0.8, 3.65, -0.5);
        tower1.castShadow = true;
        group.add(tower1);

        // cooling tower 2
        const tower2 = new THREE.Mesh(
            new THREE.CylinderGeometry(0.5, 0.7, 2.0, 12),
            new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 0.6 })
        );
        tower2.position.set(0.8, 3.65, -0.5);
        tower2.castShadow = true;
        group.add(tower2);

        // smokestack
        const stack = new THREE.Mesh(
            new THREE.CylinderGeometry(0.15, 0.2, 2.5, 8),
            new THREE.MeshStandardMaterial({ color: 0x666666, metalness: 0.4 })
        );
        stack.position.set(0.5, 4.4, 0.8);
        stack.castShadow = true;
        group.add(stack);

        // smoke particles (static puffs)
        for (let i = 0; i < 5; i++) {
            const puff = new THREE.Mesh(
                new THREE.SphereGeometry(0.15 + Math.random() * 0.15, 8, 8),
                new THREE.MeshStandardMaterial({
                    color: 0xdddddd,
                    transparent: true,
                    opacity: 0.5 - i * 0.08
                })
            );
            puff.position.set(
                0.5 + (Math.random() - 0.5) * 0.3,
                5.0 + i * 0.5,
                0.8 + (Math.random() - 0.5) * 0.3
            );
            group.add(puff);
        }

        // roof
        const roof = new THREE.Mesh(
            new THREE.BoxGeometry(3.0, 0.15, 3.0),
            new THREE.MeshStandardMaterial({ color: s.side })
        );
        roof.position.y = 3.23;
        group.add(roof);

        group.position.set(pos.x, pos.y, pos.z);
        this.group.add(group);
        this.buildingMeshes.push(group);
    }

    // ─── Ambulance Depot ──────────────────────────────────────────────────
    _createAmbulanceDepot(pos) {
        const group = new THREE.Group();
        const s = zoneColors.AmbulanceDepot;

        // garage building
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(3.2, 2.0, 2.8),
            new THREE.MeshStandardMaterial({ color: 0x6699cc, roughness: 0.5 })
        );
        body.position.y = 1.15;
        body.castShadow = true;
        body.receiveShadow = true;
        group.add(body);

        // flat roof
        const roof = new THREE.Mesh(
            new THREE.BoxGeometry(3.4, 0.15, 3.0),
            new THREE.MeshStandardMaterial({ color: 0x445566 })
        );
        roof.position.y = 2.23;
        roof.castShadow = true;
        group.add(roof);

        // garage door
        const door = new THREE.Mesh(
            new THREE.BoxGeometry(1.8, 1.5, 0.1),
            new THREE.MeshStandardMaterial({ color: 0x334455 })
        );
        door.position.set(0, 0.9, 1.45);
        group.add(door);

        // door stripes
        for (let i = 0; i < 5; i++) {
            const stripe = new THREE.Mesh(
                new THREE.BoxGeometry(1.6, 0.04, 0.02),
                new THREE.MeshStandardMaterial({ color: 0x888888 })
            );
            stripe.position.set(0, 0.3 + i * 0.3, 1.52);
            group.add(stripe);
        }

        // emergency light on roof
        const light = new THREE.Mesh(
            new THREE.SphereGeometry(0.15, 8, 8),
            new THREE.MeshStandardMaterial({
                color: 0xff0000,
                emissive: 0xff0000,
                emissiveIntensity: 0.8
            })
        );
        light.position.set(0, 2.5, 0);
        group.add(light);

        // ambulance cross on side
        const crossH = new THREE.Mesh(
            new THREE.BoxGeometry(0.6, 0.15, 0.02),
            new THREE.MeshStandardMaterial({ color: 0xffffff })
        );
        crossH.position.set(0, 1.6, 1.42);
        group.add(crossH);

        const crossV = new THREE.Mesh(
            new THREE.BoxGeometry(0.15, 0.6, 0.02),
            new THREE.MeshStandardMaterial({ color: 0xffffff })
        );
        crossV.position.set(0, 1.6, 1.42);
        group.add(crossV);

        group.position.set(pos.x, pos.y, pos.z);
        this.group.add(group);
        this.buildingMeshes.push(group);
    }

    // ─── Industrial ───────────────────────────────────────────────────────
    _createIndustrial(pos) {
        const group = new THREE.Group();
        const s = zoneColors.Industrial;

        // factory body
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(3.0, 2.5, 2.5),
            new THREE.MeshStandardMaterial({ color: 0x8a8a8a, roughness: 0.8, metalness: 0.2 })
        );
        body.position.y = 1.4;
        body.castShadow = true;
        body.receiveShadow = true;
        group.add(body);

        // sawtooth roof
        for (let i = 0; i < 3; i++) {
            const tooth = new THREE.Mesh(
                new THREE.BoxGeometry(0.9, 0.4, 2.5),
                new THREE.MeshStandardMaterial({ color: 0x6a6a6a })
            );
            tooth.position.set(-1.0 + i * 1.0, 2.85, 0);
            tooth.castShadow = true;
            group.add(tooth);
        }

        // chimney 1
        const chim1 = new THREE.Mesh(
            new THREE.CylinderGeometry(0.12, 0.18, 2.0, 8),
            new THREE.MeshStandardMaterial({ color: 0x555555 })
        );
        chim1.position.set(-1.0, 4.0, 0.8);
        chim1.castShadow = true;
        group.add(chim1);

        // chimney 2
        const chim2 = new THREE.Mesh(
            new THREE.CylinderGeometry(0.12, 0.18, 1.5, 8),
            new THREE.MeshStandardMaterial({ color: 0x555555 })
        );
        chim2.position.set(0.8, 3.7, 0.8);
        chim2.castShadow = true;
        group.add(chim2);

        // smoke
        for (let c = 0; c < 2; c++) {
            const cx = c === 0 ? -1.0 : 0.8;
            for (let i = 0; i < 4; i++) {
                const puff = new THREE.Mesh(
                    new THREE.SphereGeometry(0.1 + Math.random() * 0.1, 6, 6),
                    new THREE.MeshStandardMaterial({
                        color: 0xbbbbbb,
                        transparent: true,
                        opacity: 0.4 - i * 0.08
                    })
                );
                puff.position.set(
                    cx + (Math.random() - 0.5) * 0.2,
                    4.5 + i * 0.4,
                    0.8 + (Math.random() - 0.5) * 0.2
                );
                group.add(puff);
            }
        }

        group.position.set(pos.x, pos.y, pos.z);
        this.group.add(group);
        this.buildingMeshes.push(group);
    }

    // ─── Residential ──────────────────────────────────────────────────────
    _createResidential(pos) {
        const group = new THREE.Group();
        const s = zoneColors.Residential;

        // house body
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(1.8, 1.2, 1.8),
            new THREE.MeshStandardMaterial({ color: 0xf5e6c8, roughness: 0.7 })
        );
        body.position.y = 0.75;
        body.castShadow = true;
        body.receiveShadow = true;
        group.add(body);

        // pitched roof
        const roofGeo = new THREE.BufferGeometry();
        const roofVerts = new Float32Array([
            // left slope
            -1.1, 0, -1.1,   1.1, 0, -1.1,   0, 0.7, 0,
            // right slope
            -1.1, 0, 1.1,   1.1, 0, 1.1,   0, 0.7, 0,
            // front gable
            -1.1, 0, -1.1,   0, 0.7, 0,   -1.1, 0, 1.1,
            // back gable
            1.1, 0, -1.1,   0, 0.7, 0,   1.1, 0, 1.1,
            // top left
            -1.1, 0, -1.1,   0, 0.7, 0,   1.1, 0, -1.1,
            // top right
            -1.1, 0, 1.1,   0, 0.7, 0,   1.1, 0, 1.1,
        ]);
        roofGeo.setAttribute('position', new THREE.BufferAttribute(roofVerts, 3));
        roofGeo.computeVertexNormals();
        const roof = new THREE.Mesh(
            roofGeo,
            new THREE.MeshStandardMaterial({ color: 0x8b4513, side: THREE.DoubleSide })
        );
        roof.position.y = 1.35;
        roof.castShadow = true;
        group.add(roof);

        // chimney
        const chimney = new THREE.Mesh(
            new THREE.BoxGeometry(0.25, 0.6, 0.25),
            new THREE.MeshStandardMaterial({ color: 0x996644 })
        );
        chimney.position.set(0.5, 1.95, -0.3);
        chimney.castShadow = true;
        group.add(chimney);

        // door
        const door = new THREE.Mesh(
            new THREE.BoxGeometry(0.35, 0.55, 0.05),
            new THREE.MeshStandardMaterial({ color: 0x8b4513 })
        );
        door.position.set(0, 0.53, 0.93);
        group.add(door);

        // window
        const winMat = new THREE.MeshStandardMaterial({
            color: 0x88ccee,
            emissive: 0x446688,
            emissiveIntensity: 0.2
        });
        const win1 = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.3, 0.05), winMat);
        win1.position.set(-0.5, 0.8, 0.93);
        group.add(win1);

        const win2 = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.3, 0.05), winMat);
        win2.position.set(0.5, 0.8, 0.93);
        group.add(win2);

        group.position.set(pos.x, pos.y, pos.z);
        this.group.add(group);
        this.buildingMeshes.push(group);
    }

    // ─── Park / Empty ─────────────────────────────────────────────────────
    _createPark(pos) {
        const group = new THREE.Group();

        // tree trunk
        const trunk = new THREE.Mesh(
            new THREE.CylinderGeometry(0.08, 0.12, 0.8, 6),
            new THREE.MeshStandardMaterial({ color: 0x8b6914 })
        );
        trunk.position.set(0, 0.55, 0);
        trunk.castShadow = true;
        group.add(trunk);

        // tree canopy
        const canopy = new THREE.Mesh(
            new THREE.SphereGeometry(0.6, 8, 8),
            new THREE.MeshStandardMaterial({ color: 0x228b22 })
        );
        canopy.position.set(0, 1.4, 0);
        canopy.castShadow = true;
        group.add(canopy);

        // bench
        const benchSeat = new THREE.Mesh(
            new THREE.BoxGeometry(0.6, 0.05, 0.2),
            new THREE.MeshStandardMaterial({ color: 0x8b4513 })
        );
        benchSeat.position.set(0.8, 0.35, 0.5);
        group.add(benchSeat);

        const benchLeg1 = new THREE.Mesh(
            new THREE.BoxGeometry(0.05, 0.35, 0.05),
            new THREE.MeshStandardMaterial({ color: 0x666666 })
        );
        benchLeg1.position.set(0.55, 0.175, 0.5);
        group.add(benchLeg1);

        const benchLeg2 = new THREE.Mesh(
            new THREE.BoxGeometry(0.05, 0.35, 0.05),
            new THREE.MeshStandardMaterial({ color: 0x666666 })
        );
        benchLeg2.position.set(1.05, 0.175, 0.5);
        group.add(benchLeg2);

        // second smaller tree
        const trunk2 = new THREE.Mesh(
            new THREE.CylinderGeometry(0.06, 0.1, 0.6, 6),
            new THREE.MeshStandardMaterial({ color: 0x8b6914 })
        );
        trunk2.position.set(-0.7, 0.45, -0.5);
        group.add(trunk2);

        const canopy2 = new THREE.Mesh(
            new THREE.SphereGeometry(0.45, 8, 8),
            new THREE.MeshStandardMaterial({ color: 0x2e8b2e })
        );
        canopy2.position.set(-0.7, 1.1, -0.5);
        canopy2.castShadow = true;
        group.add(canopy2);

        // small flower bed
        const flowers = new THREE.Mesh(
            new THREE.CylinderGeometry(0.25, 0.25, 0.08, 8),
            new THREE.MeshStandardMaterial({ color: 0xff69b4 })
        );
        flowers.position.set(-0.3, 0.19, 0.7);
        group.add(flowers);

        group.position.set(pos.x, pos.y, pos.z);
        this.group.add(group);
        this.buildingMeshes.push(group);
    }

    // ─── helper: add windows to a building ────────────────────────────────
    _addWindows(group, width, height, color) {
        const winMat = new THREE.MeshStandardMaterial({
            color: 0x88ccee,
            emissive: 0x446688,
            emissiveIntensity: 0.15
        });

        const winW = 0.3;
        const winH = 0.3;
        const cols = 3;
        const rows = 2;
        const spacingX = width / (cols + 1);
        const spacingY = height / (rows + 1);

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const x = -width / 2 + spacingX * (c + 1);
                const y = spacingY * (r + 1) + 0.3;

                const win = new THREE.Mesh(
                    new THREE.BoxGeometry(winW, winH, 0.05),
                    winMat
                );
                win.position.set(x, y, width / 2 + 0.01);
                group.add(win);
            }
        }
    }
}
