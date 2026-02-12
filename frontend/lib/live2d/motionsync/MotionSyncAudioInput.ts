// @ts-nocheck
/**
 * MotionSync Audio Input
 * Captures real-time audio from microphone using AudioWorklet for MotionSync
 *
 * Based on Live2D Cubism SDK sample code
 */

import { logger } from '@/shared/infrastructure';

const log = logger.scope('MotionSyncAudioInput');

/**
 * Circular buffer for storing audio samples
 */
class AudioSampleBuffer {
  private _buffer: Float32Array;
  private _size: number;
  private _head: number;

  constructor(size: number) {
    this._buffer = new Float32Array(size);
    this._size = 0;
    this._head = 0;
  }

  get size(): number {
    return this._size;
  }

  addSample(value: number): void {
    this._buffer[this._head] = value;
    this._size = Math.min(this._size + 1, this._buffer.length);
    this._head++;
    if (this._head >= this._buffer.length) {
      this._head = 0;
    }
  }

  addSamples(samples: Float32Array): void {
    for (let i = 0; i < samples.length; i++) {
      this.addSample(samples[i]);
    }
  }

  /**
   * Convert buffer to array for MotionSync
   * Returns samples in correct order (oldest to newest)
   */
  toArray(): number[] {
    const result: number[] = [];
    let p = this._head - this._size;
    if (p < 0) {
      p += this._buffer.length;
    }
    for (let i = 0; i < this._size; i++) {
      result.push(this._buffer[p]);
      p++;
      if (p >= this._buffer.length) {
        p = 0;
      }
    }
    return result;
  }

  clear(): void {
    this._size = 0;
    this._head = 0;
  }
}

export interface MotionSyncAudioInputOptions {
  /** Sample rate for audio capture (default: from device) */
  sampleRate?: number;
  /** Frame rate for buffer size calculation (default: 30) */
  frameRate?: number;
  /** Number of frames to buffer (default: 2) */
  bufferFrames?: number;
  /** AudioWorklet processor URL (default: '/live2d/audioworklet-processor.js') */
  processorUrl?: string;
}

/**
 * MotionSync Audio Input
 * Captures real-time audio from microphone for use with CubismMotionSync
 */
export class MotionSyncAudioInput {
  private _context: AudioContext | null = null;
  private _source: MediaStreamAudioSourceNode | null = null;
  private _workletNode: AudioWorkletNode | null = null;
  private _buffer: AudioSampleBuffer;
  private _isInitialized: boolean = false;
  private _isCapturing: boolean = false;
  private _sampleRate: number = 48000;
  private _stream: MediaStream | null = null;
  private _options: Required<MotionSyncAudioInputOptions>;

  constructor(options: MotionSyncAudioInputOptions = {}) {
    this._options = {
      sampleRate: options.sampleRate || 0,
      frameRate: options.frameRate || 30,
      bufferFrames: options.bufferFrames || 2,
      processorUrl: options.processorUrl || '/live2d/audioworklet-processor.js',
    };

    // Initialize with a small default buffer (will be resized on init)
    this._buffer = new AudioSampleBuffer(4096);
  }

  get isInitialized(): boolean {
    return this._isInitialized;
  }

  get isCapturing(): boolean {
    return this._isCapturing;
  }

  get sampleRate(): number {
    return this._sampleRate;
  }

  /**
   * Initialize audio input with microphone access
   * @returns true if initialization successful
   */
  async initialize(): Promise<boolean> {
    if (this._isInitialized) {
      return true;
    }

    try {
      // Enumerate audio devices
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = devices.filter(device => device.kind === 'audioinput');

      if (audioInputs.length === 0) {
        log.error('No audio input devices found');
        return false;
      }

      // Request microphone access
      const constraints: MediaStreamConstraints = {
        audio: {
          deviceId: audioInputs[0].deviceId,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      };

      this._stream = await navigator.mediaDevices.getUserMedia(constraints);
      const tracks = this._stream.getAudioTracks();

      if (tracks.length === 0) {
        log.error('No audio tracks in stream');
        return false;
      }

      // Get sample rate from track settings
      const settings = tracks[0].getSettings();
      this._sampleRate = settings.sampleRate || this._options.sampleRate || 48000;

      // Calculate buffer size based on frame rate and sample rate
      const bufferSize = Math.trunc(
        (this._sampleRate / this._options.frameRate) * this._options.bufferFrames
      );
      this._buffer = new AudioSampleBuffer(bufferSize);

      // Create AudioContext
      this._context = new AudioContext({ sampleRate: this._sampleRate });
      this._source = this._context.createMediaStreamSource(
        new MediaStream([tracks[0]])
      );

      // Load AudioWorklet module
      await this._context.audioWorklet.addModule(this._options.processorUrl);

      // Create and connect AudioWorklet node
      this._workletNode = new AudioWorkletNode(
        this._context,
        'motionsync-audio-processor'
      );

      this._source.connect(this._workletNode);
      this._workletNode.connect(this._context.destination);

      // Handle messages from AudioWorklet
      this._workletNode.port.onmessage = this.onWorkletMessage.bind(this);

      this._isInitialized = true;
      this._isCapturing = true;

      log.info(`Initialized with sample rate: ${this._sampleRate}`);
      return true;
    } catch (error) {
      log.error('Initialization failed', error instanceof Error ? error : undefined, {
        error: error instanceof Error ? error.message : String(error),
      });
      return false;
    }
  }

  /**
   * Handle messages from AudioWorklet processor
   */
  private onWorkletMessage(event: MessageEvent): void {
    const data = event.data;
    if (data.eventType === 'data' && data.audioBuffer) {
      this._buffer.addSamples(data.audioBuffer);
    }
  }

  /**
   * Get current audio buffer as array
   * @returns Array of audio samples
   */
  getBuffer(): number[] {
    return this._buffer.toArray();
  }

  /**
   * Get current buffer size
   */
  getBufferSize(): number {
    return this._buffer.size;
  }

  /**
   * Clear the audio buffer
   */
  clearBuffer(): void {
    this._buffer.clear();
  }

  /**
   * Start audio capture (resume if suspended)
   */
  async start(): Promise<boolean> {
    if (!this._isInitialized) {
      const success = await this.initialize();
      if (!success) return false;
    }

    if (this._context?.state === 'suspended') {
      await this._context.resume();
    }

    this._isCapturing = true;
    return true;
  }

  /**
   * Stop audio capture (suspend context)
   */
  async stop(): Promise<void> {
    if (this._context && this._context.state === 'running') {
      await this._context.suspend();
    }
    this._isCapturing = false;
    this.clearBuffer();
  }

  /**
   * Release all resources
   */
  release(): void {
    if (this._workletNode) {
      this._workletNode.disconnect();
      this._workletNode = null;
    }

    if (this._source) {
      this._source.disconnect();
      this._source = null;
    }

    if (this._context) {
      this._context.close();
      this._context = null;
    }

    if (this._stream) {
      this._stream.getTracks().forEach(track => track.stop());
      this._stream = null;
    }

    this._isInitialized = false;
    this._isCapturing = false;
    this._buffer.clear();
  }
}

// Singleton instance for easy access
let instance: MotionSyncAudioInput | null = null;

export function getMotionSyncAudioInput(options?: MotionSyncAudioInputOptions): MotionSyncAudioInput {
  if (!instance) {
    instance = new MotionSyncAudioInput(options);
  }
  return instance;
}

export function releaseMotionSyncAudioInput(): void {
  if (instance) {
    instance.release();
    instance = null;
  }
}
