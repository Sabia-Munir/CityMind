// lights.js — comprehensive lighting system with day/night cycle
import * as THREE from 'three';

export class CityLighting {
    constructor(scene) {
        this.scene = scene;
        this.lights = {};
        this.timeOfDay = 0.4; // locked to daytime — no night cycle
        this.daySpeed = 0;    // disabled
        this.buildingLights = [];
        this._createLights();
    }

    _createLights() {
        // hemisphere light — sky above, ground below
        this.lights.hemi = new THREE.HemisphereLight(0x87ceeb, 0x3a6b35, 0.5);
        this.scene.add(this.lights.hemi);

        // ambient fill
        this.lights.ambient = new THREE.AmbientLight(0x404050, 0.4);
        this.scene.add(this.lights.ambient);

        // main directional (sun)
        this.lights.sun = new THREE.DirectionalLight(0xfff4e0, 1.5);
        this.lights.sun.castShadow = true;
        this.lights.sun.shadow.mapSize.set(2048, 2048);
        this.lights.sun.shadow.camera.left = -40;
        this.lights.sun.shadow.camera.right = 40;
        this.lights.sun.shadow.camera.top = 40;
        this.lights.sun.shadow.camera.bottom = -40;
        this.lights.sun.shadow.camera.near = 1;
        this.lights.sun.shadow.camera.far = 100;
        this.lights.sun.shadow.bias = -0.001;
        this.lights.sun.shadow.normalBias = 0.02;
        this.scene.add(this.lights.sun);
        this.scene.add(this.lights.sun.target);

        // moonlight (dim, blue-ish)
        this.lights.moon = new THREE.DirectionalLight(0x6688cc, 0.0);
        this.lights.moon.castShadow = false;
        this.scene.add(this.lights.moon);

        // point lights for hospital
        this.lights.hospitalGlow = new THREE.PointLight(0xff4444, 0, 10);
        this.scene.add(this.lights.hospitalGlow);

        // point lights for ambulance depot
        this.lights.depotGlow = new THREE.PointLight(0x4488ff, 0, 8);
        this.scene.add(this.lights.depotGlow);

        // street lamps (point lights along main roads)
        this._createStreetLamps();
    }

    _createStreetLamps() {
        const positions = [
            { x: -18, z: 0 },  { x: -10, z: 0 },
            { x: -2, z: 0 },   { x: 6, z: 0 },
            { x: 14, z: 0 },   { x: 0, z: -18 },
            { x: 0, z: -10 },  { x: 0, z: 2 },
            { x: 0, z: 10 },   { x: 0, z: 18 },
        ];

        positions.forEach(pos => {
            const lampLight = new THREE.PointLight(0xffcc66, 0, 8);
            lampLight.position.set(pos.x, 3, pos.z);
            this.scene.add(lampLight);

            // lamp post visual
            const post = new THREE.Mesh(
                new THREE.CylinderGeometry(0.05, 0.07, 2.5, 6),
                new THREE.MeshStandardMaterial({ color: 0x555555, metalness: 0.5 })
            );
            post.position.set(pos.x, 1.25, pos.z);
            this.scene.add(post);

            // lamp head
            const head = new THREE.Mesh(
                new THREE.SphereGeometry(0.15, 8, 8),
                new THREE.MeshStandardMaterial({
                    color: 0xffee88,
                    emissive: 0xffcc44,
                    emissiveIntensity: 0.5
                })
            );
            head.position.set(pos.x, 2.6, pos.z);
            this.scene.add(head);

            this.buildingLights.push({ light: lampLight, baseIntensity: 1.5, type: 'street' });
        });
    }

    addBuildingLight(position, color, intensity) {
        const light = new THREE.PointLight(color, 0, 6);
        light.position.copy(position);
        light.position.y += 2;
        this.scene.add(light);
        this.buildingLights.push({ light, baseIntensity: intensity, type: 'building' });
    }

    update(delta) {
        this.timeOfDay += this.daySpeed * delta;
        if (this.timeOfDay > 1) this.timeOfDay -= 1;

        // sun position (arc across sky)
        const sunAngle = (this.timeOfDay - 0.25) * Math.PI * 2;
        const sunHeight = Math.sin(sunAngle);
        const sunX = Math.cos(sunAngle) * 35;
        const sunY = sunHeight * 35;

        this.lights.sun.position.set(sunX, Math.max(sunY, -5), 20);
        this.lights.sun.target.position.set(0, 0, 0);

        // day/night intensity
        const dayFactor = Math.max(0, sunHeight);
        const nightFactor = Math.max(0, -sunHeight);

        // sun color shifts during golden hour
        const goldenHour = Math.max(0, 1 - Math.abs(this.timeOfDay - 0.78) * 10);
        const sunColor = new THREE.Color().setHSL(
            0.1 - goldenHour * 0.05,
            0.8 + goldenHour * 0.2,
            0.7 + dayFactor * 0.3
        );
        this.lights.sun.color.copy(sunColor);
        this.lights.sun.intensity = dayFactor * 2.0;

        // moon
        const moonAngle = sunAngle + Math.PI;
        this.lights.moon.position.set(
            Math.cos(moonAngle) * 30,
            Math.max(Math.sin(moonAngle) * 30, -5),
            -20
        );
        this.lights.moon.intensity = nightFactor * 0.3;

        // hemisphere light
        const skyColor = new THREE.Color().lerpColors(
            new THREE.Color(0x0a0a2a), // night sky
            new THREE.Color(0x87ceeb), // day sky
            dayFactor
        );
        const groundColor = new THREE.Color().lerpColors(
            new THREE.Color(0x0a0a0a),
            new THREE.Color(0x3a6b35),
            dayFactor
        );
        this.lights.hemi.color.copy(skyColor);
        this.lights.hemi.groundColor.copy(groundColor);
        this.lights.hemi.intensity = 0.3 + dayFactor * 0.4;

        // ambient
        this.lights.ambient.intensity = 0.15 + dayFactor * 0.35;

        // hospital and depot glow
        this.lights.hospitalGlow.intensity = nightFactor * 3;
        this.lights.depotGlow.intensity = nightFactor * 2;

        // street lamps and building lights turn on at night
        this.buildingLights.forEach(bl => {
            if (bl.type === 'street') {
                bl.light.intensity = nightFactor * bl.baseIntensity;
            } else {
                bl.light.intensity = nightFactor * bl.baseIntensity;
            }
        });
    }
}
