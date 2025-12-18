// @ts-nocheck
/**
 * Live2D Manager - Manages Live2D model loading, rendering and interaction
 * Adapted for Next.js + React environment
 */

import { CubismFramework, Option, LogLevel } from './live2dcubismframework';
import { CubismMatrix44 } from './math/cubismmatrix44';
import { CubismViewMatrix } from './math/cubismviewmatrix';

// Global configuration
export interface Live2DConfig {
  resourcesPath: string;
  modelName: string;
  canvasId: string;
  width?: number;
  height?: number;
  scale?: number;
  debug?: boolean;
}

// Default configuration
const defaultConfig: Partial<Live2DConfig> = {
  resourcesPath: '/live2d/models/',
  width: 800,
  height: 600,
  scale: 1.0,
  debug: false,
};

/**
 * Live2D Manager Singleton Class
 */
export class Live2DManager {
  private static _instance: Live2DManager | null = null;
  private _initialized: boolean = false;
  private _canvas: HTMLCanvasElement | null = null;
  private _gl: WebGLRenderingContext | null = null;
  private _config: Live2DConfig | null = null;
  private _animationFrameId: number | null = null;
  private _viewMatrix: CubismViewMatrix | null = null;
  private _projectionMatrix: CubismMatrix44 | null = null;

  // Model position and scale
  private _modelX: number = 0;
  private _modelY: number = 0;
  private _modelScale: number = 1.0;

  private constructor() {}

  public static getInstance(): Live2DManager {
    if (!Live2DManager._instance) {
      Live2DManager._instance = new Live2DManager();
    }
    return Live2DManager._instance;
  }

  public static releaseInstance(): void {
    if (Live2DManager._instance) {
      Live2DManager._instance.release();
      Live2DManager._instance = null;
    }
  }

  /**
   * Initialize Live2D Framework
   */
  public async initialize(config: Live2DConfig): Promise<boolean> {
    if (this._initialized) {
      console.warn('Live2D Manager already initialized');
      return true;
    }

    this._config = { ...defaultConfig, ...config };

    // Get canvas
    this._canvas = document.getElementById(config.canvasId) as HTMLCanvasElement;
    if (!this._canvas) {
      console.error(`Canvas with id "${config.canvasId}" not found`);
      return false;
    }

    // Set canvas dimensions
    this._canvas.width = this._config.width!;
    this._canvas.height = this._config.height!;

    // Initialize WebGL
    this._gl = this._canvas.getContext('webgl') || this._canvas.getContext('experimental-webgl') as WebGLRenderingContext;
    if (!this._gl) {
      console.error('WebGL not supported');
      return false;
    }

    // Initialize Cubism Framework
    const cubismOption = new Option();
    cubismOption.logFunction = (message: string) => {
      if (this._config?.debug) {
        console.log(`[Live2D] ${message}`);
      }
    };
    cubismOption.loggingLevel = this._config.debug ? LogLevel.LogLevel_Verbose : LogLevel.LogLevel_Off;

    if (!CubismFramework.startUp(cubismOption)) {
      console.error('Failed to start Cubism Framework');
      return false;
    }

    CubismFramework.initialize();

    // Initialize view matrix
    this._viewMatrix = new CubismViewMatrix();
    this._projectionMatrix = new CubismMatrix44();

    this._initialized = true;
    console.log('Live2D Manager initialized successfully');

    return true;
  }

  /**
   * Release resources
   */
  public release(): void {
    if (this._animationFrameId !== null) {
      cancelAnimationFrame(this._animationFrameId);
      this._animationFrameId = null;
    }

    if (this._initialized) {
      CubismFramework.dispose();
    }

    this._canvas = null;
    this._gl = null;
    this._config = null;
    this._viewMatrix = null;
    this._projectionMatrix = null;
    this._initialized = false;
  }

  /**
   * Set model position
   */
  public setModelPosition(x: number, y: number): void {
    this._modelX = x;
    this._modelY = y;
  }

  /**
   * Set model scale
   */
  public setModelScale(scale: number): void {
    this._modelScale = Math.max(0.1, Math.min(5.0, scale));
  }

  /**
   * Get current configuration
   */
  public getConfig(): Live2DConfig | null {
    return this._config;
  }

  /**
   * Check if initialized
   */
  public isInitialized(): boolean {
    return this._initialized;
  }

  /**
   * Get WebGL context
   */
  public getGL(): WebGLRenderingContext | null {
    return this._gl;
  }

  /**
   * Get Canvas
   */
  public getCanvas(): HTMLCanvasElement | null {
    return this._canvas;
  }
}

export default Live2DManager;
