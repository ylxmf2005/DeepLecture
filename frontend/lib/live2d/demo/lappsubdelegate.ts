// @ts-nocheck
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */

import { CubismFramework, Option } from '@framework/live2dcubismframework';

import * as LAppDefine from './lappdefine';
import { LAppGlManager } from './lappglmanager';
import { LAppLive2DManager } from './lapplive2dmanager';
import { LAppLipSyncManager, LipSyncSource } from './lapplipsyncmanager';
import { LAppPal } from './lapppal';
import { LAppTextureManager } from './lapptexturemanager';
import { LAppView } from './lappview';

let s_cubismInitialized = false;

/**
 * Canvasに関連する操作を取りまとめるクラス
 */
export class LAppSubdelegate {
  /**
   * コンストラクタ
   */
  public constructor() {
    this._canvas = null;
    this._glManager = new LAppGlManager();
    this._textureManager = new LAppTextureManager();
    this._live2dManager = new LAppLive2DManager();
    this._lipSyncManager = new LAppLipSyncManager();
    this._view = new LAppView();
    this._frameBuffer = null;
    this._captured = false;
    this._resizeDebounceTimer = null;
  }

  /**
   * デストラクタ相当の処理
   */
  public release(): void {
    if (this._resizeDebounceTimer !== null) {
      clearTimeout(this._resizeDebounceTimer);
      this._resizeDebounceTimer = null;
    }
    this._resizeObserver.unobserve(this._canvas);
    this._resizeObserver.disconnect();
    this._resizeObserver = null;

    this._lipSyncManager.release();
    this._lipSyncManager = null;

    this._live2dManager.release();
    this._live2dManager = null;

    this._view.release();
    this._view = null;

    this._textureManager.release();
    this._textureManager = null;

    this._glManager.release();
    this._glManager = null;
  }

  /**
   * APPに必要な物を初期化する。
   */
  public initialize(canvas: HTMLCanvasElement): boolean {
    if (!this._glManager.initialize(canvas)) {
      return false;
    }

    this._canvas = canvas;

    if (LAppDefine.CanvasSize === 'auto') {
      this.resizeCanvas();
    } else {
      canvas.width = LAppDefine.CanvasSize.width;
      canvas.height = LAppDefine.CanvasSize.height;
    }

    this._textureManager.setGlManager(this._glManager);

    const gl = this._glManager.getGl();

    if (!this._frameBuffer) {
      this._frameBuffer = gl.getParameter(gl.FRAMEBUFFER_BINDING);
    }

    // 透過設定
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    // Initialize Cubism Framework (only once)
    if (!s_cubismInitialized) {
      const cubismOption = new Option();
      cubismOption.logFunction = LAppPal.printMessage;
      cubismOption.loggingLevel = LAppDefine.CubismLoggingLevel;
      CubismFramework.startUp(cubismOption);
      CubismFramework.initialize();
      s_cubismInitialized = true;
      LAppPal.printMessage('[LAppSubdelegate] CubismFramework initialized');
    }

    // AppViewの初期化
    this._view.initialize(this);
    this._view.initializeSprite();

    this._live2dManager.initialize(this);

    this._resizeObserver = new ResizeObserver(
      (entries: ResizeObserverEntry[], observer: ResizeObserver) =>
        this.resizeObserverCallback.call(this, entries, observer)
    );
    this._resizeObserver.observe(this._canvas);

    return true;
  }

  /**
   * Resize canvas and re-initialize view.
   */
  public onResize(): void {
    // Only reinitialize if the canvas was actually resized
    if (this.resizeCanvas()) {
      this._view.initialize(this);
      this._view.initializeSprite();
    }
  }

  private resizeObserverCallback(
    entries: ResizeObserverEntry[],
    observer: ResizeObserver
  ): void {
    if (LAppDefine.CanvasSize === 'auto') {
      // Debounce resize to prevent flickering from rapid resize events
      if (this._resizeDebounceTimer !== null) {
        clearTimeout(this._resizeDebounceTimer);
      }
      this._resizeDebounceTimer = window.setTimeout(() => {
        this._needResize = true;
        this._resizeDebounceTimer = null;
      }, 100) as unknown as number;
    }
  }

  /**
   * ループ処理
   */
  public update(): void {
    if (this._glManager.getGl().isContextLost()) {
      return;
    }

    // Update time for animation
    LAppPal.updateTime();

    // キャンバスのサイズが変わっている場合はリサイズに必要な処理をする。
    if (this._needResize) {
      this.onResize();
      this._needResize = false;
    }

    // Update lip sync value from LipSyncManager
    if (this._lipSyncManager && this._lipSyncManager.isActive()) {
      const lipSyncValue = this._lipSyncManager.update();
      this._live2dManager.setLipSyncValue(lipSyncValue);
    }

    const gl = this._glManager.getGl();

    // 画面の初期化 - 透明背景
    gl.clearColor(0.0, 0.0, 0.0, 0.0);

    // 深度テストを有効化
    gl.enable(gl.DEPTH_TEST);

    // 近くにある物体は、遠くにある物体を覆い隠す
    gl.depthFunc(gl.LEQUAL);

    // Clear both buffers for transparent background
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.clearDepth(1.0);

    // 透過設定
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    // 描画更新
    this._view.render();
  }

  /**
   * シェーダーを登録する。
   */
  public createShader(): WebGLProgram {
    const gl = this._glManager.getGl();

    // バーテックスシェーダーのコンパイル
    const vertexShaderId = gl.createShader(gl.VERTEX_SHADER);

    if (vertexShaderId == null) {
      LAppPal.printMessage('failed to create vertexShader');
      return null;
    }

    const vertexShader: string =
      'precision mediump float;' +
      'attribute vec3 position;' +
      'attribute vec2 uv;' +
      'varying vec2 vuv;' +
      'void main(void)' +
      '{' +
      '   gl_Position = vec4(position, 1.0);' +
      '   vuv = uv;' +
      '}';

    gl.shaderSource(vertexShaderId, vertexShader);
    gl.compileShader(vertexShaderId);

    // フラグメントシェーダのコンパイル
    const fragmentShaderId = gl.createShader(gl.FRAGMENT_SHADER);

    if (fragmentShaderId == null) {
      LAppPal.printMessage('failed to create fragmentShader');
      return null;
    }

    const fragmentShader: string =
      'precision mediump float;' +
      'varying vec2 vuv;' +
      'uniform sampler2D texture;' +
      'void main(void)' +
      '{' +
      '   gl_FragColor = texture2D(texture, vuv);' +
      '}';

    gl.shaderSource(fragmentShaderId, fragmentShader);
    gl.compileShader(fragmentShaderId);

    // プログラムオブジェクトの作成
    const programId = gl.createProgram();
    gl.attachShader(programId, vertexShaderId);
    gl.attachShader(programId, fragmentShaderId);

    gl.deleteShader(vertexShaderId);
    gl.deleteShader(fragmentShaderId);

    // リンク
    gl.linkProgram(programId);
    gl.useProgram(programId);

    return programId;
  }

  public getTextureManager(): LAppTextureManager {
    return this._textureManager;
  }

  public getFrameBuffer(): WebGLFramebuffer {
    return this._frameBuffer;
  }

  public getCanvas(): HTMLCanvasElement {
    return this._canvas;
  }

  public getGlManager(): LAppGlManager {
    return this._glManager;
  }

  public getLive2DManager(): LAppLive2DManager {
    return this._live2dManager;
  }

  public getView(): LAppView {
    return this._view;
  }

  /**
   * Resize the canvas to fill the screen.
   * Returns true if the canvas was actually resized, false if dimensions unchanged.
   */
  private resizeCanvas(): boolean {
    const newWidth = this._canvas.clientWidth * window.devicePixelRatio;
    const newHeight = this._canvas.clientHeight * window.devicePixelRatio;

    // Skip resize if dimensions haven't changed
    if (this._canvas.width === newWidth && this._canvas.height === newHeight) {
      return false;
    }

    this._canvas.width = newWidth;
    this._canvas.height = newHeight;

    const gl = this._glManager.getGl();
    gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
    return true;
  }

  public onPointBeganLocal(localX: number, localY: number): void {
    if (!this._view) return;
    this._captured = true;
    this._view.onTouchesBegan(localX, localY);
  }

  public onPointMovedLocal(localX: number, localY: number): void {
    if (!this._captured) return;
    this._view.onTouchesMoved(localX, localY);
  }

  public onPointEndedLocal(localX: number, localY: number): void {
    this._captured = false;
    if (!this._view) return;
    this._view.onTouchesEnded(localX, localY);
  }

  public isContextLost(): boolean {
    return this._glManager.getGl().isContextLost();
  }

  /**
   * マウスホイールイベント処理
   */
  public onWheel(deltaY: number, localX: number, localY: number): void {
    if (!this._view) {
      return;
    }
    // deltaY is inverted: negative = scroll up = zoom in
    const delta = -deltaY > 0 ? 1 : -1;
    this._view.onWheel(delta, localX, localY);
  }

  /**
   * 現在のスケールを取得
   */
  public getScale(): number {
    if (!this._view) {
      return 1.0;
    }
    return this._view.getScale();
  }

  /**
   * 指定した表情をセットする
   * @param expressionId 表情ID
   */
  public setExpression(expressionId: string): void {
    this._live2dManager.setExpression(expressionId);
  }

  /**
   * ランダムな表情をセットする
   */
  public setRandomExpression(): void {
    this._live2dManager.setRandomExpression();
  }

  /**
   * 指定したモーションを再生する
   * @param group モーショングループ名
   * @param index モーションのインデックス
   * @param priority 優先度 (1: Idle, 2: Normal, 3: Force)
   */
  public startMotion(group: string, index: number, priority: number = 2): void {
    this._live2dManager.startMotion(group, index, priority);
  }

  /**
   * 指定グループからランダムにモーションを再生する
   * @param group モーショングループ名
   * @param priority 優先度
   */
  public startRandomMotion(group: string, priority: number = 2): void {
    this._live2dManager.startRandomMotion(group, priority);
  }

  /**
   * 利用可能な表情名のリストを取得
   */
  public getExpressionNames(): string[] {
    return this._live2dManager.getExpressionNames();
  }

  /**
   * 利用可能なモーショングループのリストを取得
   */
  public getMotionGroups(): { group: string; count: number }[] {
    return this._live2dManager.getMotionGroups();
  }

  /**
   * モデル情報を取得
   */
  public getModelInfo(): { expressions: string[]; motions: { group: string; count: number }[] } {
    return {
      expressions: this.getExpressionNames(),
      motions: this.getMotionGroups()
    };
  }

  /**
   * Play audio from URL with lip sync
   * @param url Audio file URL
   * @returns Promise that resolves when playback starts
   */
  public async playAudioWithLipSync(url: string): Promise<void> {
    this._live2dManager.enableExternalLipSync();
    return this._lipSyncManager.playAudioUrl(url);
  }

  /**
   * Connect a media element (audio or video) for lip sync
   * @param mediaElement HTMLMediaElement to connect
   */
  public async connectAudioForLipSync(mediaElement: HTMLMediaElement): Promise<void> {
    this._live2dManager.enableExternalLipSync();
    return this._lipSyncManager.connectAudioElement(mediaElement);
  }

  /**
   * Start microphone input for real-time lip sync
   */
  public async startMicrophoneLipSync(): Promise<void> {
    this._live2dManager.enableExternalLipSync();
    return this._lipSyncManager.startMicrophone();
  }

  /**
   * Stop lip sync
   */
  public async stopLipSync(): Promise<void> {
    await this._lipSyncManager.stopLipSync();
    this._live2dManager.disableExternalLipSync();
  }

  /**
   * Pause lip sync audio playback
   */
  public pauseLipSync(): void {
    this._lipSyncManager.pause();
  }

  /**
   * Resume lip sync audio playback
   */
  public resumeLipSync(): void {
    this._lipSyncManager.resume();
  }

  /**
   * Check if lip sync is active
   */
  public isLipSyncActive(): boolean {
    return this._lipSyncManager.isActive();
  }

  /**
   * Get current lip sync source type
   */
  public getLipSyncSource(): LipSyncSource {
    return this._lipSyncManager.getSource();
  }

  /**
   * Set lip sync smoothing (0-1)
   */
  public setLipSyncSmoothing(value: number): void {
    this._lipSyncManager.setSmoothing(value);
  }

  /**
   * Set lip sync gain multiplier
   */
  public setLipSyncGain(value: number): void {
    this._lipSyncManager.setGain(value);
  }

  /**
   * Set lip sync value directly (0-1)
   */
  public setLipSyncValue(value: number): void {
    this._live2dManager.enableExternalLipSync();
    this._live2dManager.setLipSyncValue(value);
  }

  /**
   * Set callback for when audio ends
   */
  public setOnLipSyncAudioEnded(callback: (() => void) | null): void {
    this._lipSyncManager.setOnAudioEnded(callback);
  }

  /**
   * Get current lip sync value
   */
  public getLipSyncValue(): number {
    return this._live2dManager.getLipSyncValue();
  }

  private _canvas: HTMLCanvasElement;

  /**
   * View情報
   */
  private _view: LAppView;

  /**
   * テクスチャマネージャー
   */
  private _textureManager: LAppTextureManager;
  private _frameBuffer: WebGLFramebuffer;
  private _glManager: LAppGlManager;
  private _live2dManager: LAppLive2DManager;
  private _lipSyncManager: LAppLipSyncManager;

  /**
   * ResizeObserver
   */
  private _resizeObserver: ResizeObserver;

  /**
   * クリックしているか
   */
  private _captured: boolean;

  private _needResize: boolean;
  private _resizeDebounceTimer: number | null;
}
