// civilians.js — show civilian SOS markers on the 3D map
import * as THREE from 'three';
import { zoneGrid } from './cityData.js';

const TILE_SIZE = 4;

export class CivilianSystem {
    constructor(scene, terrain) {
        this.scene = scene;
        this.terrain = terrain;
        this.group = new THREE.Group();
        this.group.name = 'civilians';
        this.scene.add(this.group);
        this.markers = [];
    }

    showCivilians(positions) {
        this.clearAll();
        positions.forEach((pos, i) => {
            const wp = this.terrain.gridToWorld(pos[0], pos[1]);
            const g = new THREE.Group();

            // person body
            const body = new THREE.Mesh(
                new THREE.CylinderGeometry(0.08, 0.12, 0.5, 8),
                new THREE.MeshStandardMaterial({ color: 0xffaa44 })
            );
            body.position.y = 0.45;
            g.add(body);

            // head
            const head = new THREE.Mesh(
                new THREE.SphereGeometry(0.1, 8, 8),
                new THREE.MeshStandardMaterial({ color: 0xffcc88 })
            );
            head.position.y = 0.78;
            g.add(head);

            // SOS flag
            const flag = new THREE.Mesh(
                new THREE.BoxGeometry(0.02, 0.3, 0.02),
                new THREE.MeshStandardMaterial({ color: 0x888888 })
            );
            flag.position.set(0.2, 0.7, 0);
            g.add(flag);

            const flagPlane = new THREE.Mesh(
                new THREE.PlaneGeometry(0.25, 0.12),
                new THREE.MeshStandardMaterial({ color: 0xff0000, emissive: 0xff0000, emissiveIntensity: 0.3, side: THREE.DoubleSide })
            );
            flagPlane.position.set(0.33, 0.82, 0);
            flagPlane.name = `sosFlag_${i}`;
            g.add(flagPlane);

            // bobbing animation data
            g.position.set(wp.x, 0, wp.z);
            this.group.add(g);
            this.markers.push({ mesh: g, phase: i * 0.8, rescued: false });
        });
    }

    markRescued(index) {
        if (index < this.markers.length) {
            this.markers[index].rescued = true;
            this.markers[index].mesh.visible = false;
        }
    }

    clearAll() {
        [...this.group.children].forEach(obj => { this.group.remove(obj); });
        this.markers = [];
    }

    update(elapsed) {
        this.markers.forEach(m => {
            if (m.rescued || !m.mesh.visible) return;
            m.mesh.position.y = Math.sin(elapsed * 2 + m.phase) * 0.08;
        });
    }
}
