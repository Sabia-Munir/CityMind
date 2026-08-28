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
    }

    addFlood(row1, col1, row2, col2, floodId) {
        const wp1 = this.terrain.gridToWorld(row1, col1);
        const wp2 = this.terrain.gridToWorld(row2, col2);

        const midX = (wp1.x + wp2.x) / 2;
        const midZ = (wp1.z + wp2.z) / 2;

        const isHorizontal = Math.abs(row1 - row2) < 0.01;
        const w = isHorizontal ? TILE_SIZE + 1.0 : TILE_SIZE * 0.9;
        const d = isHorizontal ? TILE_SIZE * 0.9 : TILE_SIZE + 1.0;

        // main water surface — raised above road
        const waterGeo = new THREE.BoxGeometry(w, 0.25, d);
        const waterMat = new THREE.MeshStandardMaterial({
            color: 0x2090dd,
            transparent: true,
            opacity: 0.75,
            roughness: 0.1,
            metalness: 0.4,
        });
        const water = new THREE.Mesh(waterGeo, waterMat);
        water.position.set(midX, 0.22, midZ);
        water.name = `flood_${floodId}`;
        water.receiveShadow = true;
        this.group.add(water);

        // surface highlight (top shimmer)
        const shimmerGeo = new THREE.PlaneGeometry(w * 0.8, d * 0.8);
        const shimmerMat = new THREE.MeshBasicMaterial({
            color: 0x88ccff,
            transparent: true,
            opacity: 0.35,
            side: THREE.DoubleSide,
        });
        const shimmer = new THREE.Mesh(shimmerGeo, shimmerMat);
        shimmer.rotation.x = -Math.PI / 2;
        shimmer.position.set(midX, 0.36, midZ);
        shimmer.name = `shimmer_${floodId}`;
        this.group.add(shimmer);

        // warning sign post
        const post = new THREE.Mesh(
            new THREE.CylinderGeometry(0.04, 0.04, 0.8, 6),
            new THREE.MeshStandardMaterial({ color: 0x888888 })
        );
        post.position.set(midX + w * 0.35, 0.65, midZ);
        post.name = `post_${floodId}`;
        this.group.add(post);

        // warning triangle
        const triShape = new THREE.Shape();
        triShape.moveTo(0, 0.25);
        triShape.lineTo(-0.15, 0);
        triShape.lineTo(0.15, 0);
        triShape.closePath();
        const triGeo = new THREE.ShapeGeometry(triShape);
        const triMat = new THREE.MeshStandardMaterial({
            color: 0xffcc00,
            emissive: 0xff8800,
            emissiveIntensity: 0.4,
            side: THREE.DoubleSide,
        });
        const tri = new THREE.Mesh(triGeo, triMat);
        tri.position.set(midX + w * 0.35, 1.05, midZ);
        tri.name = `warning_${floodId}`;
        this.group.add(tri);

        this.floodPlanes.push({
            id: floodId,
            water,
            shimmer,
            time: Math.random() * 10,
            row1, col1, row2, col2,
        });
    }

    removeFlood(floodId) {
        const toRemove = [];
        this.group.children.forEach(child => {
            if (child.name.includes(floodId)) {
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

    removeFloodByEdge(r1, c1, r2, c2) {
        const match = this.floodPlanes.find(f =>
            (f.row1 === r1 && f.col1 === c1 && f.row2 === r2 && f.col2 === c2) ||
            (f.row1 === r2 && f.col1 === c2 && f.row2 === r1 && f.col2 === c1)
        );
        if (match) this.removeFlood(match.id);
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
        this.floodPlanes.forEach(flood => {
            flood.time += delta;

            // bob the water
            flood.water.position.y = 0.22 + Math.sin(flood.time * 1.5) * 0.03;

            // shimmer pulse
            if (flood.shimmer) {
                flood.shimmer.material.opacity = 0.25 + Math.sin(flood.time * 2) * 0.15;
            }
        });
    }
}
