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

    init() {
        this.playbackKey = 'chayakada-audio-playback';
        this.restoring = {};          // track -> true while its position is being restored
        this.lastPlaybackSave = 0;
        this.loadSettings();
        this.migrateLegacyMusicState();
        this.setupEventListeners();
        this.setupPlaybackPersistence();

        // Restore everything (on/off, track, volume, position) WITHOUT resetting
        // sources: this is what makes audio continue across page changes.
        this.restoreFromSnapshot();
        this.updateControls();
        this.updateSongDisplay();

        if (this.settings.thunder.enabled) this.startLightningTimer();
        this.createLightningElements(); // Create lightning elements on init

        // Web Audio (realistic-mode filter) is only wired after a user gesture,
        // otherwise a suspended AudioContext would silence the media elements.
        if (this.realisticMode) {
            const arm = () => {
                this.initWebAudio();
                if (this.realisticMode) this.enableRealisticMode();
            };
            if (navigator.userActivation && navigator.userActivation.hasBeenActive) arm();
            else document.addEventListener('pointerdown', arm, { once: true });
        }
    }

    // ---------- source helpers ----------
    absUrl(path) {
        return new URL(path, window.location.href).href;
    }

    // Compare by absolute URL (el.src / currentSrc are absolute, our paths are
    // relative and may contain spaces) and never reassign the same source.
    hasSrc(el, path) {
        if (!el) return false;
        const want = this.absUrl(path);
        const have = el.getAttribute('src') ? el.src : (el.currentSrc || '');
        return have === want || decodeURI(have) === decodeURI(want);
    }

    setSrcIfChanged(el, path) {
        if (!el || this.hasSrc(el, path)) return false;
        el.src = path;
        return true;
    }

    songPath(song) {
        return `/static/chatkada/sounds/${song.file}`;
    }

    currentSong() {
        if (!this.nostalgicSongs.length) return null;
        return this.nostalgicSongs[((this.currentSongIndex % this.nostalgicSongs.length) + this.nostalgicSongs.length) % this.nostalgicSongs.length];
    }

    updateSongDisplay() {
        const el = document.getElementById('current-song');
        if (!el) return;
        const song = this.currentSong();
        el.textContent = this.settings.music.enabled && song ? song.name : 'No song playing';
    }

    // ---------- playback persistence ----------
    readSnapshot() {
        try {
            const snap = JSON.parse(localStorage.getItem(this.playbackKey) || 'null');
            if (!snap || Date.now() - (snap.savedAt || 0) > 6 * 3600 * 1000) return null;
            return snap;
        } catch (e) {
            return null;
        }
    }

    trackState(name) {
        const el = this.audioElements[name];
        if (!el) return null;
        return {
            time: el.currentTime || 0,
            playing: !el.paused && !el.ended,
            src: el.currentSrc || el.src || ''
        };
    }

    savePlayback(force = false) {
        const now = Date.now();
        if (!force && now - this.lastPlaybackSave < 1000) return;
        this.lastPlaybackSave = now;
        try {
            const prev = this.readSnapshot() || {};
            const snap = { savedAt: now };
            ['rain', 'crowd', 'music'].forEach(name => {
                const el = this.audioElements[name];
                // While a track is still being restored (or has no media yet)
                // keep the previous value: never overwrite a good position with 0.
                if (!el || this.restoring[name] || el.readyState < 1) {
                    if (prev[name]) snap[name] = prev[name];
                    return;
                }
                snap[name] = this.trackState(name);
            });
            const song = this.currentSong();
            if (snap.music && song) snap.music.file = song.file;
            else if (prev.music && prev.music.file && snap.music) snap.music.file = prev.music.file;
            localStorage.setItem(this.playbackKey, JSON.stringify(snap));
        } catch (e) {
            console.warn('Failed to save audio playback state:', e);
        }
    }

    setupPlaybackPersistence() {
        ['rain', 'crowd', 'music'].forEach(name => {
            const el = this.audioElements[name];
            if (!el) return;
            el.preload = 'metadata';
            el.addEventListener('timeupdate', () => this.savePlayback(false));
            el.addEventListener('pause', () => this.savePlayback(true));
            el.addEventListener('playing', () => {
                this.savePlayback(true);
                if (window.persistentAudioManager) window.persistentAudioManager.hideAutoplayWarning();
            });
        });
        const flush = () => this.savePlayback(true);
        window.addEventListener('pagehide', flush);
        window.addEventListener('beforeunload', flush);
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') flush();
        });
        // Back/forward cache: the page is resumed with media paused -> resume
        // from the latest snapshot (another page may have advanced it).
        window.addEventListener('pageshow', (e) => {
            if (e.persisted) {
                this.loadSettings();
                this.updateControls();
                this.restoreFromSnapshot();
            }
        });
    }

    // Seek to a saved position once metadata is available, then play.
    resumeTrack(name, path, saved, volume, loop) {
        const el = this.audioElements[name];
        if (!el) return;
        this.restoring[name] = true;
        const changed = this.setSrcIfChanged(el, path);
        el.loop = loop;
        el.volume = Math.max(0, Math.min(1, volume / 100));
        const apply = () => {
            if (saved && saved.time > 0 && isFinite(saved.time)) {
                let t = saved.time;
                if (isFinite(el.duration) && el.duration > 0) {
                    t = loop ? t % el.duration : Math.min(t, Math.max(0, el.duration - 0.25));
                }
                // Only seek if we're not already there (bfcache resume keeps it)
                if (Math.abs((el.currentTime || 0) - t) > 0.75) {
                    try { el.currentTime = t; } catch (e) { /* not seekable yet */ }
                }
            }
            this.restoring[name] = false;
            const p = el.play();
            if (p && p.then) {
                p.then(() => {
                    if (window.persistentAudioManager) window.persistentAudioManager.hideAutoplayWarning();
                }).catch(() => {
                    if (window.persistentAudioManager) window.persistentAudioManager.onAutoplayBlocked();
                });
            }
        };
        if (!changed && el.readyState >= 1) {
            apply();
        } else {
            el.addEventListener('loadedmetadata', apply, { once: true });
            if (!changed && el.readyState === 0) el.load();
        }
    }

    restoreFromSnapshot() {
        const snap = this.readSnapshot() || {};
        const s = this.settings;
        if (s.rain.enabled) {
            this.resumeTrack('rain', `/static/chatkada/sounds/${this.rainSounds[s.rain.intensity] || 'Rain.mp3'}`,
                             snap.rain, s.rain.volume, true);
            const rc = document.getElementById('rain-container');
            if (rc) { rc.style.display = 'block'; this.updateRainEffect(); }
        }
        if (s.crowd.enabled) {
            this.resumeTrack('crowd', `/static/chatkada/sounds/${this.crowdSound}`, snap.crowd, s.crowd.volume, true);
        }
        if (s.music.enabled) {
            // Track identity is the file name (playlist order can be shuffled)
            const file = (snap.music && snap.music.file) || s.music.file;
            if (file) {
                const idx = this.nostalgicSongs.findIndex(x => x.file === file);
                if (idx >= 0) this.currentSongIndex = idx;
            }
            const song = this.currentSong();
            if (song) {
                const sameSong = snap.music && snap.music.file === song.file;
                this.resumeTrack('music', this.songPath(song), sameSong ? snap.music : null, s.music.volume, false);
            }
        }
        this.updateSongDisplay();
    }

    migrateLegacyMusicState() {
        try {
            const legacy = JSON.parse(localStorage.getItem('chayakada_music_state') || 'null');
            localStorage.removeItem('chayakada_music_state');
            localStorage.removeItem('chayakada_persistent_audio_state');
            if (legacy && !this.settings.music.file && this.nostalgicSongs[legacy.currentSongIndex]) {
                this.settings.music.file = this.nostalgicSongs[legacy.currentSongIndex].file;
            }
        } catch (e) { /* ignore */ }
    }

    initWebAudio() {
        if (this.audioContext) return;
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
            if (this.audioContext.state === 'suspended') this.audioContext.resume().catch(() => {});
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
            this.settings.rain.volume = Number(e.target.value);
            document.getElementById('rain-volume-display').textContent = e.target.value + '%';
            if (this.audioElements.rain) this.audioElements.rain.volume = this.settings.rain.volume / 100;
            this.saveSettings();
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
            this.settings.crowd.volume = Number(e.target.value);
            document.getElementById('crowd-volume-display').textContent = e.target.value + '%';
            if (this.audioElements.crowd) this.audioElements.crowd.volume = this.settings.crowd.volume / 100;
            this.saveSettings();
        });

        document.getElementById('music-shuffle')?.addEventListener('click', () => {
            this.shuffleSongs();
        });

        // Nostalgic radio controls (previously had no listeners at all)
        document.getElementById('music-toggle')?.addEventListener('change', (e) => {
            this.settings.music.enabled = e.target.checked;
            this.updateMusic();
        });

        document.getElementById('music-volume')?.addEventListener('input', (e) => {
            this.settings.music.volume = Number(e.target.value);
            document.getElementById('music-volume-display').textContent = e.target.value + '%';
            if (this.audioElements.music) this.audioElements.music.volume = this.settings.music.volume / 100;
            this.saveSettings();
        });

        document.getElementById('music-next')?.addEventListener('click', () => this.nextSong());
        document.getElementById('music-prev')?.addEventListener('click', () => this.previousSong());

        // Music ended event
        this.audioElements.music?.addEventListener('ended', () => {
            this.nextSong();
        });

        // User interaction to start audio context
        document.addEventListener('pointerdown', () => {
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
            const rainFile = this.rainSounds[this.settings.rain.intensity] || 'Rain.mp3';
            // keeps position when the source is unchanged (e.g. only volume moved)
            this.setSrcIfChanged(rain, `/static/chatkada/sounds/${rainFile}`);
            rain.volume = this.settings.rain.volume / 100;
            rain.loop = true;
            if (rain.paused) {
                rain.play().catch(() => window.persistentAudioManager && window.persistentAudioManager.onAutoplayBlocked());
            }
            if (rainContainer) {
                rainContainer.style.display = 'block';
                this.updateRainEffect();
            }
        } else {
            rain.pause();
            rain.currentTime = 0; // user switched it off: start fresh next time
            if (rainContainer) rainContainer.style.display = 'none';
        }
        this.saveSettings();
        this.savePlayback(true);
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
            this.setSrcIfChanged(crowd, `/static/chatkada/sounds/${this.crowdSound}`);
            crowd.volume = this.settings.crowd.volume / 100;
            crowd.loop = true;
            if (crowd.paused) {
                crowd.play().catch(() => window.persistentAudioManager && window.persistentAudioManager.onAutoplayBlocked());
            }
        } else {
            crowd.pause();
            crowd.currentTime = 0;
        }
        this.saveSettings();
        this.savePlayback(true);
    }

    updateMusic() {
        const music = this.audioElements.music;
        if (!music) return;

        if (this.settings.music.enabled) {
            music.volume = this.settings.music.volume / 100;
            this.playCurrentSong(false);
        } else {
            music.pause();
            music.currentTime = 0;
        }
        this.updateSongDisplay();
        this.saveSettings();
        this.savePlayback(true);
    }

    randomizeInitialSong() {
        this.currentSongIndex = Math.floor(Math.random() * this.nostalgicSongs.length);
    }

    // restart=true when the user picks another song; otherwise an already
    // loaded song keeps its position.
    playCurrentSong(restart = true) {
        const song = this.currentSong();
        const music = this.audioElements.music;
        if (!song || !music) return;

        const changed = this.setSrcIfChanged(music, this.songPath(song));
        if (restart && !changed) music.currentTime = 0;
        music.loop = false;
        music.volume = this.settings.music.volume / 100;
        this.settings.music.file = song.file;

        music.play().then(() => this.savePlayback(true))
            .catch(() => window.persistentAudioManager && window.persistentAudioManager.onAutoplayBlocked());
        this.updateSongDisplay();
        this.saveSettings();
    }

    nextSong() {
        if (this.nostalgicSongs.length === 0) return;
        this.currentSongIndex = (this.currentSongIndex + 1) % this.nostalgicSongs.length;
        this.settings.music.file = this.currentSong().file;
        if (this.settings.music.enabled) this.playCurrentSong(true);
        else { this.updateSongDisplay(); this.saveSettings(); }
    }

    previousSong() {
        if (this.nostalgicSongs.length === 0) return;
        this.currentSongIndex = (this.currentSongIndex - 1 + this.nostalgicSongs.length) % this.nostalgicSongs.length;
        this.settings.music.file = this.currentSong().file;
        if (this.settings.music.enabled) this.playCurrentSong(true);
        else { this.updateSongDisplay(); this.saveSettings(); }
    }

    shuffleSongs() {
        if (this.nostalgicSongs.length === 0) return;

        // Fisher-Yates shuffle algorithm
        for (let i = this.nostalgicSongs.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [this.nostalgicSongs[i], this.nostalgicSongs[j]] = [this.nostalgicSongs[j], this.nostalgicSongs[i]];
        }
        this.currentSongIndex = 0;
        this.settings.music.file = this.currentSong().file;
        if (this.settings.music.enabled) this.playCurrentSong(true);
        else { this.updateSongDisplay(); this.saveSettings(); }
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
        this.initWebAudio();
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

        const rmBtn = document.getElementById('realistic-mode-btn');
        if (rmBtn) {
            rmBtn.innerHTML = this.realisticMode
                ? '<i class="fas fa-magic"></i> Disable Realistic Mode'
                : '<i class="fas fa-magic"></i> Enable Realistic Mode';
            rmBtn.classList.toggle('active', !!this.realisticMode);
        }

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
        const song = this.currentSong();
        if (song) this.settings.music.file = song.file;
        const saveData = {
            ...this.settings,
            realisticMode: this.realisticMode
        };
        localStorage.setItem('chayakada-audio-settings', JSON.stringify(saveData));
    }

    loadSettings() {
        try {
            const saved = localStorage.getItem('chayakada-audio-settings');
            if (!saved) return;
            const savedData = JSON.parse(saved);
            ['rain', 'thunder', 'lightning', 'crowd', 'music'].forEach(k => {
                if (savedData[k]) this.settings[k] = { ...this.settings[k], ...savedData[k] };
            });
            if (savedData.realisticMode !== undefined) this.realisticMode = !!savedData.realisticMode;
            if (this.settings.music.file) {
                const idx = this.nostalgicSongs.findIndex(x => x.file === this.settings.music.file);
                if (idx >= 0) this.currentSongIndex = idx;
            }
        } catch (e) {
            console.warn('Bad audio settings in storage, using defaults', e);
        }
    }
}

// Initialize enhanced audio controller
document.addEventListener('DOMContentLoaded', () => {
    window.audioController = new EnhancedAudioController();
});
