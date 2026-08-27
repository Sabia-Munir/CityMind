// camera.js — camera presets and smooth transitions
import * as THREE from 'three';

const VIEWS = {
    aerial: {
        position: new THREE.Vector3(0, 40, 0),
        target: new THREE.Vector3(0, 0, 0),
        label: 'Aerial (1)'
    },
    perspective: {
        position: new THREE.Vector3(30, 25, 30),
        target: new THREE.Vector3(0, 0, 0),
        label: 'Perspective (2)'
    },
    streetNorth: {
        position: new THREE.Vector3(0, 2.5, -20),
        target: new THREE.Vector3(0, 1.5, 0),
        label: 'Street N (3)'
    },
    streetSouth: {
        position: new THREE.Vector3(0, 2.5, 20),
        target: new THREE.Vector3(0, 1.5, 0),
        label: 'Street S (4)'
    },
    streetEast: {
        position: new THREE.Vector3(20, 2.5, 0),
        target: new THREE.Vector3(0, 1.5, 0),
        label: 'Street E (5)'
    },
    streetWest: {
        position: new THREE.Vector3(-20, 2.5, 0),
        target: new THREE.Vector3(0, 1.5, 0),
        label: 'Street W (6)'
    },
    closeup: {
        position: new THREE.Vector3(5, 5, 5),
        target: new THREE.Vector3(0, 1, 0),
        label: 'Close-up (7)'
    },
};

export class CameraController {
    constructor(camera, controls) {
        this.camera = camera;
        this.controls = controls;
        this.currentView = 'perspective';
        this.transitioning = false;
        this.transitionProgress = 0;
        this.transitionDuration = 1.5; // seconds
        this.startPos = new THREE.Vector3();
        this.endPos = new THREE.Vector3();
        this.startTarget = new THREE.Vector3();
        this.endTarget = new THREE.Vector3();

        this._bindKeys();
    }

    _bindKeys() {
        window.addEventListener('keydown', (e) => {
            const key = e.key;
            switch (key) {
                case '1': this.switchTo('aerial'); break;
                case '2': this.switchTo('perspective'); break;
                case '3': this.switchTo('streetNorth'); break;
                case '4': this.switchTo('streetSouth'); break;
                case '5': this.switchTo('streetEast'); break;
                case '6': this.switchTo('streetWest'); break;
                case '7': this.switchTo('closeup'); break;
            }
        });
    }

    switchTo(viewName) {
        const view = VIEWS[viewName];
        if (!view) return;

        this.currentView = viewName;
        this.startPos.copy(this.camera.position);
        this.endPos.copy(view.position);
        this.startTarget.copy(this.controls.target);
        this.endTarget.copy(view.target);
        this.transitionProgress = 0;
        this.transitioning = true;
    }

    update(delta) {
        if (!this.transitioning) return;

        this.transitionProgress += delta / this.transitionDuration;
        if (this.transitionProgress >= 1) {
            this.transitionProgress = 1;
            this.transitioning = false;
        }

        // smooth easing (ease in-out)
        const t = this.transitionProgress;
        const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

        this.camera.position.lerpVectors(this.startPos, this.endPos, ease);
        this.controls.target.lerpVectors(this.startTarget, this.endTarget, ease);
    }

    getCurrentViewLabel() {
        return VIEWS[this.currentView]?.label || 'Custom';
    }

    getAllViewLabels() {
        return Object.entries(VIEWS).map(([key, v]) => ({
            key,
            label: v.label,
            active: key === this.currentView
        }));
    }
}
