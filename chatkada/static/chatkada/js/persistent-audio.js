// Persistent Audio Manager - Seamless playback across navigation
// Handles localStorage state, bfcache, back/forward buttons, and autoplay restrictions

class PersistentAudioManager {
    constructor() {
        this.stateKey = 'chayakada_persistent_audio_state';
        this.lastSaveTime = 0;
        this.saveThrottleMs = 1000; // Save at most once per second
        this.autoplayBlocked = false;
        
        this.init();
    }
    
    init() {
        // Restore state on initial load
        this.restoreCompleteState();
        
        // Handle bfcache (back/forward button)
        window.addEventListener('pageshow', (event) => {
            if (event.persisted) {
                // Page was restored from bfcache
                console.log('Page restored from bfcache - resuming audio');
                this.restoreCompleteState();
            }
        });
        
        // Save state before page unload
        window.addEventListener('beforeunload', () => {
            this.saveCompleteState(true); // Force immediate save
        });
        
        // Periodic state saving while audio is playing
        setInterval(() => {
            this.saveCompleteState();
        }, 2000); // Every 2 seconds
        
        // Handle autoplay restrictions - resume on first user interaction
        this.setupAutoplayFallback();
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
                // Settings for all audio types
                settings: controller.settings,
                realisticMode: controller.realisticMode,
                
                // Music-specific state
                currentSongIndex: controller.currentSongIndex,
                musicCurrentTime: controller.audioElements.music?.currentTime || 0,
                musicPaused: controller.audioElements.music?.paused ?? true,
                
                // Timestamps for validation
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
                console.log('No saved audio state found');
                return false;
            }
            
            const state = JSON.parse(savedState);
            
            // Validate state age (reject if older than 1 hour)
            const age = Date.now() - (state.timestamp || 0);
            if (age > 3600000) {
                console.log('Saved audio state too old, ignoring');
                localStorage.removeItem(this.stateKey);
                return false;
            }
            
            const controller = window.audioController;
            if (!controller) {
                console.warn('Audio controller not ready yet, will retry');
                // Retry after controller initializes
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
            controller.updateControls();
            
            // Restore audio playback states
            this.restoreAudioPlayback(controller, state);
            
            return true;
        } catch (e) {
            console.warn('Failed to restore audio state:', e);
            return false;
        }
    }
    
    restoreAudioPlayback(controller, state) {
        // Restore rain
        if (state.settings?.rain?.enabled) {
            controller.updateRain();
        }
        
        // Restore thunder
        if (state.settings?.thunder?.enabled) {
            controller.updateThunder();
        }
        
        // Restore crowd
        if (state.settings?.crowd?.enabled) {
            controller.updateCrowd();
        }
        
        // Restore music with playback position
        if (state.settings?.music?.enabled && !state.musicPaused) {
            const music = controller.audioElements.music;
            if (music) {
                const currentSong = controller.nostalgicSongs[controller.currentSongIndex % controller.nostalgicSongs.length];
                const musicPath = `/static/chatkada/sounds/${currentSong.file}`;
                
                music.src = musicPath;
                music.volume = (state.settings.music.volume || 25) / 100;
                music.currentTime = state.musicCurrentTime || 0;
                music.loop = false;
                
                // Try to play - may be blocked by browser autoplay policy
                const playPromise = music.play();
                if (playPromise !== undefined) {
                    playPromise.then(() => {
                        console.log('Audio resumed successfully');
                        this.autoplayBlocked = false;
                        this.hideAutoplayWarning();
                    }).catch((e) => {
                        console.log('Autoplay blocked - waiting for user interaction');
                        this.autoplayBlocked = true;
                        this.showAutoplayWarning();
                    });
                }
                
                // Update now playing display
                const currentSongElement = document.getElementById('current-song');
                if (currentSongElement && currentSong) {
                    currentSongElement.textContent = currentSong.name;
                }
            }
        }
        
        // Restore realistic mode effects
        if (controller.realisticMode) {
            setTimeout(() => {
                controller.enableRealisticMode();
            }, 100);
        }
    }
    
    setupAutoplayFallback() {
        // Single click anywhere resumes blocked audio
        const resumeAudio = () => {
            if (!this.autoplayBlocked) return;
            
            const controller = window.audioController;
            if (!controller) return;
            
            // Resume any audio that should be playing
            if (controller.settings.music?.enabled) {
                controller.audioElements.music?.play().then(() => {
                    this.autoplayBlocked = false;
                    this.hideAutoplayWarning();
                }).catch(e => console.log('Resume failed:', e));
            }
            if (controller.settings.rain?.enabled) {
                controller.audioElements.rain?.play().catch(e => {});
            }
            if (controller.settings.thunder?.enabled) {
                // Thunder will play on next timer event
            }
            if (controller.settings.crowd?.enabled) {
                controller.audioElements.crowd?.play().catch(e => {});
            }
        };
        
        document.addEventListener('click', resumeAudio, { once: true });
        document.addEventListener('keydown', resumeAudio, { once: true });
    }
    
    showAutoplayWarning() {
        // Show a subtle indicator that audio is paused due to browser restrictions
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
