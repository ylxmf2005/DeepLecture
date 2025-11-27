// @ts-nocheck
/**
 * Live2D Manager - 管理 Live2D 模型的加载、渲染和交互
 * 适配 Next.js + React 环境
 */

import { CubismFramework, Option, LogLevel } from './live2dcubismframework';
import { CubismMatrix44 } from './math/cubismmatrix44';
import { CubismViewMatrix } from './math/cubismviewmatrix';

// 全局配置
export interface Live2DConfig {
  resourcesPath: string;
  modelName: string;
  canvasId: string;
  width?: number;
  height?: number;
  scale?: number;
  debug?: boolean;
}

// 默认配置
const defaultConfig: Partial<Live2DConfig> = {
  resourcesPath: '/live2d/models/',
  width: 800,
  height: 600,
  scale: 1.0,
  debug: false,
};

/**
 * Live2D 管理器单例类
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

  // 模型位置和缩放
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
   * 初始化 Live2D 框架
   */
  public async initialize(config: Live2DConfig): Promise<boolean> {
    if (this._initialized) {
      console.warn('Live2D Manager already initialized');
      return true;
    }

    this._config = { ...defaultConfig, ...config };

    // 获取 canvas
    this._canvas = document.getElementById(config.canvasId) as HTMLCanvasElement;
    if (!this._canvas) {
      console.error(`Canvas with id "${config.canvasId}" not found`);
      return false;
    }

    // 设置 canvas 尺寸
    this._canvas.width = this._config.width!;
    this._canvas.height = this._config.height!;

    // 初始化 WebGL
    this._gl = this._canvas.getContext('webgl') || this._canvas.getContext('experimental-webgl') as WebGLRenderingContext;
    if (!this._gl) {
      console.error('WebGL not supported');
      return false;
    }

    // 初始化 Cubism Framework
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

    // 初始化视图矩阵
    this._viewMatrix = new CubismViewMatrix();
    this._projectionMatrix = new CubismMatrix44();

    this._initialized = true;
    console.log('Live2D Manager initialized successfully');

    return true;
  }

  /**
   * 释放资源
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
   * 设置模型位置
   */
  public setModelPosition(x: number, y: number): void {
    this._modelX = x;
    this._modelY = y;
  }

  /**
   * 设置模型缩放
   */
  public setModelScale(scale: number): void {
    this._modelScale = Math.max(0.1, Math.min(5.0, scale));
  }

  /**
   * 获取当前配置
   */
  public getConfig(): Live2DConfig | null {
    return this._config;
  }

  /**
   * 检查是否已初始化
   */
  public isInitialized(): boolean {
    return this._initialized;
  }

  /**
   * 获取 WebGL 上下文
   */
  public getGL(): WebGLRenderingContext | null {
    return this._gl;
  }

  /**
   * 获取 Canvas
   */
  public getCanvas(): HTMLCanvasElement | null {
    return this._canvas;
  }
}

export default Live2DManager;
