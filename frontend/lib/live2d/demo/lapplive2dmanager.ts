// @ts-nocheck
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */

import { CubismMatrix44 } from '@framework/math/cubismmatrix44';
import { ACubismMotion } from '@framework/motion/acubismmotion';
import { csmVector } from '@framework/type/csmvector';

import * as LAppDefine from './lappdefine';
import { LAppModel } from './lappmodel';
import { LAppPal } from './lapppal';
import { LAppSubdelegate } from './lappsubdelegate';

/**
 * サンプルアプリケーションにおいてCubismModelを管理するクラス
 * モデル生成と破棄、タップイベントの処理、モデル切り替えを行う。
 */
export class LAppLive2DManager {
  /**
   * 現在のシーンで保持しているすべてのモデルを解放する
   */
  private releaseAllModel(): void {
    this._models.clear();
  }

  /**
   * 画面をドラッグした時の処理
   *
   * @param x 画面のX座標
   * @param y 画面のY座標
   */
  public onDrag(x: number, y: number): void {
    const model: LAppModel = this._models.at(0);
    if (model) {
      model.setDragging(x, y);
    }
  }

  /**
   * 画面をタップした時の処理
   *
   * @param x 画面のX座標
   * @param y 画面のY座標
   */
  public onTap(x: number, y: number): void {
    if (LAppDefine.DebugLogEnable) {
      LAppPal.printMessage(
        `[APP]tap point: {x: ${x.toFixed(2)} y: ${y.toFixed(2)}}`
      );
    }

    const model: LAppModel = this._models.at(0);

    if (model.hitTest(LAppDefine.HitAreaNameHead, x, y)) {
      if (LAppDefine.DebugLogEnable) {
        LAppPal.printMessage(`[APP]hit area: [${LAppDefine.HitAreaNameHead}]`);
      }
      model.setRandomExpression();
    } else if (model.hitTest(LAppDefine.HitAreaNameBody, x, y)) {
      if (LAppDefine.DebugLogEnable) {
        LAppPal.printMessage(`[APP]hit area: [${LAppDefine.HitAreaNameBody}]`);
      }
      model.startRandomMotion(
        LAppDefine.MotionGroupTapBody,
        LAppDefine.PriorityNormal,
        this.finishedMotion,
        this.beganMotion
      );
    }
  }

  /**
   * 画面を更新するときの処理
   * モデルの更新処理及び描画処理を行う
   */
  public onUpdate(): void {
    const { width, height } = this._subdelegate.getCanvas();

    const projection: CubismMatrix44 = new CubismMatrix44();
    const model: LAppModel = this._models.at(0);

    if (model.getModel()) {
      if (model.getModel().getCanvasWidth() > 1.0 && width < height) {
        // 横に長いモデルを縦長ウィンドウに表示する際モデルの横サイズでscaleを算出する
        model.getModelMatrix().setWidth(2.0);
        projection.scale(1.0, width / height);
      } else {
        projection.scale(height / width, 1.0);
      }

      // 必要があればここで乗算
      if (this._viewMatrix != null) {
        projection.multiplyByMatrix(this._viewMatrix);
      }
    }

    model.update();
    model.draw(projection); // 参照渡しなのでprojectionは変質する。
  }

  /**
   * 次のシーンに切りかえる
   * サンプルアプリケーションではモデルセットの切り替えを行う。
   */
  public nextScene(): void {
    const no: number = (this._sceneIndex + 1) % LAppDefine.ModelDirSize;
    this.changeScene(no);
  }

  /**
   * シーンを切り替える
   * サンプルアプリケーションではモデルセットの切り替えを行う。
   * @param index
   */
  private changeScene(index: number): void {
    this._sceneIndex = index;

    if (LAppDefine.DebugLogEnable) {
      LAppPal.printMessage(`[APP]model index: ${this._sceneIndex}`);
    }

    // ModelDir[]に保持したディレクトリ名から
    // model3.jsonのパスを決定する。
    // ディレクトリ名とmodel3.jsonの名前を一致させておくこと。
    const model: string = LAppDefine.ModelDir[index];
    const modelPath: string = LAppDefine.ResourcesPath + model + '/';
    let modelJsonName: string = LAppDefine.ModelDir[index];
    modelJsonName += '.model3.json';

    this.releaseAllModel();
    const instance = new LAppModel();
    instance.setSubdelegate(this._subdelegate);
    instance.loadAssets(modelPath, modelJsonName);
    this._models.pushBack(instance);
  }

  public setViewMatrix(m: CubismMatrix44) {
    for (let i = 0; i < 16; i++) {
      this._viewMatrix.getArray()[i] = m.getArray()[i];
    }
  }

  /**
   * モデルの追加
   */
  public addModel(sceneIndex: number = 0): void {
    this._sceneIndex = sceneIndex;
    this.changeScene(this._sceneIndex);
  }

  /**
   * 指定したインデックスのモデルを取得
   * @param index モデルのインデックス
   */
  public getModel(index: number): LAppModel | null {
    if (index < 0 || index >= this._models.getSize()) {
      return null;
    }
    return this._models.at(index);
  }

  /**
   * 指定したパスからモデルを読み込む
   * @param modelPath モデルディレクトリのパス (末尾に/を含む)
   * @param modelFileName モデルファイル名 (.model3.json)
   */
  public loadModelByPath(modelPath: string, modelFileName: string): void {
    if (LAppDefine.DebugLogEnable) {
      LAppPal.printMessage(`[APP]Loading model: ${modelPath}${modelFileName}`);
    }

    this.releaseAllModel();
    const instance = new LAppModel();
    instance.setSubdelegate(this._subdelegate);
    instance.loadAssets(modelPath, modelFileName);
    this._models.pushBack(instance);
  }

  /**
   * モデルがMotionSync対応かを判定
   * @param modelName モデル名
   */
  public isMotionSyncModel(modelName: string): boolean {
    return LAppDefine.MotionSyncModelDir.includes(modelName);
  }

  /**
   * コンストラクタ
   */
  public constructor() {
    this._subdelegate = null;
    this._viewMatrix = new CubismMatrix44();
    this._models = new csmVector<LAppModel>();
    this._sceneIndex = 0;
  }

  /**
   * 解放する。
   */
  public release(): void {}

  /**
   * 初期化する。
   * @param subdelegate
   * @param autoLoadModel 自動でデフォルトモデルを読み込むかどうか (default: false)
   */
  public initialize(subdelegate: LAppSubdelegate, autoLoadModel: boolean = false): void {
    this._subdelegate = subdelegate;
    if (autoLoadModel) {
      this.changeScene(this._sceneIndex);
    }
  }

  /**
   * 自身が所属するSubdelegate
   */
  private _subdelegate: LAppSubdelegate;

  _viewMatrix: CubismMatrix44; // モデル描画に用いるview行列
  _models: csmVector<LAppModel>; // モデルインスタンスのコンテナ
  private _sceneIndex: number; // 表示するシーンのインデックス値

  /**
   * 指定した表情をセットする
   * @param expressionId 表情ID
   */
  public setExpression(expressionId: string): void {
    const model: LAppModel = this._models.at(0);
    if (model) {
      model.setExpression(expressionId);
    }
  }

  /**
   * ランダムな表情をセットする
   */
  public setRandomExpression(): void {
    const model: LAppModel = this._models.at(0);
    if (model) {
      model.setRandomExpression();
    }
  }

  /**
   * 指定したモーションを再生する
   * @param group モーショングループ名
   * @param index モーションのインデックス
   * @param priority 優先度 (1: Idle, 2: Normal, 3: Force)
   */
  public startMotion(group: string, index: number, priority: number = 2): void {
    const model: LAppModel = this._models.at(0);
    if (model) {
      model.startMotion(group, index, priority, this.finishedMotion, this.beganMotion);
    }
  }

  /**
   * 指定グループからランダムにモーションを再生する
   * @param group モーショングループ名
   * @param priority 優先度
   */
  public startRandomMotion(group: string, priority: number = 2): void {
    const model: LAppModel = this._models.at(0);
    if (model) {
      model.startRandomMotion(group, priority, this.finishedMotion, this.beganMotion);
    }
  }

  /**
   * 利用可能な表情名のリストを取得
   */
  public getExpressionNames(): string[] {
    const model: LAppModel = this._models.at(0);
    if (model) {
      return model.getExpressionNames();
    }
    return [];
  }

  /**
   * 利用可能なモーショングループのリストを取得
   */
  public getMotionGroups(): { group: string; count: number }[] {
    const model: LAppModel = this._models.at(0);
    if (model) {
      return model.getMotionGroups();
    }
    return [];
  }

  // モーション再生開始のコールバック関数
  beganMotion = (self: ACubismMotion): void => {
    LAppPal.printMessage('Motion Began:');
    console.log(self);
  };
  // モーション再生終了のコールバック関数
  finishedMotion = (self: ACubismMotion): void => {
    LAppPal.printMessage('Motion Finished:');
    console.log(self);
  };

  /**
   * Set lip sync value directly (for external audio analysis)
   * @param value Lip sync value (0-1)
   */
  public setLipSyncValue(value: number): void {
    const model: LAppModel = this._models.at(0);
    if (model) {
      model.setLipSyncValue(value);
    }
  }

  /**
   * Enable external lip sync mode
   */
  public enableExternalLipSync(): void {
    const model: LAppModel = this._models.at(0);
    if (model) {
      model.enableExternalLipSync();
    }
  }

  /**
   * Disable external lip sync
   */
  public disableExternalLipSync(): void {
    const model: LAppModel = this._models.at(0);
    if (model) {
      model.disableExternalLipSync();
    }
  }

  /**
   * Check if external lip sync is enabled
   */
  public isExternalLipSyncEnabled(): boolean {
    const model: LAppModel = this._models.at(0);
    if (model) {
      return model.isExternalLipSyncEnabled();
    }
    return false;
  }

  /**
   * Get current lip sync value
   */
  public getLipSyncValue(): number {
    const model: LAppModel = this._models.at(0);
    if (model) {
      return model.getLipSyncValue();
    }
    return 0;
  }
}
