// vehicles.js — 3 ambulances on road surfaces, smooth movement
import * as THREE from 'three';
const TILE_SIZE = 4;

const START_POSITIONS = [
    [1, 5],
    [5, 4],
    [8, 8],
];
const AMB_NAMES = ['ALPHA', 'BRAVO', 'CHARLIE'];
const AMB_COLORS_HEX = [0x3cff8c, 0xff6b3c, 0x44aaff];

export class VehicleSystem {
    constructor(scene, terrain) {
        this.scene = scene;
        this.terrain = terrain;
        this.group = new THREE.Group();
        this.group.name = 'vehicles';
        this.scene.add(this.group);
        this.ambulances = [];
        this.speed = 6.0;
        this._createAll();
    }

    _createAll() {
        START_POSITIONS.forEach((pos, i) => {
            const mesh = this._buildAmbulance();
            const wp = this.terrain.gridToWorld(pos[0], pos[1]);
            mesh.position.set(wp.x, 0.5, wp.z);
            this.group.add(mesh);

            const nameSprite = this._makeNameSprite(AMB_NAMES[i], AMB_COLORS_HEX[i]);
            nameSprite.position.set(wp.x, 2.2, wp.z);
            this.group.add(nameSprite);

            const groundRing = this._makeGroundRing(AMB_COLORS_HEX[i]);
            groundRing.position.set(wp.x, 0.05, wp.z);
            this.group.add(groundRing);

            this.ambulances.push({
                mesh,
                nameSprite,
                groundRing,
                gridPos: [...pos],
                worldPos: wp.clone(),
                targetWorldPos: wp.clone(),
                path: [],
                pathIndex: 0,
                moving: false,
                lightPhase: Math.random() * 6.28,
            });
        });
    }

    _makeNameSprite(text, color) {
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 80;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = 'rgba(0,0,0,0.75)';
        ctx.beginPath();
        ctx.roundRect(4, 4, 248, 72, 10);
        ctx.fill();
        ctx.font = 'bold 40px monospace';
        ctx.fillStyle = '#' + color.toString(16).padStart(6, '0');
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, 128, 40);
        const tex = new THREE.CanvasTexture(canvas);
        const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
        const sprite = new THREE.Sprite(mat);
        sprite.scale.set(2.5, 0.8, 1);
        return sprite;
    }

    _makeGroundRing(color) {
        const g = new THREE.Group();
        const ring = new THREE.Mesh(
            new THREE.RingGeometry(1.0, 1.2, 32),
            new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5, side: THREE.DoubleSide })
        );
        ring.rotation.x = -Math.PI / 2;
        g.add(ring);
        const disc = new THREE.Mesh(
            new THREE.CircleGeometry(0.7, 16),
            new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.2, side: THREE.DoubleSide })
        );
        disc.rotation.x = -Math.PI / 2;
        g.add(disc);
        return g;
    }

    _buildAmbulance() {
        const g = new THREE.Group();
        const s = 1.6;

        g.add(this._box(0.9 * s, 0.45 * s, 1.6 * s, 0xffffff, [0, 0.35 * s, 0]));
        g.add(this._box(0.8 * s, 0.35 * s, 0.5 * s, 0xeeeeee, [0, 0.52 * s, -0.5 * s]));

        const ws = this._box(0.7 * s, 0.25 * s, 0.05, 0x88ccff, [0, 0.58 * s, -0.76 * s]);
        ws.material.transparent = true;
        ws.material.opacity = 0.7;
        g.add(ws);

        [0.48, -0.48].forEach(x => {
            g.add(this._box(0.03, 0.25 * s, 0.35 * s, 0xff0000, [x * s, 0.4 * s, 0.1]));
            g.add(this._box(0.03, 0.4 * s, 0.2 * s, 0xff0000, [x * s, 0.4 * s, 0.1]));
        });

        g.add(this._box(0.3 * s, 0.04, 0.03, 0xff0000, [0, 0.4 * s, -0.81 * s]));
        g.add(this._box(0.04, 0.3 * s, 0.03, 0xff0000, [0, 0.4 * s, -0.81 * s]));

        g.add(this._box(0.6 * s, 0.1, 0.2, 0x333333, [0, 0.68 * s, 0.1]));

        const lr = new THREE.Mesh(new THREE.SphereGeometry(0.1 * s, 8, 8),
            new THREE.MeshStandardMaterial({ color: 0xff0000, emissive: 0xff0000, emissiveIntensity: 1 }));
        lr.position.set(-0.2 * s, 0.78 * s, 0.1);
        lr.name = 'lightRed';
        g.add(lr);

        const lb = new THREE.Mesh(new THREE.SphereGeometry(0.1 * s, 8, 8),
            new THREE.MeshStandardMaterial({ color: 0x0066ff, emissive: 0x0066ff, emissiveIntensity: 1 }));
        lb.position.set(0.2 * s, 0.78 * s, 0.1);
        lb.name = 'lightBlue';
        g.add(lb);

        const wm = new THREE.MeshStandardMaterial({ color: 0x111111 });
        const wg = new THREE.CylinderGeometry(0.12 * s, 0.12 * s, 0.1 * s, 8);
        [[-0.45, -0.45], [0.45, -0.45], [-0.45, 0.45], [0.45, 0.45]].forEach(([x, z]) => {
            const w = new THREE.Mesh(wg, wm);
            w.position.set(x * s, 0.12 * s, z * s);
            w.rotation.z = Math.PI / 2;
            g.add(w);
        });

        const pl = new THREE.PointLight(0xff4444, 3, 8);
        pl.position.set(0, 1.5, 0);
        pl.name = 'emergencyLight';
        g.add(pl);

        return g;
    }

    _box(w, h, d, color, pos) {
        const m = new THREE.Mesh(
            new THREE.BoxGeometry(w, h, d),
            new THREE.MeshStandardMaterial({ color, roughness: 0.4 })
        );
        m.position.set(...pos);
        m.castShadow = true;
        m.receiveShadow = true;
        return m;
    }

    setPath(ambIdx, gridPath) {
        if (ambIdx >= this.ambulances.length) return;
        const amb = this.ambulances[ambIdx];
        amb.path = gridPath.map(([r, c]) => this.terrain.gridToWorld(r, c));
        amb.pathIndex = 0;
        amb.moving = amb.path.length > 0;
        if (amb.path.length > 0) amb.targetWorldPos.copy(amb.path[0]);
    }

    teleportTo(idx, row, col) {
        if (idx >= this.ambulances.length) return;
        const amb = this.ambulances[idx];
        const wp = this.terrain.gridToWorld(row, col);
        amb.mesh.position.set(wp.x, 0.5, wp.z);
        amb.nameSprite.position.set(wp.x, 2.2, wp.z);
        amb.groundRing.position.set(wp.x, 0.05, wp.z);
        amb.gridPos = [row, col];
        amb.worldPos.copy(wp);
        amb.targetWorldPos.copy(wp);
        amb.moving = false;
        amb.path = [];
        amb.pathIndex = 0;
    }

    update(delta) {
        this.ambulances.forEach(amb => {
            amb.lightPhase += delta * 8;
            const flash = Math.sin(amb.lightPhase) > 0;
            const red = amb.mesh.getObjectByName('lightRed');
            const blue = amb.mesh.getObjectByName('lightBlue');
            const pt = amb.mesh.getObjectByName('emergencyLight');
            if (red) red.material.emissiveIntensity = flash ? 1.0 : 0.1;
            if (blue) blue.material.emissiveIntensity = flash ? 0.1 : 1.0;
            if (pt) {
                pt.intensity = flash ? 5 : 1;
                pt.color.setHex(flash ? 0xff0000 : 0x0066ff);
            }

            if (!amb.moving || amb.path.length === 0) return;
            const pos = amb.mesh.position;
            const tgt = amb.targetWorldPos;
            const dist = pos.distanceTo(tgt);

            if (dist < 0.2) {
                amb.pathIndex++;
                if (amb.pathIndex >= amb.path.length) {
                    amb.moving = false;
                    amb.pathIndex = 0;
                } else {
                    amb.targetWorldPos.copy(amb.path[amb.pathIndex]);
                }
            } else {
                const dir = new THREE.Vector3().subVectors(tgt, pos).normalize();
                pos.addScaledVector(dir, Math.min(this.speed * delta, dist));
                pos.y = 0.5;
                amb.mesh.rotation.y = Math.atan2(dir.x, dir.z);

                amb.nameSprite.position.x = pos.x;
                amb.nameSprite.position.z = pos.z;
                amb.nameSprite.position.y = 2.2;

                amb.groundRing.position.x = pos.x;
                amb.groundRing.position.z = pos.z;
            }
        });
    }
}
