// @ts-nocheck
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */

import { CubismMatrix44 } from '@framework/math/cubismmatrix44';
import { CubismViewMatrix } from '@framework/math/cubismviewmatrix';

import * as LAppDefine from './lappdefine';
import { LAppDelegate } from './lappdelegate';
import { LAppPal } from './lapppal';
import { LAppSprite } from './lappsprite';
import { TextureInfo } from './lapptexturemanager';
import { TouchManager } from './touchmanager';
import { LAppSubdelegate } from './lappsubdelegate';

/**
 * 描画クラス。
 */
export class LAppView {
  /**
   * コンストラクタ
   */
  public constructor() {
    this._programId = null;
    this._back = null;
    this._gear = null;
    this._isDragging = false;

    // タッチ関係のイベント管理
    this._touchManager = new TouchManager();

    // デバイス座標からスクリーン座標に変換するための
    this._deviceToScreen = new CubismMatrix44();

    // 画面の表示の拡大縮小や移動の変換を行う行列
    this._viewMatrix = new CubismViewMatrix();
  }

  /**
   * 初期化する。
   */
  public initialize(subdelegate: LAppSubdelegate): void {
    this._subdelegate = subdelegate;
    const { width, height } = subdelegate.getCanvas();

    const ratio: number = width / height;
    const left: number = -ratio;
    const right: number = ratio;
    const bottom: number = LAppDefine.ViewLogicalLeft;
    const top: number = LAppDefine.ViewLogicalRight;

    this._viewMatrix.setScreenRect(left, right, bottom, top); // デバイスに対応する画面の範囲。 Xの左端、Xの右端、Yの下端、Yの上端
    this._viewMatrix.scale(LAppDefine.ViewScale, LAppDefine.ViewScale);

    this._deviceToScreen.loadIdentity();
    if (width > height) {
      const screenW: number = Math.abs(right - left);
      this._deviceToScreen.scaleRelative(screenW / width, -screenW / width);
    } else {
      const screenH: number = Math.abs(top - bottom);
      this._deviceToScreen.scaleRelative(screenH / height, -screenH / height);
    }
    this._deviceToScreen.translateRelative(-width * 0.5, -height * 0.5);

    // 表示範囲の設定
    this._viewMatrix.setMaxScale(LAppDefine.ViewMaxScale); // 限界拡張率
    this._viewMatrix.setMinScale(LAppDefine.ViewMinScale); // 限界縮小率

    // 表示できる最大範囲
    this._viewMatrix.setMaxScreenRect(
      LAppDefine.ViewLogicalMaxLeft,
      LAppDefine.ViewLogicalMaxRight,
      LAppDefine.ViewLogicalMaxBottom,
      LAppDefine.ViewLogicalMaxTop
    );
  }

  /**
   * 解放する
   */
  public release(): void {
    this._viewMatrix = null;
    this._touchManager = null;
    this._deviceToScreen = null;

    // 背景と歯車は無効化済み
    if (this._gear) {
      this._gear.release();
      this._gear = null;
    }

    if (this._back) {
      this._back.release();
      this._back = null;
    }

    this._subdelegate.getGlManager().getGl().deleteProgram(this._programId);
    this._programId = null;
  }

  /**
   * 描画する。
   */
  public render(): void {
    this._subdelegate.getGlManager().getGl().useProgram(this._programId);

    // 背景と歯車アイコンは描画しない（透明背景用）
    // if (this._back) {
    //   this._back.render(this._programId);
    // }
    // if (this._gear) {
    //   this._gear.render(this._programId);
    // }

    this._subdelegate.getGlManager().getGl().flush();

    const lapplive2dmanager = this._subdelegate.getLive2DManager();
    if (lapplive2dmanager != null) {
      lapplive2dmanager.setViewMatrix(this._viewMatrix);

      lapplive2dmanager.onUpdate();
    }
  }

  /**
   * 画像の初期化を行う。
   */
  public initializeSprite(): void {
    // 背景と歯車は透明背景モードでは不要のため、読み込みをスキップ
    // const width: number = this._subdelegate.getCanvas().width;
    // const height: number = this._subdelegate.getCanvas().height;
    // const textureManager = this._subdelegate.getTextureManager();
    // const resourcesPath = LAppDefine.ResourcesPath;

    // let imageName = '';

    // // 背景画像初期化
    // imageName = LAppDefine.BackImageName;

    // // 非同期なのでコールバック関数を作成
    // const initBackGroundTexture = (textureInfo: TextureInfo): void => {
    //   const x: number = width * 0.5;
    //   const y: number = height * 0.5;

    //   const fwidth = textureInfo.width * 2.0;
    //   const fheight = height * 0.95;
    //   this._back = new LAppSprite(x, y, fwidth, fheight, textureInfo.id);
    //   this._back.setSubdelegate(this._subdelegate);
    // };

    // textureManager.createTextureFromPngFile(
    //   resourcesPath + imageName,
    //   false,
    //   initBackGroundTexture
    // );

    // // 歯車画像初期化
    // imageName = LAppDefine.GearImageName;
    // const initGearTexture = (textureInfo: TextureInfo): void => {
    //   const x = width - textureInfo.width * 0.5;
    //   const y = height - textureInfo.height * 0.5;
    //   const fwidth = textureInfo.width;
    //   const fheight = textureInfo.height;
    //   this._gear = new LAppSprite(x, y, fwidth, fheight, textureInfo.id);
    //   this._gear.setSubdelegate(this._subdelegate);
    // };

    // textureManager.createTextureFromPngFile(
    //   resourcesPath + imageName,
    //   false,
    //   initGearTexture
    // );

    // シェーダーを作成
    if (this._programId == null) {
      this._programId = this._subdelegate.createShader();
    }
  }

  /**
   * タッチされた時に呼ばれる。
   *
   * @param pointX スクリーンX座標
   * @param pointY スクリーンY座標
   */
  public onTouchesBegan(pointX: number, pointY: number): void {
    this._touchManager.touchesBegan(
      pointX * window.devicePixelRatio,
      pointY * window.devicePixelRatio
    );
    this._isDragging = true;
  }

  /**
   * タッチしているときにポインタが動いたら呼ばれる。
   *
   * @param pointX スクリーンX座標
   * @param pointY スクリーンY座標
   */
  public onTouchesMoved(pointX: number, pointY: number): void {
    const posX = pointX * window.devicePixelRatio;
    const posY = pointY * window.devicePixelRatio;

    const lapplive2dmanager = this._subdelegate.getLive2DManager();

    // 前回位置を保存
    const prevX = this._touchManager.getX();
    const prevY = this._touchManager.getY();

    // タッチ位置を更新
    this._touchManager.touchesMoved(posX, posY);

    // 平移模型位置（ドラッグで移動）
    if (this._isDragging) {
      const deltaX = posX - prevX;
      const deltaY = posY - prevY;

      // スクリーン座標系での移動量を計算
      const screenDeltaX = this._deviceToScreen.transformX(deltaX) - this._deviceToScreen.transformX(0);
      const screenDeltaY = this._deviceToScreen.transformY(deltaY) - this._deviceToScreen.transformY(0);

      this._viewMatrix.adjustTranslate(screenDeltaX, screenDeltaY);
    } else {
      // 目の追従（元の動作）
      const viewX: number = this.transformViewX(prevX);
      const viewY: number = this.transformViewY(prevY);
      lapplive2dmanager.onDrag(viewX, viewY);
    }
  }

  /**
   * タッチが終了したら呼ばれる。
   *
   * @param pointX スクリーンX座標
   * @param pointY スクリーンY座標
   */
  public onTouchesEnded(pointX: number, pointY: number): void {
    const posX = pointX * window.devicePixelRatio;
    const posY = pointY * window.devicePixelRatio;

    const lapplive2dmanager = this._subdelegate.getLive2DManager();

    // ドラッグ終了
    this._isDragging = false;

    // タッチ終了
    lapplive2dmanager.onDrag(0.0, 0.0);

    // シングルタップ（移動距離が小さい場合のみ）
    const startX = this._touchManager.getStartX();
    const startY = this._touchManager.getStartY();
    const distance = Math.sqrt(Math.pow(posX - startX, 2) + Math.pow(posY - startY, 2));

    // 移動距離がタップ閾値以下ならタップとみなす（devicePixelRatio考慮）
    const tapThreshold = 15 * window.devicePixelRatio;
    if (distance < tapThreshold) {
      const x: number = this.transformViewX(posX);
      const y: number = this.transformViewY(posY);

      if (LAppDefine.DebugTouchLogEnable) {
        LAppPal.printMessage(`[APP]touchesEnded x: ${x} y: ${y}`);
      }
      lapplive2dmanager.onTap(x, y);
    }

    // 歯車にタップしたか（歯車は無効化済み）
    // if (this._gear && this._gear.isHit(posX, posY)) {
    //   lapplive2dmanager.nextScene();
    // }
  }

  /**
   * X座標をView座標に変換する。
   *
   * @param deviceX デバイスX座標
   */
  public transformViewX(deviceX: number): number {
    const screenX: number = this._deviceToScreen.transformX(deviceX); // 論理座標変換した座標を取得。
    return this._viewMatrix.invertTransformX(screenX); // 拡大、縮小、移動後の値。
  }

  /**
   * Y座標をView座標に変換する。
   *
   * @param deviceY デバイスY座標
   */
  public transformViewY(deviceY: number): number {
    const screenY: number = this._deviceToScreen.transformY(deviceY); // 論理座標変換した座標を取得。
    return this._viewMatrix.invertTransformY(screenY);
  }

  /**
   * X座標をScreen座標に変換する。
   * @param deviceX デバイスX座標
   */
  public transformScreenX(deviceX: number): number {
    return this._deviceToScreen.transformX(deviceX);
  }

  /**
   * Y座標をScreen座標に変換する。
   *
   * @param deviceY デバイスY座標
   */
  public transformScreenY(deviceY: number): number {
    return this._deviceToScreen.transformY(deviceY);
  }

  /**
   * マウスホイールでズームする
   *
   * @param delta ホイールのdelta値（正: ズームイン、負: ズームアウト）
   * @param centerX ズームの中心X座標
   * @param centerY ズームの中心Y座標
   */
  public onWheel(delta: number, centerX: number, centerY: number): void {
    const scaleFactor = delta > 0 ? 1.1 : 0.9;
    const currentScale = this._viewMatrix.getScaleX();
    const newScale = currentScale * scaleFactor;

    // Check scale limits
    const minScale = LAppDefine.ViewMinScale;
    const maxScale = LAppDefine.ViewMaxScale;

    if (newScale >= minScale && newScale <= maxScale) {
      // Get the point in view coordinates before scaling
      const screenX = this._deviceToScreen.transformX(centerX * window.devicePixelRatio);
      const screenY = this._deviceToScreen.transformY(centerY * window.devicePixelRatio);

      // Apply scale
      this._viewMatrix.adjustScale(screenX, screenY, scaleFactor);
    }
  }

  /**
   * ビューマトリックスの現在のスケールを取得
   */
  public getScale(): number {
    return this._viewMatrix.getScaleX();
  }

  _touchManager: TouchManager; // タッチマネージャー
  _deviceToScreen: CubismMatrix44; // デバイスからスクリーンへの行列
  _viewMatrix: CubismViewMatrix; // viewMatrix
  _programId: WebGLProgram; // シェーダID
  _back: LAppSprite; // 背景画像
  _gear: LAppSprite; // ギア画像
  _changeModel: boolean; // モデル切り替えフラグ
  _isClick: boolean; // クリック中
  _isDragging: boolean; // ドラッグ中フラグ
  private _subdelegate: LAppSubdelegate;
}
