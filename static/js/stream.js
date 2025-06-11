// Audio Stream Player following SOLID principles

// Single Responsibility Principle: Each class has one responsibility
class AudioEngine {
    constructor() {
        this.audio = null;
        this.isPlaying = false;
        this.currentStation = null;
    }

    async play(streamUrl) {
        try {
            if (this.audio) {
                this.stop();
            }

            this.audio = new Audio();
            this.audio.crossOrigin = "anonymous";
            this.audio.preload = "none";
            
            // Set up error handling
            this.audio.onerror = () => {
                throw new Error('Failed to load audio stream');
            };

            this.audio.src = streamUrl;
            await this.audio.play();
            this.isPlaying = true;
            
            return true;
        } catch (error) {
            this.isPlaying = false;
            throw error;
        }
    }

    stop() {
        if (this.audio) {
            this.audio.pause();
            this.audio.currentTime = 0;
            this.audio.src = '';
            this.audio = null;
        }
        this.isPlaying = false;
    }

    pause() {
        if (this.audio && this.isPlaying) {
            this.audio.pause();
            this.isPlaying = false;
        }
    }

    resume() {
        if (this.audio && !this.isPlaying) {
            this.audio.play();
            this.isPlaying = true;
        }
    }

    setVolume(volume) {
        if (this.audio) {
            this.audio.volume = Math.max(0, Math.min(1, volume));
        }
    }

    getPlayingState() {
        return {
            isPlaying: this.isPlaying,
            currentStation: this.currentStation
        };
    }
}

// Open/Closed Principle: Open for extension, closed for modification
class EventEmitter {
    constructor() {
        this.events = {};
    }

    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
    }

    emit(event, data) {
        if (this.events[event]) {
            this.events[event].forEach(callback => callback(data));
        }
    }

    off(event, callback) {
        if (this.events[event]) {
            this.events[event] = this.events[event].filter(cb => cb !== callback);
        }
    }
}

// Liskov Substitution Principle: UI components can be substituted
class UIComponent extends EventEmitter {
    constructor(element) {
        super();
        this.element = element;
    }

    show() {
        if (this.element) {
            this.element.style.display = 'block';
        }
    }

    hide() {
        if (this.element) {
            this.element.style.display = 'none';
        }
    }

    updateContent(content) {
        if (this.element) {
            this.element.innerHTML = content;
        }
    }
}

class PlayButton extends UIComponent {
    constructor(element) {
        super(element);
        this.isPlaying = false;
        this.setupEventListeners();
    }

    setupEventListeners() {
        if (this.element) {
            this.element.addEventListener('click', () => {
                this.emit('toggle-play');
            });
        }
    }

    updateState(isPlaying) {
        this.isPlaying = isPlaying;
        if (this.element) {
            const icon = this.element.querySelector('i');
            if (icon) {
                icon.className = isPlaying ? 'fas fa-pause mr-2' : 'fas fa-play mr-2';
            }
            this.element.textContent = isPlaying ? 'Stop Station' : 'Play Station';
            if (icon) {
                this.element.insertBefore(icon, this.element.firstChild);
            }
        }
    }
}

class StatusIndicator extends UIComponent {
    constructor(element) {
        super(element);
    }

    showLoading() {
        this.updateContent('<i class="fas fa-spinner fa-spin mr-2"></i>Loading...');
        this.element.className = 'bg-yellow-100 text-yellow-800 px-4 py-2 rounded-lg';
    }

    showPlaying(stationName) {
        this.updateContent(`<i class="fas fa-play mr-2"></i>Playing: ${stationName}`);
        this.element.className = 'bg-green-100 text-green-800 px-4 py-2 rounded-lg';
    }

    showError(message) {
        this.updateContent(`<i class="fas fa-exclamation-triangle mr-2"></i>${message}`);
        this.element.className = 'bg-red-100 text-red-800 px-4 py-2 rounded-lg';
    }

    showStopped() {
        this.updateContent('<i class="fas fa-stop mr-2"></i>Stopped');
        this.element.className = 'bg-gray-100 text-gray-800 px-4 py-2 rounded-lg';
    }
}

// Interface Segregation Principle: Specific interfaces for different needs
class StreamUrlResolver {
    static async resolveUrl(url) {
        // Handle different stream URL formats
        if (url.includes('.m3u') || url.includes('.pls')) {
            try {
                const response = await fetch(url);
                const text = await response.text();
                const streamUrl = this.parsePlaylist(text);
                return streamUrl || url;
            } catch (error) {
                console.warn('Failed to resolve playlist, using original URL:', error);
                return url;
            }
        }
        return url;
    }

    static parsePlaylist(content) {
        // Parse M3U playlist
        if (content.includes('#EXTM3U')) {
            const lines = content.split('\n');
            for (const line of lines) {
                if (line.trim() && !line.startsWith('#')) {
                    return line.trim();
                }
            }
        }
        
        // Parse PLS playlist
        if (content.includes('[playlist]')) {
            const match = content.match(/File\d+=(.+)/i);
            if (match) {
                return match[1].trim();
            }
        }
        
        return null;
    }
}

// Dependency Inversion Principle: High-level modules don't depend on low-level modules
class RadioStreamPlayer extends EventEmitter {
    constructor(audioEngine = new AudioEngine()) {
        super();
        this.audioEngine = audioEngine;
        this.currentStation = null;
        this.ui = {
            playButton: null,
            statusIndicator: null
        };
    }

    // Initialize UI components
    initializeUI() {
        const playButton = document.querySelector('[onclick*="playStation"]');
        const statusContainer = this.createStatusIndicator();
        
        if (playButton) {
            this.ui.playButton = new PlayButton(playButton);
            this.ui.playButton.on('toggle-play', () => this.togglePlayback());
            
            // Remove the inline onclick handler
            playButton.removeAttribute('onclick');
        }

        if (statusContainer) {
            this.ui.statusIndicator = new StatusIndicator(statusContainer);
        }
    }

    createStatusIndicator() {
        const container = document.createElement('div');
        container.className = 'mt-4 text-center';
        container.style.display = 'none';
        
        const playButton = document.querySelector('[onclick*="playStation"]');
        if (playButton && playButton.parentNode) {
            playButton.parentNode.insertBefore(container, playButton.nextSibling);
        }
        
        return container;
    }

    async playStation(stationId, stationName, country, streamUrl) {
        try {
            this.currentStation = { stationId, stationName, country, streamUrl };
            
            if (this.ui.statusIndicator) {
                this.ui.statusIndicator.show();
                this.ui.statusIndicator.showLoading();
            }

            // Resolve the actual stream URL
            const resolvedUrl = await StreamUrlResolver.resolveUrl(streamUrl);
            
            // Start playback
            await this.audioEngine.play(resolvedUrl);
            
            // Update UI
            if (this.ui.playButton) {
                this.ui.playButton.updateState(true);
            }
            
            if (this.ui.statusIndicator) {
                this.ui.statusIndicator.showPlaying(stationName);
            }

            this.emit('station-started', this.currentStation);
            
        } catch (error) {
            console.error('Failed to play station:', error);
            
            if (this.ui.statusIndicator) {
                this.ui.statusIndicator.showError('Failed to play station. Please try again.');
            }
            
            if (this.ui.playButton) {
                this.ui.playButton.updateState(false);
            }

            this.emit('station-error', { error, station: this.currentStation });
        }
    }

    stopStation() {
        this.audioEngine.stop();
        
        if (this.ui.playButton) {
            this.ui.playButton.updateState(false);
        }
        
        if (this.ui.statusIndicator) {
            this.ui.statusIndicator.showStopped();
            setTimeout(() => {
                this.ui.statusIndicator.hide();
            }, 2000);
        }

        this.emit('station-stopped', this.currentStation);
        this.currentStation = null;
    }

    togglePlayback() {
        if (this.audioEngine.isPlaying) {
            this.stopStation();
        } else if (this.currentStation) {
            this.playStation(
                this.currentStation.stationId,
                this.currentStation.stationName,
                this.currentStation.country,
                this.currentStation.streamUrl
            );
        }
    }

    setVolume(volume) {
        this.audioEngine.setVolume(volume);
    }

    getCurrentStation() {
        return this.currentStation;
    }

    isPlaying() {
        return this.audioEngine.isPlaying;
    }
}

// Global instance and initialization
let radioPlayer = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    radioPlayer = new RadioStreamPlayer();
    radioPlayer.initializeUI();
    
    // Listen to player events
    radioPlayer.on('station-started', (station) => {
        console.log('Started playing:', station.stationName);
    });
    
    radioPlayer.on('station-stopped', (station) => {
        console.log('Stopped playing:', station?.stationName);
    });
    
    radioPlayer.on('station-error', ({ error, station }) => {
        console.error('Playback error:', error.message);
    });
});

// Global function for template compatibility
function playStation(stationId, stationName, country, streamUrl = null) {
    if (!radioPlayer) {
        console.error('Radio player not initialized');
        return;
    }
    
    // If no stream URL provided, try to find it in the page
    if (!streamUrl) {
        const streamElement = document.querySelector('code');
        streamUrl = streamElement ? streamElement.textContent.trim() : null;
    }
    
    if (!streamUrl) {
        console.error('No stream URL found');
        return;
    }
    
    radioPlayer.playStation(stationId, stationName, country, streamUrl);
}

// Export for module usage
export {
    RadioStreamPlayer,
    AudioEngine,
    StreamUrlResolver,
    PlayButton,
    StatusIndicator
};