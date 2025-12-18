// @ts-nocheck
/**
 * LipSync Manager using Web Audio API
 * Supports:
 * - Audio element playback (any format)
 * - Audio URL playback
 * - Real-time microphone input
 * - External media element connection (video/audio)
 */

export type LipSyncSource = 'audio' | 'microphone' | 'none';

export class LAppLipSyncManager {
  private _audioContext: AudioContext | null = null;
  private _analyser: AnalyserNode | null = null;
  private _mediaSource: MediaElementAudioSourceNode | MediaStreamAudioSourceNode | null = null;
  private _mediaElement: HTMLMediaElement | null = null;
  private _micStream: MediaStream | null = null;
  private _dataArray: Uint8Array | null = null;
  private _currentValue: number = 0;
  private _source: LipSyncSource = 'none';
  private _smoothing: number = 0.5;
  private _gain: number = 1.0;
  private _isActive: boolean = false;
  private _onAudioEnded: (() => void) | null = null;
  // Track whether we own the media element (created it) vs borrowed (external)
  private _ownsMediaElement: boolean = false;
  // Bound handler for cleanup
  private _boundEndedHandler: (() => void) | null = null;
  // Track created media sources with their AudioContext to avoid cross-context issues
  private static _mediaSourceCache = new WeakMap<HTMLMediaElement, { ctx: AudioContext; node: MediaElementAudioSourceNode }>();
  // Auto-unlock handlers (user gesture -> resume AudioContext)
  private _autoUnlockInstalled: boolean = false;
  private _autoUnlockHandler: (() => void) | null = null;
  // Track if we used captureStream (safe to disconnect) vs MediaElementSource (must keep connected)
  private _usedCaptureStream: boolean = false;
  // Silent gain node for captureStream branch to ensure analyser receives data
  private _silentGainNode: GainNode | null = null;

  constructor() {
    // Create the AudioContext early so we can "unlock" it on the very first user gesture.
    // Creating it early is fine; it will start suspended in most browsers until resumed.
    this.ensureAudioContextCreated();
    this.installAutoUnlockHandlers();
  }

  /**
   * Ensure AudioContext exists. Does NOT attempt to resume.
   */
  private ensureAudioContextCreated(): void {
    if (typeof window === 'undefined') return;
    if (!this._audioContext) {
      this._audioContext = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    }
  }

  /**
   * Attempt to resume AudioContext.
   * Returns true if context is running, false if still suspended (needs user gesture).
   */
  private async initAudioContext(): Promise<boolean> {
    this.ensureAudioContextCreated();
    if (!this._audioContext) return false;
    if (this._audioContext.state === 'suspended') {
      try {
        await this._audioContext.resume();
      } catch (e) {
        console.warn('[LipSync] AudioContext resume failed (may need user gesture):', e);
        return false;
      }
    }
    return this._audioContext.state === 'running';
  }

  /**
   * Install global gesture listeners to unlock AudioContext.
   * IMPORTANT: resume() must be called directly inside a user gesture handler.
   */
  private installAutoUnlockHandlers(): void {
    if (typeof document === 'undefined') return;
    if (this._autoUnlockInstalled) return;
    this._autoUnlockInstalled = true;

    const handler = () => {
      if (!this._audioContext) return;
      if (this._audioContext.state !== 'suspended') {
        this.removeAutoUnlockHandlers();
        return;
      }

      // Call resume() synchronously within the gesture handler.
      this._audioContext
        .resume()
        .catch((e) => {
          // Keep handlers installed; next gesture can retry.
          console.warn('[LipSync] AudioContext resume failed in gesture handler:', e);
        })
        .finally(() => {
          if (this._audioContext?.state === 'running') {
            this.removeAutoUnlockHandlers();
          }
        });
    };

    this._autoUnlockHandler = handler;

    // Use capture so we run before app handlers; keep it lightweight.
    document.addEventListener('pointerdown', handler, { capture: true, passive: true });
    document.addEventListener('touchend', handler, { capture: true, passive: true });
    document.addEventListener('keydown', handler, { capture: true });
  }

  private removeAutoUnlockHandlers(): void {
    if (!this._autoUnlockHandler) return;
    const handler = this._autoUnlockHandler;
    this._autoUnlockHandler = null;

    // Use boolean capture flag so removeEventListener matches across browsers.
    document.removeEventListener('pointerdown', handler, true);
    document.removeEventListener('touchend', handler, true);
    document.removeEventListener('keydown', handler, true);
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
    const contextReady = await this.initAudioContext();
    if (!contextReady) {
      throw new Error('AudioContext not ready (may need user gesture)');
    }

    return new Promise((resolve, reject) => {
      const audio = new Audio();
      audio.crossOrigin = 'anonymous';
      audio.src = url;

      // We own this element (created it ourselves)
      this._mediaElement = audio;
      this._ownsMediaElement = true;

      audio.oncanplaythrough = async () => {
        try {
          this.createAnalyser();
          if (!this._audioContext || !this._analyser || !this._mediaElement) {
            throw new Error('Audio context not initialized');
          }

          this._mediaSource = this._audioContext.createMediaElementSource(this._mediaElement);
          this._mediaSource.connect(this._analyser);
          this._analyser.connect(this._audioContext.destination);

          this._source = 'audio';
          this._isActive = true;
          await audio.play();
          resolve();
        } catch (err) {
          reject(err);
        }
      };

      // Use addEventListener instead of property to avoid overwriting
      this._boundEndedHandler = () => {
        this._isActive = false;
        this._currentValue = 0;
        this._onAudioEnded?.();
      };
      audio.addEventListener('ended', this._boundEndedHandler);

      audio.onerror = () => {
        reject(new Error('Failed to load audio'));
      };
    });
  }

  /**
   * Connect to an existing media element (video or audio) for lip sync.
   * IMPORTANT: This does NOT pause or seek the element - it's external and we don't own it.
   *
   * SAFETY PRINCIPLE: Never break audio playback. If lip sync cannot be established,
   * gracefully degrade to "audio works, no lip sync" rather than silence.
   *
   * @param mediaElement HTMLMediaElement (video or audio) to connect
   */
  public async connectAudioElement(mediaElement: HTMLMediaElement): Promise<void> {
    this.ensureAudioContextCreated();
    if (!this._audioContext) return;

    // If connecting to the same element, just ensure connection is active
    if (this._mediaElement === mediaElement && this._mediaSource && this._isActive) {
      console.debug('[LipSync] Already connected to this element');
      return;
    }

    // Create new analyser for this connection
    const newAnalyser = this._audioContext.createAnalyser();
    newAnalyser.fftSize = 256;
    newAnalyser.smoothingTimeConstant = this._smoothing;

    let newMediaSource: MediaElementAudioSourceNode | MediaStreamAudioSourceNode | null = null;
    let usedCaptureStream = false;

    // Path A (preferred): captureStream() -> MediaStreamSource -> Analyser -> SilentGain -> Destination.
    // This is SAFE - it does NOT affect the element's own audio output.
    // We connect analyser to a silent gain node to ensure the audio graph is "pulled" by the browser.
    const captureStreamFn =
      (mediaElement as unknown as { captureStream?: () => MediaStream; mozCaptureStream?: () => MediaStream }).captureStream ||
      (mediaElement as unknown as { mozCaptureStream?: () => MediaStream }).mozCaptureStream;

    let newSilentGain: GainNode | null = null;

    if (captureStreamFn) {
      try {
        const stream = captureStreamFn.call(mediaElement);
        const audioTracks = stream.getAudioTracks();
        if (audioTracks.length > 0) {
          newMediaSource = this._audioContext.createMediaStreamSource(stream);
          newMediaSource.connect(newAnalyser);

          // Create silent gain node to ensure analyser receives data on all browsers
          // Without this, some browsers won't process the audio graph
          newSilentGain = this._audioContext.createGain();
          newSilentGain.gain.value = 0; // Silent - no audible output
          newAnalyser.connect(newSilentGain);
          newSilentGain.connect(this._audioContext.destination);

          usedCaptureStream = true;
          console.debug('[LipSync] Using captureStream() for', mediaElement.tagName);
        } else {
          console.warn('[LipSync] captureStream() returned no audio tracks');
        }
      } catch (error) {
        console.warn('[LipSync] captureStream() failed:', error);
      }
    }

    // Path B (fallback): MediaElementSource -> Analyser -> Destination.
    // WARNING: This "steals" element output and routes through WebAudio.
    // Only safe when AudioContext is running; otherwise audio will be silent.
    if (!newMediaSource) {
      // Check if we previously created a MediaElementSource for this element
      const cached = LAppLipSyncManager._mediaSourceCache.get(mediaElement);

      // Validate cache: must be from the same AudioContext
      if (cached && cached.ctx === this._audioContext) {
        // CRITICAL: If we previously used createMediaElementSource(), we MUST keep it
        // connected to destination, otherwise audio will be silent.
        // Reconnect it to the new analyser and destination.
        try {
          cached.node.disconnect();
        } catch (e) {
          // Ignore disconnect errors
        }
        try {
          cached.node.connect(newAnalyser);
          newAnalyser.connect(this._audioContext.destination);
          newMediaSource = cached.node;
          console.debug('[LipSync] Reconnected cached MediaElementSource for', mediaElement.tagName);
        } catch (error) {
          // Connection failed - try to at least keep audio playing
          console.error('[LipSync] Failed to reconnect cached source:', error);
          try {
            cached.node.connect(this._audioContext.destination);
          } catch (e) {
            // Last resort failed
          }
          return;
        }
      } else {
        // No valid cached source - need to create new one, but only if AudioContext is running
        const contextReady = await this.initAudioContext();
        if (!contextReady) {
          // AudioContext suspended - cannot safely use createMediaElementSource()
          // Degrade gracefully: audio plays normally, no lip sync
          console.warn('[LipSync] AudioContext suspended, lip sync unavailable (audio will play normally)');
          return;
        }

        // AudioContext is running, safe to create MediaElementSource
        try {
          const mediaSource = this._audioContext.createMediaElementSource(mediaElement);
          LAppLipSyncManager._mediaSourceCache.set(mediaElement, { ctx: this._audioContext, node: mediaSource });
          mediaSource.connect(newAnalyser);
          newAnalyser.connect(this._audioContext.destination);
          newMediaSource = mediaSource;
          console.debug('[LipSync] Created new MediaElementSource for', mediaElement.tagName);
        } catch (error) {
          // Failed to create source - degrade gracefully
          console.error('[LipSync] Failed to create MediaElementSource:', error);
          return;
        }
      }
    }

    // SUCCESS: We have a working connection. Now clean up old state.
    // IMPORTANT: Only disconnect old source AFTER new connection is established.

    // Clean up old silent gain node
    if (this._silentGainNode) {
      try {
        this._silentGainNode.disconnect();
      } catch (e) {
        // Ignore disconnect errors
      }
    }

    // Only disconnect old captureStream source (safe to disconnect)
    // Do NOT disconnect old MediaElementSource - it would silence the audio
    if (this._mediaSource && this._mediaSource !== newMediaSource && this._usedCaptureStream) {
      try {
        this._mediaSource.disconnect();
      } catch (e) {
        // Ignore disconnect errors
      }
    }

    if (this._mediaElement && this._boundEndedHandler) {
      this._mediaElement.removeEventListener('ended', this._boundEndedHandler);
    }

    // Update state
    this._analyser = newAnalyser;
    this._dataArray = new Uint8Array(newAnalyser.frequencyBinCount);
    this._mediaSource = newMediaSource;
    this._mediaElement = mediaElement;
    this._ownsMediaElement = false;
    this._usedCaptureStream = usedCaptureStream;
    this._silentGainNode = newSilentGain;
    this._source = 'audio';
    this._isActive = true;

    // Set up ended handler
    this._boundEndedHandler = () => {
      this._isActive = false;
      this._currentValue = 0;
      this._onAudioEnded?.();
    };
    mediaElement.addEventListener('ended', this._boundEndedHandler);

    console.debug('[LipSync] Connected to', mediaElement.tagName,
      '- method:', usedCaptureStream ? 'captureStream' : 'MediaElementSource',
      '- AudioContext:', this._audioContext.state);
  }

  /**
   * Disconnect audio graph without affecting media playback.
   * Used internally when switching sources.
   */
  private disconnectAudioGraph(): void {
    this._isActive = false;
    this._currentValue = 0;

    // Remove event listener from previous element
    if (this._mediaElement && this._boundEndedHandler) {
      this._mediaElement.removeEventListener('ended', this._boundEndedHandler);
      this._boundEndedHandler = null;
    }

    // Disconnect media source from analyser (cache, if any, is held separately)
    if (this._mediaSource) {
      try {
        this._mediaSource.disconnect();
      } catch (e) {
        // Ignore disconnect errors
      }
      this._mediaSource = null;
    }

    // Clear reference to external element (but don't pause/seek it!)
    this._mediaElement = null;
    this._ownsMediaElement = false;
    this._source = 'none';
  }

  /**
   * Start microphone input for real-time lip sync
   * @returns Promise that resolves when mic is connected
   */
  public async startMicrophone(): Promise<void> {
    await this.stopLipSync();
    const contextReady = await this.initAudioContext();
    if (!contextReady) {
      throw new Error('AudioContext not ready (may need user gesture)');
    }

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
      console.error('[LipSync] Failed to access microphone:', err);
      throw err;
    }
  }

  /**
   * Stop current lip sync source.
   * Only pauses/seeks media elements that we created ourselves.
   *
   * SAFETY: For external media elements using MediaElementSource, we do NOT
   * disconnect the source as that would silence the audio. The source remains
   * connected to destination to keep audio playing.
   */
  public async stopLipSync(): Promise<void> {
    this._isActive = false;
    this._currentValue = 0;

    // Remove event listener from media element
    if (this._mediaElement && this._boundEndedHandler) {
      this._mediaElement.removeEventListener('ended', this._boundEndedHandler);
      this._boundEndedHandler = null;
    }

    // Only stop media element if we own it (created it ourselves)
    if (this._mediaElement && this._ownsMediaElement) {
      this._mediaElement.pause();
      this._mediaElement.currentTime = 0;
    }
    this._mediaElement = null;
    this._ownsMediaElement = false;

    // Stop microphone stream
    if (this._micStream) {
      this._micStream.getTracks().forEach(track => track.stop());
      this._micStream = null;
    }

    // Disconnect silent gain node (used by captureStream path)
    if (this._silentGainNode) {
      try {
        this._silentGainNode.disconnect();
      } catch (e) {
        // Ignore disconnect errors
      }
      this._silentGainNode = null;
    }

    // Disconnect media source - but only if safe to do so
    // captureStream sources: safe to disconnect (element outputs audio itself)
    // MediaElementSource for owned elements: safe to disconnect (we're stopping it anyway)
    // MediaElementSource for external elements: DO NOT disconnect (would silence audio!)
    if (this._mediaSource) {
      const safeToDisconnect = this._usedCaptureStream || this._ownsMediaElement || this._source === 'microphone';

      if (safeToDisconnect) {
        try {
          this._mediaSource.disconnect();
        } catch (e) {
          // Ignore disconnect errors
        }
        this._mediaSource = null;
      } else {
        // External MediaElementSource - leave connected to keep audio playing
        // Just clear our reference so we don't try to reuse it incorrectly
        console.debug('[LipSync] Keeping MediaElementSource connected for external element');
        this._mediaSource = null;
      }
    }

    this._usedCaptureStream = false;
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
   * Pause audio playback (only for owned media elements)
   */
  public pause(): void {
    if (this._mediaElement && this._ownsMediaElement) {
      this._mediaElement.pause();
    }
  }

  /**
   * Resume audio playback (only for owned media elements)
   */
  public resume(): void {
    if (this._mediaElement && this._ownsMediaElement) {
      this._mediaElement.play();
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
    this.removeAutoUnlockHandlers();
    this._analyser = null;
    this._dataArray = null;
  }
}
