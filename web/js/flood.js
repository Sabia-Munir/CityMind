// flood.js — BIG visible flood water on roads
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
    }

    addFlood(row1, col1, row2, col2, floodId) {
        const wp1 = this.terrain.gridToWorld(row1, col1);
        const wp2 = this.terrain.gridToWorld(row2, col2);
        const midX = (wp1.x + wp2.x) / 2;
        const midZ = (wp1.z + wp2.z) / 2;
        const isH = Math.abs(row1 - row2) < 0.01;
        const w = isH ? TILE_SIZE + 1.5 : TILE_SIZE * 0.85;
        const d = isH ? TILE_SIZE * 0.85 : TILE_SIZE + 1.5;

        // BIG bright blue water block
        const water = new THREE.Mesh(
            new THREE.BoxGeometry(w, 0.5, d),
            new THREE.MeshStandardMaterial({ color: 0x0088ff, emissive: 0x0044aa, emissiveIntensity: 0.5, transparent: true, opacity: 0.85, roughness: 0.1, metalness: 0.3 })
        );
        water.position.set(midX, 0.35, midZ);
        water.name = `flood_${floodId}`;
        this.group.add(water);

        // bright shimmer top
        const shimmer = new THREE.Mesh(
            new THREE.PlaneGeometry(w * 0.9, d * 0.9),
            new THREE.MeshBasicMaterial({ color: 0x44ccff, transparent: true, opacity: 0.5, side: THREE.DoubleSide })
        );
        shimmer.rotation.x = -Math.PI / 2;
        shimmer.position.set(midX, 0.62, midZ);
        shimmer.name = `shimmer_${floodId}`;
        this.group.add(shimmer);

        // warning sign post
        const post = new THREE.Mesh(
            new THREE.CylinderGeometry(0.06, 0.06, 1.5, 6),
            new THREE.MeshStandardMaterial({ color: 0xaaaaaa, metalness: 0.4 })
        );
        post.position.set(midX + w * 0.4, 1.1, midZ + d * 0.3);
        post.name = `post_${floodId}`;
        this.group.add(post);

        // warning triangle
        const shape = new THREE.Shape();
        shape.moveTo(0, 0.4); shape.lineTo(-0.25, 0); shape.lineTo(0.25, 0); shape.closePath();
        const tri = new THREE.Mesh(
            new THREE.ShapeGeometry(shape),
            new THREE.MeshStandardMaterial({ color: 0xffcc00, emissive: 0xff6600, emissiveIntensity: 0.8, side: THREE.DoubleSide })
        );
        tri.position.set(midX + w * 0.4, 1.85, midZ + d * 0.3);
        tri.name = `warning_${floodId}`;
        this.group.add(tri);

        // "FLOODED" text marker — red exclamation box
        const marker = new THREE.Mesh(
            new THREE.BoxGeometry(0.5, 0.5, 0.1),
            new THREE.MeshStandardMaterial({ color: 0xff0000, emissive: 0xff0000, emissiveIntensity: 0.6 })
        );
        marker.position.set(midX, 0.7, midZ);
        marker.rotation.x = -Math.PI / 2;
        marker.name = `marker_${floodId}`;
        this.group.add(marker);

        this.floodPlanes.push({ id: floodId, water, shimmer, row1, col1, row2, col2 });
    }

    removeFlood(floodId) {
        const toRemove = this.group.children.filter(c => c.name.includes(floodId));
        toRemove.forEach(obj => { this.group.remove(obj); obj.geometry?.dispose(); obj.material?.dispose(); });
        this.floodPlanes = this.floodPlanes.filter(f => f.id !== floodId);
    }

    removeFloodByEdge(r1, c1, r2, c2) {
        const match = this.floodPlanes.find(f =>
            (f.row1===r1&&f.col1===c1&&f.row2===r2&&f.col2===c2) ||
            (f.row1===r2&&f.col1===c2&&f.row2===r1&&f.col2===c1));
        if (match) this.removeFlood(match.id);
    }

    clearAll() {
        [...this.group.children].forEach(obj => { this.group.remove(obj); obj.geometry?.dispose(); obj.material?.dispose(); });
        this.floodPlanes = [];
    }

    update(delta) {
        // NO vertex modification — just bob positions to avoid black screen
        this.floodPlanes.forEach(flood => {
            flood.water.position.y = 0.35 + Math.sin(Date.now() * 0.002) * 0.05;
            flood.shimmer.material.opacity = 0.35 + Math.sin(Date.now() * 0.003) * 0.15;
        });
    }
}
