import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CityTerrain } from './terrain.js';
import { CityBuildings } from './buildings.js';
import { CityLighting } from './lights.js';
import { CameraController } from './camera.js';
import { VehicleSystem } from './vehicles.js';
import { PathVisualizer } from './path.js';
import { FloodSystem } from './flood.js';
import { UIController } from './ui.js';
import { HeatmapSystem } from './heatmap.js';

// ─── constants ───────────────────────────────────────────────────────────
const GRID_SIZE = 10;
const TILE_SIZE = 4;

// ─── scene setup ─────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0xb0c4de, 0.005);

const camera = new THREE.PerspectiveCamera(
    50,
    window.innerWidth / window.innerHeight,
    0.1,
    500
);
camera.position.set(30, 25, 30);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;
document.getElementById('canvas-container').appendChild(renderer.domElement);

// ─── orbit controls ──────────────────────────────────────────────────────
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI / 2.1;
controls.minDistance = 5;
controls.maxDistance = 80;
controls.target.set(0, 0, 0);

// ─── camera presets ──────────────────────────────────────────────────────
const cameraCtrl = new CameraController(camera, controls);

// ─── sky ─────────────────────────────────────────────────────────────────
function createSky() {
    const skyGeo = new THREE.SphereGeometry(200, 32, 32);
    const skyMat = new THREE.ShaderMaterial({
        side: THREE.BackSide,
        uniforms: {
            topColor:    { value: new THREE.Color(0x3a7bd5) },
            bottomColor: { value: new THREE.Color(0xfdf4e3) },
            offset:      { value: 20 },
            exponent:    { value: 0.5 }
        },
        vertexShader: `
            varying vec3 vWorldPosition;
            void main() {
                vec4 worldPos = modelMatrix * vec4(position, 1.0);
                vWorldPosition = worldPos.xyz;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform vec3 topColor;
            uniform vec3 bottomColor;
            uniform float offset;
            uniform float exponent;
            varying vec3 vWorldPosition;
            void main() {
                float h = normalize(vWorldPosition + offset).y;
                gl_FragColor = vec4(mix(bottomColor, topColor, max(pow(max(h, 0.0), exponent), 0.0)), 1.0);
            }
        `
    });
    return new THREE.Mesh(skyGeo, skyMat);
}
scene.add(createSky());

// ─── ground plane ────────────────────────────────────────────────────────
const groundGeo = new THREE.PlaneGeometry(80, 80);
const groundMat = new THREE.MeshStandardMaterial({
    color: 0x7ec87e,
    roughness: 0.9,
    metalness: 0.0
});
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.05;
ground.receiveShadow = true;
scene.add(ground);

// ─── grid helper (subtle) ────────────────────────────────────────────────
const gridSize = GRID_SIZE * TILE_SIZE;
const gridHelper = new THREE.GridHelper(gridSize, GRID_SIZE, 0x445566, 0x334455);
gridHelper.position.y = 0.01;
gridHelper.material.opacity = 0.3;
gridHelper.material.transparent = true;
scene.add(gridHelper);

// ─── build city terrain ──────────────────────────────────────────────────
const terrain = new CityTerrain(scene);
terrain.build();

// ─── build 3D buildings ──────────────────────────────────────────────────
const buildings = new CityBuildings(scene, terrain);
buildings.build();

// ─── lighting system ─────────────────────────────────────────────────────
const lighting = new CityLighting(scene);

// ─── vehicle system ──────────────────────────────────────────────────────
const vehicles = new VehicleSystem(scene, terrain);

// ─── path visualization ──────────────────────────────────────────────────
const pathViz = new PathVisualizer(scene, terrain);

// ─── flood effects ───────────────────────────────────────────────────────
const floods = new FloodSystem(scene, terrain);

// ─── UI controller ───────────────────────────────────────────────────────
const ui = new UIController();

// ─── risk heatmap ────────────────────────────────────────────────────────
const heatmap = new HeatmapSystem(scene, terrain);

// bind UI events
ui.on('camera', (view) => cameraCtrl.switchTo(view));
ui.on('togglePaths', (on) => { pathViz.group.visible = on; });
ui.on('toggleFloods', (on) => { floods.group.visible = on; });
ui.on('toggleVehicles', (on) => { vehicles.group.visible = on; });
ui.on('toggleRisk', (on) => { heatmap.group.visible = on; });

// demo: add some floods
setTimeout(() => {
    floods.addFlood(3, 5, 4, 5, 'flood1');
    floods.addFlood(7, 2, 7, 3, 'flood2');
}, 3000);

// demo: show paths for the ambulances
setTimeout(() => {
    vehicles.setPath(0, [[1,4],[1,5],[2,5],[3,5],[4,5]]);
    pathViz.showPath([[1,4],[1,5],[2,5],[3,5],[4,5]], 0x3cff8c, 'amb0');

    vehicles.setPath(1, [[6,4],[5,4],[4,4],[3,4],[2,4]]);
    pathViz.showPath([[6,4],[5,4],[4,4],[3,4],[2,4]], 0xff6b3c, 'amb1');
}, 2000);

// ─── remove loading screen ───────────────────────────────────────────────
window.addEventListener('load', () => {
    setTimeout(() => {
        document.getElementById('loading-screen').classList.add('hidden');
    }, 800);
});

// ─── animation loop ──────────────────────────────────────────────────────
const clock = new THREE.Clock();

function animate() {
    requestAnimationFrame(animate);
    const delta = clock.getDelta();
    const elapsed = clock.getElapsedTime();
    cameraCtrl.update(delta);
    controls.update();
    lighting.update(delta);
    vehicles.update(delta, elapsed);
    pathViz.update(elapsed);
    floods.update(delta);
    heatmap.update(elapsed);
    renderer.render(scene, camera);
}
animate();

// ─── window resize ───────────────────────────────────────────────────────
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

console.log('CityMind 3D initialized');
