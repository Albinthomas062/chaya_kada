// Persistent Audio Manager - Seamless playback across navigation
// Handles localStorage state, bfcache, back/forward buttons, currentTime resume

class PersistentAudioManager {
    constructor() {
        this.stateKey = 'chayakada_persistent_audio_state';
        this.lastSaveTime = 0;
        this.saveThrottleMs = 500; // Save at most twice per second
        this.autoplayBlocked = false;
        this.timeupdateListeners = new Map();
        
        this.init();
    }
    
    init() {
        // Restore state on initial load
        this.restoreCompleteState();
        
        // Handle bfcache (back/forward button)
        window.addEventListener('pageshow', (event) => {
            if (event.persisted) {
                console.log('Page restored from bfcache - resuming audio');
                this.restoreCompleteState();
            }
        });
        
        // Save state before page unload and on pagehide (for bfcache)
        window.addEventListener('beforeunload', () => {
            this.saveCompleteState(true);
        });
        
        window.addEventListener('pagehide', () => {
            this.saveCompleteState(true);
        });
        
        // Handle autoplay restrictions
        this.setupAutoplayFallback();
        
        // Set up timeupdate listeners once controller is ready
        this.setupTimeupdateListeners();
    }
    
    setupTimeupdateListeners() {
        // Wait for audio controller to be ready
        const checkController = () => {
            const controller = window.audioController;
            if (!controller || !controller.audioElements) {
                setTimeout(checkController, 500);
                return;
            }
            
            // Add timeupdate listeners to all audio elements
            const elements = controller.audioElements;
            
            if (elements.rain) {
                this.addTimeupdateListener('rain', elements.rain);
            }
            if (elements.thunder) {
                this.addTimeupdateListener('thunder', elements.thunder);
            }
            if (elements.crowd) {
                this.addTimeupdateListener('crowd', elements.crowd);
            }
            if (elements.music) {
                this.addTimeupdateListener('music', elements.music);
            }
        };
        
        checkController();
    }
    
    addTimeupdateListener(name, audioElement) {
        const listener = () => {
            this.saveCompleteState();
        };
        
        audioElement.addEventListener('timeupdate', listener);
        this.timeupdateListeners.set(name, listener);
    }
    
    saveCompleteState(force = false) {
        // Throttle saves unless forced
        const now = Date.now();
        if (!force && (now - this.lastSaveTime) < this.saveThrottleMs) {
            return;
        }
        this.lastSaveTime = now;
        
        try {
            const controller = window.audioController;
            if (!controller) return;
            
            const state = {
                settings: controller.settings,
                realisticMode: controller.realisticMode,
                currentSongIndex: controller.currentSongIndex,
                
                // Save currentTime for all tracks
                tracks: {
                    rain: {
                        currentTime: controller.audioElements.rain?.currentTime || 0,
                        paused: controller.audioElements.rain?.paused ?? true,
                        duration: controller.audioElements.rain?.duration || 0
                    },
                    thunder: {
                        currentTime: controller.audioElements.thunder?.currentTime || 0,
                        paused: controller.audioElements.thunder?.paused ?? true
                    },
                    crowd: {
                        currentTime: controller.audioElements.crowd?.currentTime || 0,
                        paused: controller.audioElements.crowd?.paused ?? true,
                        duration: controller.audioElements.crowd?.duration || 0
                    },
                    music: {
                        currentTime: controller.audioElements.music?.currentTime || 0,
                        paused: controller.audioElements.music?.paused ?? true,
                        duration: controller.audioElements.music?.duration || 0
                    }
                },
                
                timestamp: now,
                url: window.location.pathname
            };
            
            localStorage.setItem(this.stateKey, JSON.stringify(state));
        } catch (e) {
            console.warn('Failed to save audio state:', e);
        }
    }
    
    restoreCompleteState() {
        try {
            const savedState = localStorage.getItem(this.stateKey);
            if (!savedState) {
                return false;
            }
            
            const state = JSON.parse(savedState);
            
            // Validate state age (reject if older than 1 hour)
            const age = Date.now() - (state.timestamp || 0);
            if (age > 3600000) {
                localStorage.removeItem(this.stateKey);
                return false;
            }
            
            const controller = window.audioController;
            if (!controller || !controller.audioElements) {
                setTimeout(() => this.restoreCompleteState(), 500);
                return false;
            }
            
            console.log('Restoring audio state from:', state.url);
            
            // Restore settings
            if (state.settings) {
                controller.settings = { ...controller.settings, ...state.settings };
            }
            if (state.realisticMode !== undefined) {
                controller.realisticMode = state.realisticMode;
            }
            if (state.currentSongIndex !== undefined) {
                controller.currentSongIndex = state.currentSongIndex;
            }
            
            // Update UI controls first
            if (controller.updateControls) {
                controller.updateControls();
            }
            
            // Restore audio playback with currentTime
            this.restoreAudioPlayback(controller, state);
            
            return true;
        } catch (e) {
            console.warn('Failed to restore audio state:', e);
            return false;
        }
    }
    
    restoreAudioPlayback(controller, state) {
        const tracks = state.tracks || {};
        
        // Restore rain
        if (state.settings?.rain?.enabled && tracks.rain) {
            const rain = controller.audioElements.rain;
            if (rain) {
                this.restoreTrack(rain, tracks.rain, () => {
                    if (controller.updateRain) controller.updateRain();
                });
            }
        }
        
        // Restore crowd
        if (state.settings?.crowd?.enabled && tracks.crowd) {
            const crowd = controller.audioElements.crowd;
            if (crowd) {
                this.restoreTrack(crowd, tracks.crowd, () => {
                    if (controller.updateCrowd) controller.updateCrowd();
                });
            }
        }
        
        // Restore music
        if (state.settings?.music?.enabled && tracks.music && !tracks.music.paused) {
            const music = controller.audioElements.music;
            if (music) {
                const currentSong = controller.nostalgicSongs?.[controller.currentSongIndex % controller.nostalgicSongs.length];
                if (currentSong) {
                    const musicPath = `/static/chatkada/sounds/${currentSong.file}`;
                    music.src = musicPath;
                    music.volume = (state.settings.music.volume || 25) / 100;
                    music.loop = false;
                    
                    this.restoreTrack(music, tracks.music);
                    
                    // Update now playing display
                    const currentSongElement = document.getElementById('current-song');
                    if (currentSongElement) {
                        currentSongElement.textContent = currentSong.name;
                    }
                }
            }
        }
        
        // Restore realistic mode effects
        if (controller.realisticMode && controller.enableRealisticMode) {
            setTimeout(() => controller.enableRealisticMode(), 100);
        }
    }
    
    restoreTrack(audioElement, trackState, onReady) {
        if (!audioElement || !trackState) return;
        
        const resumePlayback = () => {
            // Set currentTime after metadata is loaded
            if (trackState.currentTime > 0 && isFinite(trackState.currentTime)) {
                audioElement.currentTime = Math.min(trackState.currentTime, audioElement.duration || trackState.duration);
            }
            
            // Play if it wasn't paused
            if (!trackState.paused) {
                const playPromise = audioElement.play();
                if (playPromise !== undefined) {
                    playPromise.then(() => {
                        console.log('Audio track resumed successfully');
                        this.autoplayBlocked = false;
                        this.hideAutoplayWarning();
                    }).catch((e) => {
                        console.log('Autoplay blocked:', e.message);
                        this.autoplayBlocked = true;
                        this.showAutoplayWarning();
                    });
                }
            }
            
            if (onReady) onReady();
        };
        
        // Wait for loadedmetadata before setting currentTime
        if (audioElement.readyState >= 1) {
            // Metadata already loaded
            resumePlayback();
        } else {
            audioElement.addEventListener('loadedmetadata', resumePlayback, { once: true });
        }
    }
    
    setupAutoplayFallback() {
        const resumeAudio = () => {
            if (!this.autoplayBlocked) return;
            
            const controller = window.audioController;
            if (!controller) return;
            
            // Resume any audio that should be playing
            const elements = controller.audioElements;
            if (elements.music && controller.settings.music?.enabled) {
                elements.music.play().catch(e => {});
            }
            if (elements.rain && controller.settings.rain?.enabled) {
                elements.rain.play().catch(e => {});
            }
            if (elements.crowd && controller.settings.crowd?.enabled) {
                elements.crowd.play().catch(e => {});
            }
            
            this.autoplayBlocked = false;
            this.hideAutoplayWarning();
        };
        
        document.addEventListener('click', resumeAudio, { once: true });
        document.addEventListener('keydown', resumeAudio, { once: true });
    }
    
    showAutoplayWarning() {
        let warning = document.getElementById('autoplay-warning');
        if (!warning) {
            warning = document.createElement('div');
            warning.id = 'autoplay-warning';
            warning.innerHTML = `
                <i class="fas fa-volume-mute"></i>
                <span>Click anywhere to resume audio</span>
            `;
            warning.style.cssText = `
                position: fixed;
                bottom: 80px;
                right: 20px;
                background: rgba(199, 141, 80, 0.95);
                color: white;
                padding: 12px 20px;
                border-radius: 8px;
                font-size: 14px;
                z-index: 10000;
                display: flex;
                align-items: center;
                gap: 10px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                cursor: pointer;
                animation: fadeIn 0.3s ease;
            `;
            document.body.appendChild(warning);
            
            warning.addEventListener('click', () => {
                this.setupAutoplayFallback();
                warning.style.animation = 'fadeOut 0.3s ease';
                setTimeout(() => warning.remove(), 300);
            });
        }
    }
    
    hideAutoplayWarning() {
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

// Initialize persistent audio manager after DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.persistentAudioManager = new PersistentAudioManager();
    });
} else {
    window.persistentAudioManager = new PersistentAudioManager();
}
