// Persistent audio helper.
// Position/track/volume persistence lives in EnhancedAudioController
// (enhanced-audio-control.js: savePlayback / restoreFromSnapshot). This file
// only handles browsers that block autoplay on a fresh page: it shows a small
// "tap to resume" hint and resumes on the first user gesture. The hint is
// hidden as soon as any track is actually playing.

class PersistentAudioManager {
    constructor() {
        this.autoplayBlocked = false;
        this.armGestureResume();
    }

    controller() {
        return window.audioController || null;
    }

    anyShouldPlayButPaused() {
        const c = this.controller();
        if (!c) return false;
        return ['rain', 'crowd', 'music'].some(name => {
            const el = c.audioElements[name];
            return c.settings[name] && c.settings[name].enabled && el && el.paused;
        });
    }

    anyPlaying() {
        const c = this.controller();
        if (!c) return false;
        return ['rain', 'crowd', 'music'].some(name => {
            const el = c.audioElements[name];
            return el && !el.paused && !el.ended;
        });
    }

    onAutoplayBlocked() {
        this.autoplayBlocked = true;
        // Only nag if nothing is audible and something is supposed to be
        setTimeout(() => {
            if (this.anyShouldPlayButPaused() && !this.anyPlaying()) this.showAutoplayWarning();
        }, 300);
    }

    armGestureResume() {
        const resume = () => {
            const c = this.controller();
            if (!c || !this.anyShouldPlayButPaused()) return;
            c.restoreFromSnapshot();
        };
        ['pointerdown', 'keydown'].forEach(evt =>
            document.addEventListener(evt, resume, { once: true, capture: true }));
    }

    showAutoplayWarning() {
        if (document.getElementById('autoplay-warning')) return;
        const warning = document.createElement('button');
        warning.id = 'autoplay-warning';
        warning.type = 'button';
        warning.innerHTML = '<i class="fas fa-volume-mute" aria-hidden="true"></i><span>Tap to resume audio</span>';
        warning.style.cssText = `
            position: fixed; bottom: 80px; right: 20px;
            background: #5c3a1e; color: #fff; border: 1px solid #d4af37;
            padding: 12px 20px; border-radius: 8px; font-size: 14px;
            z-index: 10004; display: flex; align-items: center; gap: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3); cursor: pointer;
            animation: fadeIn 0.3s ease;`;
        warning.addEventListener('click', () => {
            const c = this.controller();
            if (c) c.restoreFromSnapshot();
            this.hideAutoplayWarning();
        });
        document.body.appendChild(warning);
    }

    hideAutoplayWarning() {
        this.autoplayBlocked = false;
        const warning = document.getElementById('autoplay-warning');
        if (warning) {
            warning.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => warning.remove(), 300);
        }
    }
}

// Add fade animations
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeOut {
        from { opacity: 1; transform: translateY(0); }
        to { opacity: 0; transform: translateY(10px); }
    }
`;
document.head.appendChild(style);

// Created synchronously so the controller can report autoplay blocks at once
window.persistentAudioManager = new PersistentAudioManager();
