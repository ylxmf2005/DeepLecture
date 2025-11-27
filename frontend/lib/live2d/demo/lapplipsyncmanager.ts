// @ts-nocheck
/**
 * LipSync Manager using Web Audio API
 * Supports:
 * - Audio element playback (any format)
 * - Audio URL playback
 * - Real-time microphone input
 */

export type LipSyncSource = 'audio' | 'microphone' | 'none';

export class LAppLipSyncManager {
  private _audioContext: AudioContext | null = null;
  private _analyser: AnalyserNode | null = null;
  private _mediaSource: MediaElementAudioSourceNode | MediaStreamAudioSourceNode | null = null;
  private _audioElement: HTMLAudioElement | null = null;
  private _micStream: MediaStream | null = null;
  private _dataArray: Uint8Array | null = null;
  private _currentValue: number = 0;
  private _source: LipSyncSource = 'none';
  private _smoothing: number = 0.5;
  private _gain: number = 1.0;
  private _isActive: boolean = false;
  private _onAudioEnded: (() => void) | null = null;
  // Track created media sources to avoid recreating them
  private static _mediaSourceCache = new WeakMap<HTMLMediaElement, MediaElementAudioSourceNode>();

  constructor() {}

  /**
   * Initialize audio context (must be called after user interaction)
   */
  private async initAudioContext(): Promise<void> {
    if (!this._audioContext) {
      this._audioContext = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    }
    if (this._audioContext.state === 'suspended') {
      await this._audioContext.resume();
    }
  }

  /**
   * Create analyser node
   */
  private createAnalyser(): void {
    if (!this._audioContext) return;

    this._analyser = this._audioContext.createAnalyser();
    this._analyser.fftSize = 256;
    this._analyser.smoothingTimeConstant = this._smoothing;
    this._dataArray = new Uint8Array(this._analyser.frequencyBinCount);
  }

  /**
   * Play audio from URL with lip sync
   * @param url Audio file URL
   * @returns Promise that resolves when playback starts
   */
  public async playAudioUrl(url: string): Promise<void> {
    await this.stopLipSync();
    await this.initAudioContext();

    return new Promise((resolve, reject) => {
      this._audioElement = new Audio();
      this._audioElement.crossOrigin = 'anonymous';
      this._audioElement.src = url;

      this._audioElement.oncanplaythrough = async () => {
        try {
          this.createAnalyser();
          if (!this._audioContext || !this._analyser || !this._audioElement) {
            throw new Error('Audio context not initialized');
          }

          this._mediaSource = this._audioContext.createMediaElementSource(this._audioElement);
          this._mediaSource.connect(this._analyser);
          this._analyser.connect(this._audioContext.destination);

          this._source = 'audio';
          this._isActive = true;
          await this._audioElement.play();
          resolve();
        } catch (err) {
          reject(err);
        }
      };

      this._audioElement.onended = () => {
        this._isActive = false;
        this._currentValue = 0;
        this._onAudioEnded?.();
      };

      this._audioElement.onerror = () => {
        reject(new Error('Failed to load audio'));
      };
    });
  }

  /**
   * Connect to an existing audio element
   * @param audioElement HTMLAudioElement to connect
   */
  public async connectAudioElement(audioElement: HTMLAudioElement): Promise<void> {
    await this.stopLipSync();
    await this.initAudioContext();

    this.createAnalyser();
    if (!this._audioContext || !this._analyser) {
      throw new Error('Audio context not initialized');
    }

    // Store reference but don't create new element
    this._audioElement = audioElement;

    // Check if we already have a media source for this element
    let mediaSource = LAppLipSyncManager._mediaSourceCache.get(audioElement);

    if (!mediaSource) {
      // Create source from existing element only if not already created
      try {
        mediaSource = this._audioContext.createMediaElementSource(audioElement);
        LAppLipSyncManager._mediaSourceCache.set(audioElement, mediaSource);
      } catch (error) {
        console.error('Failed to create media element source:', error);
        throw error;
      }
    }

    this._mediaSource = mediaSource;

    // Disconnect from previous connections and reconnect to current analyser
    try {
      this._mediaSource.disconnect();
    } catch (e) {
      // Ignore if not connected
    }

    this._mediaSource.connect(this._analyser);
    this._analyser.connect(this._audioContext.destination);

    this._source = 'audio';
    this._isActive = true;

    audioElement.onended = () => {
      this._isActive = false;
      this._currentValue = 0;
      this._onAudioEnded?.();
    };
  }

  /**
   * Start microphone input for real-time lip sync
   * @returns Promise that resolves when mic is connected
   */
  public async startMicrophone(): Promise<void> {
    await this.stopLipSync();
    await this.initAudioContext();

    try {
      this._micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      this.createAnalyser();
      if (!this._audioContext || !this._analyser) {
        throw new Error('Audio context not initialized');
      }

      this._mediaSource = this._audioContext.createMediaStreamSource(this._micStream);
      this._mediaSource.connect(this._analyser);
      // Don't connect to destination to avoid feedback

      this._source = 'microphone';
      this._isActive = true;
    } catch (err) {
      console.error('Failed to access microphone:', err);
      throw err;
    }
  }

  /**
   * Stop current lip sync source
   */
  public async stopLipSync(): Promise<void> {
    this._isActive = false;
    this._currentValue = 0;

    // Stop audio element
    if (this._audioElement) {
      this._audioElement.pause();
      this._audioElement.currentTime = 0;
      this._audioElement = null;
    }

    // Stop microphone stream
    if (this._micStream) {
      this._micStream.getTracks().forEach(track => track.stop());
      this._micStream = null;
    }

    // Disconnect media source
    if (this._mediaSource) {
      try {
        this._mediaSource.disconnect();
      } catch (e) {
        // Ignore disconnect errors
      }
      this._mediaSource = null;
    }

    this._source = 'none';
  }

  /**
   * Update and get current lip sync value (call every frame)
   * @returns Current lip sync value (0-1)
   */
  public update(): number {
    if (!this._isActive || !this._analyser || !this._dataArray) {
      return 0;
    }

    // Get frequency data
    this._analyser.getByteFrequencyData(this._dataArray);

    // Calculate RMS (Root Mean Square) for volume
    let sum = 0;
    const len = this._dataArray.length;

    // Focus on lower frequencies (better for voice)
    const voiceRange = Math.floor(len * 0.5); // First half of frequencies
    for (let i = 0; i < voiceRange; i++) {
      const normalized = this._dataArray[i] / 255;
      sum += normalized * normalized;
    }

    const rms = Math.sqrt(sum / voiceRange);

    // Apply gain and clamp to 0-1
    let value = Math.min(1, rms * this._gain * 2);

    // Apply smoothing
    this._currentValue = this._currentValue * this._smoothing + value * (1 - this._smoothing);

    return this._currentValue;
  }

  /**
   * Get current lip sync value without updating
   */
  public getValue(): number {
    return this._currentValue;
  }

  /**
   * Check if lip sync is active
   */
  public isActive(): boolean {
    return this._isActive;
  }

  /**
   * Get current source type
   */
  public getSource(): LipSyncSource {
    return this._source;
  }

  /**
   * Set smoothing factor (0-1, higher = smoother)
   */
  public setSmoothing(value: number): void {
    this._smoothing = Math.max(0, Math.min(1, value));
    if (this._analyser) {
      this._analyser.smoothingTimeConstant = this._smoothing;
    }
  }

  /**
   * Set gain multiplier
   */
  public setGain(value: number): void {
    this._gain = Math.max(0, value);
  }

  /**
   * Set callback for when audio ends
   */
  public setOnAudioEnded(callback: (() => void) | null): void {
    this._onAudioEnded = callback;
  }

  /**
   * Set lip sync value directly (for external control)
   */
  public setValueDirectly(value: number): void {
    this._currentValue = Math.max(0, Math.min(1, value));
    this._isActive = true;
    this._source = 'none';
  }

  /**
   * Pause audio playback
   */
  public pause(): void {
    if (this._audioElement) {
      this._audioElement.pause();
    }
  }

  /**
   * Resume audio playback
   */
  public resume(): void {
    if (this._audioElement) {
      this._audioElement.play();
    }
  }

  /**
   * Release all resources
   */
  public release(): void {
    this.stopLipSync();
    if (this._audioContext) {
      this._audioContext.close();
      this._audioContext = null;
    }
    this._analyser = null;
    this._dataArray = null;
  }
}
