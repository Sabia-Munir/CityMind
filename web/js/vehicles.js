// vehicles.js — 3D ambulance models with smooth path animation
import * as THREE from 'three';
import { ambulancePositions } from './cityData.js';

const TILE_SIZE = 4;

// Ambulances placed at road midpoints (between cells), not inside buildings
// Road from (0,4)→(0,5), (5,3)→(5,4), (9,6)→(9,7)
const AMBULANCE_ROAD_POSITIONS = [
    { row: 0, col: 0.5 },   // on road between (0,4) and (0,5)
    { row: 5, col: 3.5 },   // on road between (5,3) and (5,4)
    { row: 9, col: 6.5 },   // on road between (9,6) and (9,7)
];

export class VehicleSystem {
    constructor(scene, terrain) {
        this.scene = scene;
        this.terrain = terrain;
        this.group = new THREE.Group();
        this.group.name = 'vehicles';
        this.scene.add(this.group);
        this.ambulances = [];
        this.animationSpeed = 2.5;

        this._createAmbulances();
    }

    _createAmbulances() {
        AMBULANCE_ROAD_POSITIONS.forEach((pos, index) => {
            const ambulance = this._buildAmbulance(index);
            const worldPos = this.terrain.gridToWorld(pos.row, pos.col);
            ambulance.position.set(worldPos.x, 0.15, worldPos.z);
            this.group.add(ambulance);
            this.ambulances.push({
                mesh: ambulance,
                gridPos: [pos.row, pos.col],
                worldPos: worldPos.clone(),
                targetWorldPos: worldPos.clone(),
                path: [],
                pathIndex: 0,
                moving: false,
                speed: this.animationSpeed,
                lightPhase: Math.random() * Math.PI * 2,
            });
        });
    }

    _buildAmbulance(index) {
        const group = new THREE.Group();
        const scale = 1.4;

        // body
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(0.9 * scale, 0.5 * scale, 1.6 * scale),
            new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.35, metalness: 0.1 })
        );
        body.position.y = 0.35 * scale;
        body.castShadow = true;
        body.receiveShadow = true;
        group.add(body);

        // cabin (front)
        const cabin = new THREE.Mesh(
            new THREE.BoxGeometry(0.8 * scale, 0.4 * scale, 0.5 * scale),
            new THREE.MeshStandardMaterial({ color: 0xeeeeee })
        );
        cabin.position.set(0, 0.55 * scale, -0.5 * scale);
        cabin.castShadow = true;
        group.add(cabin);

        // windshield
        const windshield = new THREE.Mesh(
            new THREE.BoxGeometry(0.7 * scale, 0.3 * scale, 0.05),
            new THREE.MeshStandardMaterial({ color: 0x88ccff, transparent: true, opacity: 0.6, metalness: 0.3 })
        );
        windshield.position.set(0, 0.6 * scale, -0.76 * scale);
        group.add(windshield);

        // red cross on both sides
        const crossMat = new THREE.MeshStandardMaterial({ color: 0xff0000, emissive: 0xff0000, emissiveIntensity: 0.3 });
        [0.47, -0.47].forEach(xOff => {
            const h = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.2 * scale, 0.4 * scale), crossMat);
            h.position.set(xOff * scale, 0.45 * scale, 0.1);
            group.add(h);
            const v = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.4 * scale, 0.2 * scale), crossMat);
            v.position.set(xOff * scale, 0.45 * scale, 0.1);
            group.add(v);
        });

        // front cross
        const fh = new THREE.Mesh(new THREE.BoxGeometry(0.3 * scale, 0.04, 0.02), crossMat);
        fh.position.set(0, 0.4 * scale, -0.81 * scale);
        group.add(fh);
        const fv = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.3 * scale, 0.02), crossMat);
        fv.position.set(0, 0.4 * scale, -0.81 * scale);
        group.add(fv);

        // light bar
        const lightBar = new THREE.Mesh(
            new THREE.BoxGeometry(0.6 * scale, 0.12, 0.22),
            new THREE.MeshStandardMaterial({ color: 0x333333, metalness: 0.5 })
        );
        lightBar.position.set(0, 0.68 * scale, 0.1);
        group.add(lightBar);

        const lightRed = new THREE.Mesh(
            new THREE.SphereGeometry(0.1 * scale, 8, 8),
            new THREE.MeshStandardMaterial({ color: 0xff0000, emissive: 0xff0000, emissiveIntensity: 1.0 })
        );
        lightRed.position.set(-0.2 * scale, 0.78 * scale, 0.1);
        lightRed.name = 'lightRed';
        group.add(lightRed);

        const lightBlue = new THREE.Mesh(
            new THREE.SphereGeometry(0.1 * scale, 8, 8),
            new THREE.MeshStandardMaterial({ color: 0x0044ff, emissive: 0x0044ff, emissiveIntensity: 1.0 })
        );
        lightBlue.position.set(0.2 * scale, 0.78 * scale, 0.1);
        lightBlue.name = 'lightBlue';
        group.add(lightBlue);

        // wheels
        const wheelMat = new THREE.MeshStandardMaterial({ color: 0x222222 });
        const wheelGeo = new THREE.CylinderGeometry(0.13 * scale, 0.13 * scale, 0.1 * scale, 8);
        [[-0.45, -0.45], [0.45, -0.45], [-0.45, 0.45], [0.45, 0.45]].forEach(([x, z]) => {
            const wheel = new THREE.Mesh(wheelGeo, wheelMat);
            wheel.position.set(x * scale, 0.13 * scale, z * scale);
            wheel.rotation.z = Math.PI / 2;
            group.add(wheel);
        });

        // emergency point light
        const ptLight = new THREE.PointLight(0xff4444, 0, 5);
        ptLight.position.set(0, 1.2, 0);
        ptLight.name = 'emergencyLight';
        group.add(ptLight);

        return group;
    }

    setPath(ambulanceIndex, pathCoords) {
        if (ambulanceIndex >= this.ambulances.length) return;
        const amb = this.ambulances[ambulanceIndex];
        amb.path = pathCoords.map(([r, c]) => this.terrain.gridToWorld(r, c));
        amb.pathIndex = 0;
        amb.moving = amb.path.length > 0;
        if (amb.path.length > 0) {
            amb.targetWorldPos.copy(amb.path[0]);
        }
    }

    update(delta) {
        this.ambulances.forEach(amb => {
            // flash lights
            amb.lightPhase += delta * 6;
            const flash = Math.sin(amb.lightPhase) > 0;

            const red = amb.mesh.getObjectByName('lightRed');
            const blue = amb.mesh.getObjectByName('lightBlue');
            const pt = amb.mesh.getObjectByName('emergencyLight');
            if (red) red.material.emissiveIntensity = flash ? 1.0 : 0.1;
            if (blue) blue.material.emissiveIntensity = flash ? 0.1 : 1.0;
            if (pt) {
                pt.intensity = flash ? 3.0 : 0.5;
                pt.color.setHex(flash ? 0xff0000 : 0x0044ff);
            }

            // move along path
            if (amb.moving && amb.path.length > 0) {
                const pos = amb.mesh.position;
                const tgt = amb.targetWorldPos;
                const dist = pos.distanceTo(tgt);

                if (dist < 0.15) {
                    amb.pathIndex++;
                    if (amb.pathIndex >= amb.path.length) {
                        amb.moving = false;
                        amb.pathIndex = 0;
                    } else {
                        amb.targetWorldPos.copy(amb.path[amb.pathIndex]);
                    }
                } else {
                    const dir = new THREE.Vector3().subVectors(tgt, pos).normalize();
                    const moveAmt = amb.speed * delta;
                    pos.add(dir.multiplyScalar(Math.min(moveAmt, dist)));
                    pos.y = 0.15;
                    amb.mesh.rotation.y = Math.atan2(dir.x, dir.z);
                }
            }
        });
    }

    teleportTo(index, row, col) {
        if (index >= this.ambulances.length) return;
        const amb = this.ambulances[index];
        const wp = this.terrain.gridToWorld(row, col);
        amb.mesh.position.set(wp.x, 0.15, wp.z);
        amb.gridPos = [row, col];
        amb.worldPos.copy(wp);
        amb.targetWorldPos.copy(wp);
        amb.moving = false;
    }
}
