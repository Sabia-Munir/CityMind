// path.js — 3D path visualization with glowing lines and pulsing nodes
import * as THREE from 'three';

export class PathVisualizer {
    constructor(scene, terrain) {
        this.scene = scene;
        this.terrain = terrain;
        this.group = new THREE.Group();
        this.group.name = 'paths';
        this.scene.add(this.group);
        this.activePaths = [];
        this.pathNodes = [];
    }

    showPath(coords, color = 0x3cff8c, pathId = 'default') {
        this.clearPath(pathId);

        if (coords.length < 2) return;

        const points = coords.map(([r, c]) => {
            const wp = this.terrain.gridToWorld(r, c);
            return new THREE.Vector3(wp.x, 0.4, wp.z);
        });

        // main path tube
        const curve = new THREE.CatmullRomCurve3(points, false, 'catmullrom', 0.2);
        const tubeGeo = new THREE.TubeGeometry(curve, points.length * 4, 0.12, 8, false);
        const tubeMat = new THREE.MeshStandardMaterial({
            color: color,
            emissive: color,
            emissiveIntensity: 0.6,
            transparent: true,
            opacity: 0.85,
            roughness: 0.3,
        });
        const tube = new THREE.Mesh(tubeGeo, tubeMat);
        tube.name = `path_${pathId}`;
        this.group.add(tube);

        // glow effect (wider transparent tube)
        const glowGeo = new THREE.TubeGeometry(curve, points.length * 4, 0.25, 8, false);
        const glowMat = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.2,
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        glow.name = `pathGlow_${pathId}`;
        this.group.add(glow);

        // pulsing nodes at each waypoint
        points.forEach((pt, i) => {
            const nodeGeo = new THREE.SphereGeometry(0.15, 12, 12);
            const nodeMat = new THREE.MeshStandardMaterial({
                color: color,
                emissive: color,
                emissiveIntensity: 0.8,
                transparent: true,
                opacity: 0.9,
            });
            const node = new THREE.Mesh(nodeGeo, nodeMat);
            node.position.copy(pt);
            node.position.y = 0.4;
            node.name = `pathNode_${pathId}_${i}`;
            this.group.add(node);
            this.pathNodes.push({ mesh: node, phase: i * 0.5 });
        });

        // direction arrows along path
        for (let i = 0; i < points.length - 1; i++) {
            const start = points[i];
            const end = points[i + 1];
            const mid = new THREE.Vector3().lerpVectors(start, end, 0.5);
            const dir = new THREE.Vector3().subVectors(end, start).normalize();

            const arrowGeo = new THREE.ConeGeometry(0.08, 0.2, 6);
            const arrowMat = new THREE.MeshStandardMaterial({
                color: color,
                emissive: color,
                emissiveIntensity: 0.5,
            });
            const arrow = new THREE.Mesh(arrowGeo, arrowMat);
            arrow.position.copy(mid);
            arrow.position.y = 0.4;

            // rotate arrow to point in direction
            const angle = Math.atan2(dir.x, dir.z);
            arrow.rotation.set(0, angle, -Math.PI / 2);

            arrow.name = `arrow_${pathId}_${i}`;
            this.group.add(arrow);
        }

        this.activePaths.push({ id: pathId, tube, glow });
    }

    clearPath(pathId) {
        // remove tube and glow
        const toRemove = [];
        this.group.children.forEach(child => {
            if (child.name === `path_${pathId}` || child.name === `pathGlow_${pathId}` ||
                child.name.startsWith(`pathNode_${pathId}_`) || child.name.startsWith(`arrow_${pathId}_`)) {
                toRemove.push(child);
            }
        });
        toRemove.forEach(obj => {
            this.group.remove(obj);
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });

        this.activePaths = this.activePaths.filter(p => p.id !== pathId);
        this.pathNodes = this.pathNodes.filter(n => !n.mesh.name.startsWith(`pathNode_${pathId}_`));
    }

    clearAll() {
        const toRemove = [...this.group.children];
        toRemove.forEach(obj => {
            this.group.remove(obj);
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
        this.activePaths = [];
        this.pathNodes = [];
    }

    update(elapsedTime) {
        // pulsing node animation
        this.pathNodes.forEach(({ mesh, phase }) => {
            const pulse = 0.8 + Math.sin(elapsedTime * 3 + phase) * 0.4;
            mesh.scale.setScalar(pulse);
            mesh.material.emissiveIntensity = 0.5 + Math.sin(elapsedTime * 2 + phase) * 0.3;
        });

        // glow pulsing
        this.activePaths.forEach(({ glow }) => {
            if (glow.material) {
                glow.material.opacity = 0.15 + Math.sin(elapsedTime * 1.5) * 0.08;
            }
        });
    }
}
