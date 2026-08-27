// vehicles.js — 3D ambulance models with smooth path animation
import * as THREE from 'three';
import { ambulancePositions } from './cityData.js';

const TILE_SIZE = 4;

export class VehicleSystem {
    constructor(scene, terrain) {
        this.scene = scene;
        this.terrain = terrain;
        this.group = new THREE.Group();
        this.group.name = 'vehicles';
        this.scene.add(this.group);
        this.ambulances = [];
        this.paths = [];
        this.animationSpeed = 3.0; // tiles per second

        this._createAmbulances();
    }

    _createAmbulances() {
        ambulancePositions.forEach((pos, index) => {
            const ambulance = this._buildAmbulance(index);
            const worldPos = this.terrain.gridToWorld(pos[0], pos[1]);
            ambulance.position.copy(worldPos);
            ambulance.position.y = 0.3;
            this.group.add(ambulance);
            this.ambulances.push({
                mesh: ambulance,
                gridPos: [...pos],
                worldPos: worldPos.clone(),
                targetWorldPos: worldPos.clone(),
                path: [],
                pathIndex: 0,
                moving: false,
                speed: this.animationSpeed + Math.random() * 0.5,
                lightPhase: Math.random() * Math.PI * 2,
            });
        });
    }

    _buildAmbulance(index) {
        const group = new THREE.Group();

        // body
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(0.9, 0.5, 1.6),
            new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.4 })
        );
        body.position.y = 0.35;
        body.castShadow = true;
        body.receiveShadow = true;
        group.add(body);

        // cabin (front)
        const cabin = new THREE.Mesh(
            new THREE.BoxGeometry(0.8, 0.4, 0.5),
            new THREE.MeshStandardMaterial({ color: 0xeeeeee })
        );
        cabin.position.set(0, 0.55, -0.5);
        cabin.castShadow = true;
        group.add(cabin);

        // windshield
        const windshield = new THREE.Mesh(
            new THREE.BoxGeometry(0.7, 0.3, 0.05),
            new THREE.MeshStandardMaterial({
                color: 0x88ccff,
                transparent: true,
                opacity: 0.6,
                metalness: 0.3
            })
        );
        windshield.position.set(0, 0.6, -0.76);
        group.add(windshield);

        // red cross on side
        const crossH = new THREE.Mesh(
            new THREE.BoxGeometry(0.02, 0.2, 0.4),
            new THREE.MeshStandardMaterial({ color: 0xff0000 })
        );
        crossH.position.set(0.47, 0.45, 0.1);
        group.add(crossH);

        const crossV = new THREE.Mesh(
            new THREE.BoxGeometry(0.02, 0.4, 0.2),
            new THREE.MeshStandardMaterial({ color: 0xff0000 })
        );
        crossV.position.set(0.47, 0.45, 0.1);
        group.add(crossV);

        // other side cross
        const crossH2 = crossH.clone();
        crossH2.position.x = -0.47;
        group.add(crossH2);

        const crossV2 = crossV.clone();
        crossV2.position.x = -0.47;
        group.add(crossV2);

        // emergency lights (roof)
        const lightBar = new THREE.Mesh(
            new THREE.BoxGeometry(0.6, 0.1, 0.2),
            new THREE.MeshStandardMaterial({ color: 0x333333 })
        );
        lightBar.position.set(0, 0.65, 0.1);
        group.add(lightBar);

        const lightRed = new THREE.Mesh(
            new THREE.SphereGeometry(0.08, 8, 8),
            new THREE.MeshStandardMaterial({
                color: 0xff0000,
                emissive: 0xff0000,
                emissiveIntensity: 1.0
            })
        );
        lightRed.position.set(-0.2, 0.75, 0.1);
        lightRed.name = 'lightRed';
        group.add(lightRed);

        const lightBlue = new THREE.Mesh(
            new THREE.SphereGeometry(0.08, 8, 8),
            new THREE.MeshStandardMaterial({
                color: 0x0044ff,
                emissive: 0x0044ff,
                emissiveIntensity: 1.0
            })
        );
        lightBlue.position.set(0.2, 0.75, 0.1);
        lightBlue.name = 'lightBlue';
        group.add(lightBlue);

        // wheels
        const wheelMat = new THREE.MeshStandardMaterial({ color: 0x222222 });
        const wheelGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.1, 8);

        const wheelPositions = [
            [-0.45, 0.12, -0.45],
            [0.45, 0.12, -0.45],
            [-0.45, 0.12, 0.45],
            [0.45, 0.12, 0.45],
        ];
        wheelPositions.forEach(wp => {
            const wheel = new THREE.Mesh(wheelGeo, wheelMat);
            wheel.position.set(...wp);
            wheel.rotation.z = Math.PI / 2;
            group.add(wheel);
        });

        // point light for emergency glow
        const emergencyLight = new THREE.PointLight(0xff4444, 0, 4);
        emergencyLight.position.set(0, 1.0, 0);
        emergencyLight.name = 'emergencyLight';
        group.add(emergencyLight);

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

    update(delta, elapsedTime) {
        this.ambulances.forEach(amb => {
            // flash emergency lights
            amb.lightPhase += delta * 6;
            const flash = Math.sin(amb.lightPhase) > 0;

            const redLight = amb.mesh.getObjectByName('lightRed');
            const blueLight = amb.mesh.getObjectByName('lightBlue');
            const emergencyPt = amb.mesh.getObjectByName('emergencyLight');

            if (redLight) redLight.material.emissiveIntensity = flash ? 1.0 : 0.1;
            if (blueLight) blueLight.material.emissiveIntensity = flash ? 0.1 : 1.0;
            if (emergencyPt) emergencyPt.intensity = flash ? 2.0 : 0.5;

            // color of emergency light
            if (emergencyPt) {
                emergencyPt.color.setHex(flash ? 0xff0000 : 0x0044ff);
            }

            // movement along path
            if (amb.moving && amb.path.length > 0) {
                const current = amb.mesh.position;
                const target = amb.targetWorldPos;
                const dist = current.distanceTo(target);

                if (dist < 0.1) {
                    amb.pathIndex++;
                    if (amb.pathIndex >= amb.path.length) {
                        amb.moving = false;
                        amb.pathIndex = 0;
                    } else {
                        amb.targetWorldPos.copy(amb.path[amb.pathIndex]);
                    }
                } else {
                    const dir = new THREE.Vector3().subVectors(target, current).normalize();
                    const moveAmount = amb.speed * delta;
                    current.add(dir.multiplyScalar(Math.min(moveAmount, dist)));
                    current.y = 0.3; // keep on ground

                    // rotate vehicle to face direction
                    const angle = Math.atan2(dir.x, dir.z);
                    amb.mesh.rotation.y = angle;
                }
            }
        });
    }

    // Move ambulance to a new grid position instantly
    teleportTo(index, row, col) {
        if (index >= this.ambulances.length) return;
        const amb = this.ambulances[index];
        const worldPos = this.terrain.gridToWorld(row, col);
        amb.mesh.position.copy(worldPos);
        amb.mesh.position.y = 0.3;
        amb.gridPos = [row, col];
        amb.worldPos.copy(worldPos);
        amb.targetWorldPos.copy(worldPos);
        amb.moving = false;
    }
}
