// Enhanced Audio Control System with Proper Toggle Control and Lightning
class EnhancedAudioController {
    constructor() {
        this.audioElements = {
            rain: document.getElementById('rain-audio'),
            thunder: document.getElementById('thunder-audio'),
            crowd: document.getElementById('crowd-audio'),
            music: document.getElementById('music-audio')
        };

        this.settings = {
            rain: { enabled: false, volume: 30, intensity: 'medium' },
            thunder: { enabled: false, volume: 25, frequency: 'occasional' },
            lightning: { intensity: 'medium', type: 'single' },
            crowd: { enabled: false, volume: 15 },
            music: { enabled: false, volume: 25 }
        };

        this.thunderTimer = null;
        this.lightningTimer = null;
        this.realisticTimer = null;
        this.currentSongIndex = 0;
        this.realisticMode = false;
        this.lightningInProgress = false;

        // Web Audio API setup for realistic mode
        this.audioContext = null;
        this.gainNodes = {};
        this.filterNodes = {};
        this.sourceNodes = {};

        this.thunderSounds = [
            'thunder-1.m4a',
            'thunder-2.m4a',
            'earthquake.mp3'
        ];

        // Updated with your Malayalam songs
        this.nostalgicSongs = [
            { name: 'Alliyambal', file: 'Alliyambal.mp3' },
            { name: 'Ente Ellam', file: 'Ente Ellam.mp3' },
            { name: 'Kinnaragaanam', file: 'Kinnaragaanam.mp3' },
            { name: 'Moonlight', file: 'Moonlight.mp3' },
            { name: 'Nee En Sarga', file: 'NeeEnSarga.mp3' },
            { name: 'O Priye', file: 'O Priye.mp3' },
            { name: 'Oru Pushpam', file: 'Oru Pushpam.mp3' },
            { name: 'Oruvenal Puzhayil', file: 'Oruvenal Puzhayil.mp3' },
            { name: 'Pavizhamalli', file: 'Pavizhamalli.mp3' },
            { name: 'Pookkalam', file: 'Pookkalam.mp3' },
            { name: 'Santhamee Rathri', file: 'Santhamee Rathri.mp3' }
        ];

        this.rainSounds = {
            light: 'rain-light.mp3',
            medium: 'Rain.mp3',
            heavy: 'Rain.mp3',
            storm: 'Rain.mp3'
        };

        // Single crowd sound file
        this.crowdSound = 'Cafe.mp3';

        this.init();
    }

    async init() {
        await this.initWebAudio();
        this.loadSettings();
        this.setupEventListeners();
        this.updateAudioElements();

        // Try to restore previous music state first
        const restored = this.restoreMusicState();

        // Only randomize if we didn't restore a previous state
        if (!restored) {
            this.randomizeInitialSong();
        }

        this.createLightningElements(); // Create lightning elements on init

        // Periodically save music state while playing
        setInterval(() => {
            if (this.settings.music.enabled && this.audioElements.music && !this.audioElements.music.paused) {
                this.saveMusicState();
            }
        }, 5000); // Save every 5 seconds while playing
    }

    async initWebAudio() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // Create nodes for each audio element
            Object.keys(this.audioElements).forEach(key => {
                const audio = this.audioElements[key];
                if (audio) {
                    try {
                        this.sourceNodes[key] = this.audioContext.createMediaElementSource(audio);
                        this.gainNodes[key] = this.audioContext.createGain();
                        this.filterNodes[key] = this.audioContext.createBiquadFilter();

                        // Configure filter
                        this.filterNodes[key].type = 'lowpass';
                        this.filterNodes[key].frequency.setValueAtTime(22050, this.audioContext.currentTime);

                        // Connect nodes: source -> filter -> gain -> destination
                        this.sourceNodes[key].connect(this.filterNodes[key]);
                        this.filterNodes[key].connect(this.gainNodes[key]);
                        this.gainNodes[key].connect(this.audioContext.destination);
                    } catch (e) {
                        console.log(`Web Audio setup failed for ${key}:`, e);
                    }
                }
            });
        } catch (error) {
            console.log('Web Audio API not supported, falling back to standard audio');
        }
    }

    createLightningElements() {
        // Create screen flash element if it doesn't exist
        if (!document.getElementById('screen-flash')) {
            const screenFlash = document.createElement('div');
            screenFlash.id = 'screen-flash';
            screenFlash.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(255, 255, 255, 0.8);
                pointer-events: none;
                z-index: 9999;
                display: none;
                opacity: 0;
                transition: opacity 0.1s ease;
            `;
            document.body.appendChild(screenFlash);
        }

        // Create lightning container if it doesn't exist
        if (!document.getElementById('lightning-container')) {
            const lightningContainer = document.createElement('div');
            lightningContainer.id = 'lightning-container';
            lightningContainer.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                z-index: 9998;
            `;
            document.body.appendChild(lightningContainer);

            // Add lightning elements
            lightningContainer.innerHTML = `
                <div id="lightning-flash" class="lightning-flash"></div>
                <div id="lightning-bolt" class="lightning-bolt"></div>
                <div id="lightning-branches" class="lightning-branches"></div>
            `;
        }
    }

    setupEventListeners() {
        // Panel toggle
        document.getElementById('audio-control-btn')?.addEventListener('click', () => {
            document.getElementById('audio-control-panel').classList.toggle('active');
        });

        document.getElementById('close-audio-panel')?.addEventListener('click', () => {
            document.getElementById('audio-control-panel').classList.remove('active');
        });

        // Master controls
        document.getElementById('realistic-mode-btn')?.addEventListener('click', () => {
            this.toggleRealisticMode();
        });

        document.getElementById('mute-all-btn')?.addEventListener('click', () => {
            this.muteAll();
        });

        // Rain controls
        document.getElementById('rain-toggle')?.addEventListener('change', (e) => {
            this.settings.rain.enabled = e.target.checked;
            this.updateRain();
        });

        document.getElementById('rain-volume')?.addEventListener('input', (e) => {
            this.settings.rain.volume = e.target.value;
            document.getElementById('rain-volume-display').textContent = e.target.value + '%';
            this.updateRain();
        });

        document.getElementById('rain-intensity')?.addEventListener('change', (e) => {
            this.settings.rain.intensity = e.target.value;
            this.updateRain();
        });

        // Thunder controls
        document.getElementById('thunder-toggle')?.addEventListener('change', (e) => {
            this.settings.thunder.enabled = e.target.checked;
            this.updateThunder();
        });

        document.getElementById('thunder-volume')?.addEventListener('input', (e) => {
            this.settings.thunder.volume = e.target.value;
            document.getElementById('thunder-volume-display').textContent = e.target.value + '%';
            this.updateThunder();
        });

        document.getElementById('thunder-frequency')?.addEventListener('change', (e) => {
            this.settings.thunder.frequency = e.target.value;
            this.updateThunder();
        });

        document.getElementById('lightning-intensity')?.addEventListener('change', (e) => {
            this.settings.lightning.intensity = e.target.value;
            this.saveSettings();
        });

        document.getElementById('lightning-type')?.addEventListener('change', (e) => {
            this.settings.lightning.type = e.target.value;
            this.saveSettings();
        });

        document.getElementById('thunder-test-btn')?.addEventListener('click', () => {
            this.testThunder();
        });

        // Crowd controls
        document.getElementById('crowd-toggle')?.addEventListener('change', (e) => {
            this.settings.crowd.enabled = e.target.checked;
            this.updateCrowd();
        });

        document.getElementById('crowd-volume')?.addEventListener('input', (e) => {
            this.settings.crowd.volume = e.target.value;
            document.getElementById('crowd-volume-display').textContent = e.target.value + '%';
            this.updateCrowd();
        });

        // Music controls
        document.getElementById('music-toggle')?.addEventListener('change', (e) => {
            this.settings.music.enabled = e.target.checked;
            this.updateMusic();
        });

        document.getElementById('music-volume')?.addEventListener('input', (e) => {
            this.settings.music.volume = e.target.value;
            document.getElementById('music-volume-display').textContent = e.target.value + '%';
            this.updateMusic();
        });


        // Music ended event
        this.audioElements.music?.addEventListener('ended', () => {
            this.nextSong();
        });

        // User interaction to start audio context
        document.addEventListener('click', () => {
            if (this.audioContext && this.audioContext.state === 'suspended') {
                this.audioContext.resume();
            }
        }, { once: true });
    }

    updateRain() {
        const rain = this.audioElements.rain;
        const rainContainer = document.getElementById('rain-container');

        if (!rain) return;

        if (this.settings.rain.enabled) {
            const rainFile = this.rainSounds[this.settings.rain.intensity];
            const rainPath = `/static/chatkada/sounds/${rainFile}`;

            if (rain.src !== rainPath) {
                rain.src = rainPath;
            }

            rain.volume = this.settings.rain.volume / 100;
            rain.loop = true;

            rain.play().catch(e => {
                console.log('Rain audio play failed:', e);
                console.log('Trying to play:', rainPath);
            });

            if (rainContainer) {
                rainContainer.style.display = 'block';
                this.updateRainEffect();
            }
        } else {
            rain.pause();
            rain.currentTime = 0; // Reset to beginning
            if (rainContainer) {
                rainContainer.style.display = 'none';
            }
        }

        this.saveSettings();
    }

    updateThunder() {
        // CRITICAL: Stop all thunder timers first
        this.stopAllThunderTimers();

        if (this.settings.thunder.enabled) {
            this.audioElements.thunder.volume = this.settings.thunder.volume / 100;
            this.startLightningTimer();
        }

        this.saveSettings();
    }

    updateCrowd() {
        const crowd = this.audioElements.crowd;

        if (!crowd) return;

        if (this.settings.crowd.enabled) {
            const crowdPath = `/static/chatkada/sounds/${this.crowdSound}`;

            if (crowd.src !== crowdPath) {
                crowd.src = crowdPath;
            }

            crowd.volume = this.settings.crowd.volume / 100;
            crowd.loop = true;

            crowd.play().catch(e => {
                console.log('Crowd audio play failed:', e);
                console.log('Trying to play:', crowdPath);
            });
        } else {
            crowd.pause();
            crowd.currentTime = 0; // Reset to beginning
        }

        this.saveSettings();
    }

    updateMusic() {
        const music = this.audioElements.music;

        if (!music) return;

        if (this.settings.music.enabled) {
            music.volume = this.settings.music.volume / 100;
            this.playCurrentSong();
            this.saveMusicState(); // Save state when enabling music
        } else {
            music.pause();
            music.currentTime = 0; // Reset to beginning
            const currentSongElement = document.getElementById('current-song');
            if (currentSongElement) {
                currentSongElement.textContent = 'No song playing';
            }
            // Clear saved state when disabling
            localStorage.removeItem('chayakada_music_state');
        }

        this.saveSettings();
    }

    randomizeInitialSong() {
        this.currentSongIndex = Math.floor(Math.random() * this.nostalgicSongs.length);
    }

    playCurrentSong() {
        if (this.nostalgicSongs.length === 0) return;

        const currentSong = this.nostalgicSongs[this.currentSongIndex % this.nostalgicSongs.length];
        const music = this.audioElements.music;

        const musicPath = `/static/chatkada/sounds/${currentSong.file}`;
        music.src = musicPath;
        music.loop = false;

        music.play().then(() => {
            // Save state after successfully starting playback
            this.saveMusicState();
        }).catch(e => {
            console.log('Music play failed:', e);
            console.log('Trying to play:', musicPath);
        });

        const currentSongElement = document.getElementById('current-song');
        if (currentSongElement) {
            const currentSong = this.nostalgicSongs[this.currentSongIndex % this.nostalgicSongs.length];
            currentSongElement.textContent = currentSong.name;
        }

        const musicState = {
            currentSongIndex: this.currentSongIndex,
            currentTime: this.audioElements.music?.currentTime || 0,
            enabled: this.settings.music.enabled,
            volume: this.settings.music.volume,
            timestamp: Date.now()
        };
        localStorage.setItem('chayakada_music_state', JSON.stringify(musicState));
    } catch(e) {
        console.log('Failed to save music state:', e);
    }
}

// Restore music playback state from localStorage
restoreMusicState() {
    try {
        const savedState = localStorage.getItem('chayakada_music_state');
        if (!savedState) return false;

        const musicState = JSON.parse(savedState);

        // Check if state is recent (within last 10 minutes)
        const timeDiff = Date.now() - (musicState.timestamp || 0);
        if (timeDiff > 600000) { // 10 minutes
            localStorage.removeItem('chayakada_music_state');
            return false;
        }

        // Restore state
        this.currentSongIndex = musicState.currentSongIndex || 0;
        this.settings.music.enabled = musicState.enabled || false;
        this.settings.music.volume = musicState.volume || 25;

        // Update UI
        const musicToggle = document.getElementById('music-toggle');
        if (musicToggle) {
            musicToggle.checked = this.settings.music.enabled;
        }

        const musicVolume = document.getElementById('music-volume');
        if (musicVolume) {
            musicVolume.value = this.settings.music.volume;
            document.getElementById('music-volume-display').textContent = this.settings.music.volume + '%';
        }

        // Restore playback if music was enabled
        if (this.settings.music.enabled) {
            const music = this.audioElements.music;
            if (music) {
                const currentSong = this.nostalgicSongs[this.currentSongIndex % this.nostalgicSongs.length];
                const musicPath = `/static/chatkada/sounds/${currentSong.file}`;
                music.src = musicPath;
                music.volume = this.settings.music.volume / 100;
                music.currentTime = musicState.currentTime || 0;
                music.loop = false;

                // Play with user interaction requirement handling
                const playPromise = music.play();
                if (playPromise !== undefined) {
                    playPromise.catch(e => {
                        console.log('Auto-play prevented, waiting for user interaction');
                        // Add one-time click listener to resume
                        document.addEventListener('click', () => {
                            if (this.settings.music.enabled) {
                                music.play().catch(err => console.log('Play failed:', err));
                            }
                        }, { once: true });
                    });
                }

                const currentSongElement = document.getElementById('current-song');
                if (currentSongElement) {
                    currentSongElement.textContent = currentSong.name;
                }
            }
        }

        return true;
    } catch (e) {
        console.log('Failed to restore music state:', e);
        return false;
    }
}

// Lightning and Thunder System - FIXED
startLightningTimer() {
    this.stopAllThunderTimers();

    // Only start if thunder is enabled
    if (!this.settings.thunder.enabled) return;

    const frequencies = {
        rare: [300000, 600000], // 5-10 minutes
        occasional: [120000, 300000], // 2-5 minutes
        frequent: [30000, 120000], // 30s-2 minutes
        storm: [10000, 30000] // 10-30 seconds
    };

    const [min, max] = frequencies[this.settings.thunder.frequency];
    const delay = Math.random() * (max - min) + min;

    this.lightningTimer = setTimeout(() => {
        if (this.settings.thunder.enabled && !this.lightningInProgress) {
            this.playThunderWithLightning();
        }
        // Restart lightning timer if still enabled
        if (this.settings.thunder.enabled) {
            this.startLightningTimer();
        }
    }, delay);
}

stopAllThunderTimers() {
    if (this.thunderTimer) {
        clearTimeout(this.thunderTimer);
        this.thunderTimer = null;
    }
    if (this.lightningTimer) {
        clearTimeout(this.lightningTimer);
        this.lightningTimer = null;
    }
    this.lightningInProgress = false;
}

playThunderWithLightning() {
    if (!this.settings.thunder.enabled || this.lightningInProgress) return;

    this.lightningInProgress = true;

    console.log('Playing lightning and thunder sequence...');

    // Step 1: Show lightning first
    this.createLightningEffect();

    // Step 2: Play thunder after realistic delay
    const thunderDelay = Math.random() * 3000 + 500; // 0.5-3.5 seconds delay
    this.thunderTimer = setTimeout(() => {
        if (this.settings.thunder.enabled) {
            this.playThunderSound();
        }
        this.lightningInProgress = false;
    }, thunderDelay);
}

playThunderSound() {
    if (!this.settings.thunder.enabled) return;

    const thunder = this.audioElements.thunder;
    if (!thunder) return;

    const randomThunder = this.thunderSounds[Math.floor(Math.random() * this.thunderSounds.length)];
    const thunderPath = `/static/chatkada/sounds/${randomThunder}`;

    thunder.src = thunderPath;
    thunder.volume = this.settings.thunder.volume / 100;
    thunder.currentTime = 0;

    thunder.play().catch(e => {
        console.log('Thunder play failed:', e);
        console.log('Trying to play:', thunderPath);
    });
}

testThunder() {
    console.log('Testing thunder and lightning...');
    this.playThunderWithLightning();
}

// FIXED Lightning Effect System
createLightningEffect() {
    console.log('Creating lightning effect...');

    const intensity = this.settings.lightning.intensity;
    const type = this.settings.lightning.type;

    // Create screen flash
    this.createScreenFlash(intensity);

    // Create lightning bolt if elements exist
    this.createLightningBolt(intensity, type);

    // Create branches for multiple/continuous types
    if (type === 'multiple' || type === 'continuous') {
        this.createLightningBranches(intensity);
    }
}

createScreenFlash(intensity) {
    const screenFlash = document.getElementById('screen-flash');
    const lightningFlash = document.getElementById('lightning-flash');

    const intensitySettings = {
        subtle: { opacity: 0.15, duration: 100 },
        medium: { opacity: 0.3, duration: 150 },
        bright: { opacity: 0.5, duration: 200 },
        extreme: { opacity: 0.7, duration: 250 }
    };

    const settings = intensitySettings[intensity] || intensitySettings.medium;

    // Screen flash
    if (screenFlash) {
        screenFlash.style.display = 'block';
        screenFlash.style.opacity = settings.opacity;

        setTimeout(() => {
            screenFlash.style.opacity = '0';
            setTimeout(() => {
                screenFlash.style.display = 'none';
            }, 100);
        }, settings.duration);
    }

    // Lightning flash in container
    if (lightningFlash) {
        lightningFlash.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.8) 0%, rgba(173, 216, 230, 0.4) 50%, transparent 100%);
                display: block;
                opacity: ${settings.opacity};
                transition: opacity 0.1s ease;
            `;

        setTimeout(() => {
            lightningFlash.style.opacity = '0';
            setTimeout(() => {
                lightningFlash.style.display = 'none';
            }, 100);
        }, settings.duration);
    }
}

createLightningBolt(intensity, type) {
    const bolt = document.getElementById('lightning-bolt');
    if (!bolt) return;

    const path = this.generateLightningPath();

    bolt.innerHTML = '';
    bolt.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: block;
            opacity: 1;
            transition: opacity 0.1s ease;
        `;

    const mainBolt = document.createElement('div');
    mainBolt.className = 'lightning-strike';
    mainBolt.innerHTML = path;
    mainBolt.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            filter: drop-shadow(0 0 10px rgba(255, 255, 255, 0.8));
        `;
    bolt.appendChild(mainBolt);

    if (type === 'multiple') {
        this.createMultipleFlashes(bolt);
    } else if (type === 'continuous') {
        this.createContinuousFlicker(bolt);
    } else {
        // Single flash
        setTimeout(() => {
            bolt.style.opacity = '0';
            setTimeout(() => {
                bolt.style.display = 'none';
            }, 200);
        }, 150);
    }
}

createMultipleFlashes(bolt) {
    let flashCount = 0;
    const maxFlashes = 3;

    const flash = () => {
        bolt.style.opacity = '1';
        setTimeout(() => {
            bolt.style.opacity = '0';
            flashCount++;
            if (flashCount < maxFlashes) {
                setTimeout(flash, 100 + Math.random() * 200);
            } else {
                setTimeout(() => {
                    bolt.style.display = 'none';
                }, 200);
            }
        }, 80 + Math.random() * 120);
    };

    flash();
}

createContinuousFlicker(bolt) {
    let flickerCount = 0;
    const maxFlickers = 8;

    const flicker = () => {
        bolt.style.opacity = Math.random() * 0.8 + 0.2;
        flickerCount++;
        if (flickerCount < maxFlickers) {
            setTimeout(flicker, 50 + Math.random() * 100);
        } else {
            setTimeout(() => {
                bolt.style.opacity = '0';
                setTimeout(() => {
                    bolt.style.display = 'none';
                }, 200);
            }, 100);
        }
    };

    flicker();
}

createLightningBranches(intensity) {
    const branches = document.getElementById('lightning-branches');
    if (!branches) return;

    branches.innerHTML = '';
    branches.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: block;
            opacity: 0.6;
            transition: opacity 0.1s ease;
        `;

    for (let i = 0; i < 3; i++) {
        const branch = document.createElement('div');
        branch.className = 'lightning-branch';
        branch.innerHTML = this.generateBranchPath();
        branch.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                filter: drop-shadow(0 0 5px rgba(255, 255, 255, 0.6));
            `;
        branches.appendChild(branch);
    }

    setTimeout(() => {
        branches.style.opacity = '0';
        setTimeout(() => {
            branches.style.display = 'none';
        }, 200);
    }, 200);
}

generateLightningPath() {
    const height = window.innerHeight;
    const width = window.innerWidth;

    let path = `<svg width="${width}" height="${height}" style="position: absolute; top: 0; left: 0; pointer-events: none;">`;
    path += `<defs><filter id="glow"><feGaussianBlur stdDeviation="3" result="coloredBlur"/><feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>`;
    path += `<path d="M${width / 2} 0`;

    let x = width / 2;
    let y = 0;

    for (let i = 0; i < 20; i++) {
        x += (Math.random() - 0.5) * 100;
        y += height / 20;
        path += ` L${x} ${y}`;
    }

    path += `" stroke="#ffffff" stroke-width="3" fill="none" opacity="0.9" filter="url(#glow)"/>`;
    path += `</svg>`;

    return path;
}

generateBranchPath() {
    const height = window.innerHeight;
    const width = window.innerWidth;

    let path = `<svg width="${width}" height="${height}" style="position: absolute; top: 0; left: 0; pointer-events: none;">`;
    path += `<path d="M${width / 3 + Math.random() * width / 3} ${height / 3}`;

    let x = width / 3 + Math.random() * width / 3;
    let y = height / 3;

    for (let i = 0; i < 8; i++) {
        x += (Math.random() - 0.5) * 60;
        y += height / 30;
        path += ` L${x} ${y}`;
    }

    path += `" stroke="#ffffff" stroke-width="1" fill="none" opacity="0.6"/>`;
    path += `</svg>`;

    return path;
}

updateRainEffect() {
    const container = document.getElementById('rain-container');
    if (!container) return;

    const intensity = this.settings.rain.intensity;
    container.innerHTML = '';

    const dropCounts = {
        light: 50,
        medium: 100,
        heavy: 200,
        storm: 300
    };

    const dropCount = dropCounts[intensity] || 100;

    for (let i = 0; i < dropCount; i++) {
        setTimeout(() => {
            this.createRainDrop();
        }, i * 50);
    }
}

createRainDrop() {
    const container = document.getElementById('rain-container');
    if (!container || !this.settings.rain.enabled) return;

    const drop = document.createElement('div');
    drop.className = 'rain-drop';
    drop.style.left = Math.random() * 100 + '%';
    drop.style.animationDuration = (Math.random() * 2 + 1) + 's';
    drop.style.opacity = Math.random() * 0.5 + 0.3;

    container.appendChild(drop);

    setTimeout(() => {
        if (drop.parentNode) {
            drop.parentNode.removeChild(drop);
        }
    }, 3000);
}

// Enhanced Realistic Mode
toggleRealisticMode() {
    this.realisticMode = !this.realisticMode;
    const btn = document.getElementById('realistic-mode-btn');

    if (btn) {
        if (this.realisticMode) {
            btn.innerHTML = '<i class="fas fa-magic"></i> Disable Realistic Mode';
            btn.classList.add('active');
            this.enableRealisticMode();
        } else {
            btn.innerHTML = '<i class="fas fa-magic"></i> Enable Realistic Mode';
            btn.classList.remove('active');
            this.disableRealisticMode();
        }
    }

    this.saveSettings();
}

enableRealisticMode() {
    // Apply muffled effect using Web Audio API
    if (this.audioContext && this.filterNodes) {
        Object.keys(this.filterNodes).forEach(key => {
            if (this.filterNodes[key]) {
                this.filterNodes[key].frequency.setTargetAtTime(
                    1000, // Muffled sound
                    this.audioContext.currentTime,
                    0.25
                );
            }
        });
    }

    // Start realistic mode changes but ONLY affect enabled toggles
    this.startRealisticChanges();

    console.log('Realistic mode enabled - muffled audio effect applied');
}

disableRealisticMode() {
    // Remove muffled effect
    if (this.audioContext && this.filterNodes) {
        Object.keys(this.filterNodes).forEach(key => {
            if (this.filterNodes[key]) {
                this.filterNodes[key].frequency.setTargetAtTime(
                    22050, // Clear sound
                    this.audioContext.currentTime,
                    0.25
                );
            }
        });
    }

    this.stopRealisticChanges();

    console.log('Realistic mode disabled - audio clarity restored');
}

startRealisticChanges() {
    this.stopRealisticChanges();

    this.realisticTimer = setInterval(() => {
        if (this.realisticMode) {
            this.randomizeSettings();
        }
    }, 45000); // Every 45 seconds

    console.log('Realistic mode: Dynamic changes started');
}

stopRealisticChanges() {
    if (this.realisticTimer) {
        clearInterval(this.realisticTimer);
        this.realisticTimer = null;
    }
}

randomizeSettings() {
    if (!this.realisticMode) return;

    console.log('Realistic mode: Randomizing ONLY enabled toggles...');

    // ONLY randomize settings for ENABLED toggles
    if (this.settings.rain.enabled) {
        const intensities = ['light', 'medium', 'heavy'];
        this.settings.rain.intensity = intensities[Math.floor(Math.random() * intensities.length)];
        this.settings.rain.volume = Math.floor(Math.random() * 30) + 20; // 20-50
    }

    if (this.settings.thunder.enabled) {
        // Sometimes disable thunder for realism
        if (Math.random() < 0.2) {
            this.settings.thunder.enabled = false;
        }
    } else {
        // Sometimes enable thunder if rain is active
        if (this.settings.rain.enabled && Math.random() < 0.1) {
            this.settings.thunder.enabled = true;
        }
    }

    if (this.settings.crowd.enabled) {
        this.settings.crowd.volume = Math.floor(Math.random() * 20) + 10; // 10-30
    }

    if (this.settings.music.enabled) {
        this.settings.music.volume = Math.floor(Math.random() * 15) + 15; // 15-30
    }

    // Apply changes
    this.updateAudioElements();
    this.updateControls();

    console.log('Realistic mode: Settings randomized for enabled toggles only');
}

updateAudioElements() {
    this.updateRain();
    this.updateThunder();
    this.updateCrowd();
    this.updateMusic();
}

updateControls() {
    const safeUpdate = (id, value, type = 'value') => {
        const element = document.getElementById(id);
        if (element) {
            if (type === 'checked') {
                element.checked = value;
            } else if (type === 'text') {
                element.textContent = value;
            } else {
                element.value = value;
            }
        }
    };

    // Update all controls
    safeUpdate('rain-toggle', this.settings.rain.enabled, 'checked');
    safeUpdate('rain-volume', this.settings.rain.volume);
    safeUpdate('rain-volume-display', this.settings.rain.volume + '%', 'text');
    safeUpdate('rain-intensity', this.settings.rain.intensity);

    safeUpdate('thunder-toggle', this.settings.thunder.enabled, 'checked');
    safeUpdate('thunder-volume', this.settings.thunder.volume);
    safeUpdate('thunder-volume-display', this.settings.thunder.volume + '%', 'text');
    safeUpdate('thunder-frequency', this.settings.thunder.frequency);

    safeUpdate('lightning-intensity', this.settings.lightning.intensity);
    safeUpdate('lightning-type', this.settings.lightning.type);

    safeUpdate('crowd-toggle', this.settings.crowd.enabled, 'checked');
    safeUpdate('crowd-volume', this.settings.crowd.volume);
    safeUpdate('crowd-volume-display', this.settings.crowd.volume + '%', 'text');

    safeUpdate('music-toggle', this.settings.music.enabled, 'checked');
    safeUpdate('music-volume', this.settings.music.volume);
    safeUpdate('music-volume-display', this.settings.music.volume + '%', 'text');
}

muteAll() {
    // Turn off all toggles
    this.settings.rain.enabled = false;
    this.settings.thunder.enabled = false;
    this.settings.crowd.enabled = false;
    this.settings.music.enabled = false;

    // Stop all audio
    this.stopAllThunderTimers();
    this.updateAudioElements();
    this.updateControls();
}

saveSettings() {
    const saveData = {
        ...this.settings,
        realisticMode: this.realisticMode
    };
    localStorage.setItem('chayakada-audio-settings', JSON.stringify(saveData));
}

loadSettings() {
    const saved = localStorage.getItem('chayakada-audio-settings');
    if (saved) {
        const savedData = JSON.parse(saved);
        this.settings = { ...this.settings, ...savedData };

        if (savedData.realisticMode !== undefined) {
            this.realisticMode = savedData.realisticMode;

            setTimeout(() => {
                if (this.realisticMode) {
                    this.enableRealisticMode();
                }
                this.updateControls();
            }, 1000);
        }
    }
}
}

// Initialize enhanced audio controller
document.addEventListener('DOMContentLoaded', () => {
    window.audioController = new EnhancedAudioController();
});
