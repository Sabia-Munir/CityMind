// flood.js — water plane effects on blocked roads with animated ripples
import * as THREE from 'three';

const TILE_SIZE = 4;

export class FloodSystem {
    constructor(scene, terrain) {
        this.scene = scene;
        this.terrain = terrain;
        this.group = new THREE.Group();
        this.group.name = 'floods';
        this.scene.add(this.group);
        this.floodPlanes = [];
        this.rippleTime = 0;
    }

    addFlood(row1, col1, row2, col2, floodId) {
        const wp1 = this.terrain.gridToWorld(row1, col1);
        const wp2 = this.terrain.gridToWorld(row2, col2);

        const midX = (wp1.x + wp2.x) / 2;
        const midZ = (wp1.z + wp2.z) / 2;

        const isHorizontal = Math.abs(row1 - row2) < 0.01;
        const width = isHorizontal ? TILE_SIZE + 0.5 : TILE_SIZE * 0.8;
        const depth = isHorizontal ? TILE_SIZE * 0.8 : TILE_SIZE + 0.5;

        // water plane
        const waterGeo = new THREE.PlaneGeometry(width, depth, 16, 16);
        const waterMat = new THREE.MeshStandardMaterial({
            color: 0x2080cc,
            transparent: true,
            opacity: 0.65,
            roughness: 0.2,
            metalness: 0.3,
            side: THREE.DoubleSide,
        });
        const water = new THREE.Mesh(waterGeo, waterMat);
        water.rotation.x = -Math.PI / 2;
        water.position.set(midX, 0.15, midZ);
        water.name = `flood_${floodId}`;
        this.group.add(water);

        // floating debris
        for (let i = 0; i < 3; i++) {
            const debris = new THREE.Mesh(
                new THREE.BoxGeometry(0.15, 0.05, 0.15),
                new THREE.MeshStandardMaterial({ color: 0x8b6914 })
            );
            debris.position.set(
                midX + (Math.random() - 0.5) * width * 0.6,
                0.18,
                midZ + (Math.random() - 0.5) * depth * 0.6
            );
            debris.rotation.y = Math.random() * Math.PI;
            debris.name = `debris_${floodId}_${i}`;
            this.group.add(debris);
        }

        // warning sign (floating triangle)
        const signGroup = new THREE.Group();
        const signGeo = new THREE.BufferGeometry();
        const verts = new Float32Array([
            0, 0.3, 0,   -0.15, 0, 0,   0.15, 0, 0
        ]);
        signGeo.setAttribute('position', new THREE.BufferAttribute(verts, 3));
        signGeo.computeVertexNormals();
        const signMat = new THREE.MeshStandardMaterial({
            color: 0xffcc00,
            emissive: 0xff8800,
            emissiveIntensity: 0.3,
            side: THREE.DoubleSide
        });
        const sign = new THREE.Mesh(signGeo, signMat);
        sign.position.set(midX, 0.5, midZ);
        sign.name = `sign_${floodId}`;
        this.group.add(sign);

        this.floodPlanes.push({
            id: floodId,
            water,
            debris: [],
            sign,
            time: Math.random() * 10,
        });
    }

    removeFlood(floodId) {
        const toRemove = [];
        this.group.children.forEach(child => {
            if (child.name.startsWith(`flood_${floodId}`) ||
                child.name.startsWith(`debris_${floodId}`) ||
                child.name.startsWith(`sign_${floodId}`)) {
                toRemove.push(child);
            }
        });
        toRemove.forEach(obj => {
            this.group.remove(obj);
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
        this.floodPlanes = this.floodPlanes.filter(f => f.id !== floodId);
    }

    clearAll() {
        const toRemove = [...this.group.children];
        toRemove.forEach(obj => {
            this.group.remove(obj);
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
        this.floodPlanes = [];
    }

    update(delta) {
        this.rippleTime += delta;

        this.floodPlanes.forEach(flood => {
            flood.time += delta;

            // ripple the water vertices
            const geo = flood.water.geometry;
            const pos = geo.attributes.position;
            for (let i = 0; i < pos.count; i++) {
                const x = pos.getX(i);
                const y = pos.getY(i);
                const ripple = Math.sin(x * 2 + flood.time * 2) * 0.03 +
                               Math.cos(y * 2.5 + flood.time * 1.5) * 0.02;
                pos.setZ(i, ripple);
            }
            pos.needsUpdate = true;
            geo.computeVertexNormals();

            // bob the debris
            this.group.children.forEach(child => {
                if (child.name.startsWith(`debris_${flood.id}`)) {
                    child.position.y = 0.17 + Math.sin(flood.time * 1.5 + child.position.x) * 0.03;
                    child.rotation.y += delta * 0.3;
                }
            });

            // bob the warning sign
            if (flood.sign) {
                flood.sign.position.y = 0.45 + Math.sin(flood.time * 2) * 0.05;
                flood.sign.rotation.y += delta * 0.5;
            }
        });
    }
}
