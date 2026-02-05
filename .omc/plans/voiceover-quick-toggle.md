# 配音轨道快速切换功能实现计划

## 需求概要

将视频播放器上的双向箭头按钮从"切换字幕"改为"切换配音轨道"，并支持 Auto-leave 时自动切换配音。

## 核心需求

1. **预设轨道设置**：在 ActionsDialog 中设置 Original 和 Translated 两个预设轨道
   - Original：可以是视频原声（null）或某个配音
   - Translated：必须是某个已生成的配音

2. **快速切换按钮**：在两个预设之间切换配音
   - 如果未设置 Translated 轨道，点击时显示提示

3. **Auto-leave 集成**：离开页面时自动切换到 Translated 配音，返回时恢复

## 实现步骤

### Phase 1: 状态层 (stores)

#### 1.1 修改 `frontend/stores/types.ts`
```typescript
// 在 VideoState 接口中添加：
interface VideoState {
  // ... existing fields
  originalVoiceoverId: string | null;    // null = 视频原声, string = 配音ID
  translatedVoiceoverId: string | null;  // null = 未设置, string = 配音ID
}

// 添加默认值到 DEFAULT_VIDEO_STATE
```

#### 1.2 修改 `frontend/stores/useVideoStateStore.ts`
- 添加 `setOriginalVoiceoverId(videoId, id)` action
- 添加 `setTranslatedVoiceoverId(videoId, id)` action
- 添加 selector hooks: `useOriginalVoiceoverId`, `useTranslatedVoiceoverId`

### Phase 2: UI 层 - ActionsDialog

#### 2.1 修改 `frontend/components/dialogs/ActionsDialog.tsx`
- 在 "Select Audio Track" 区域下方添加新的设置区域
- UI 设计：

```
┌─────────────────────────────────────────┐
│  Quick Toggle Presets                    │
│  ┌─────────────────────────────────────┐ │
│  │ Original Track:  [Dropdown ▼]       │ │
│  │   • Video Original                  │ │
│  │   • Chinese Voiceover #1            │ │
│  └─────────────────────────────────────┘ │
│  ┌─────────────────────────────────────┐ │
│  │ Translated Track: [Dropdown ▼]      │ │
│  │   • Chinese Voiceover #2            │ │
│  │   • (Not set)                       │ │
│  └─────────────────────────────────────┘ │
│  ℹ️ Use the toggle button on video to   │
│     quickly switch between these tracks │
└─────────────────────────────────────────┘
```

### Phase 3: 播放器层 - VideoPlayer

#### 3.1 修改 `frontend/components/video/VideoPlayer.tsx`
- 修改 props：移除字幕相关的快速切换 props，添加配音切换 props
- 修改 `handleQuickToggle` 逻辑：
  ```typescript
  const handleQuickToggle = useCallback(() => {
    if (translatedVoiceoverId === null) {
      toast.info("Please set up quick toggle presets in Actions dialog");
      return;
    }

    // 判断当前是哪个轨道，切换到另一个
    const currentIsOriginal = selectedVoiceoverId === originalVoiceoverId;
    const newId = currentIsOriginal ? translatedVoiceoverId : originalVoiceoverId;
    onVoiceoverChange(newId);
  }, [...]);
  ```

#### 3.2 修改按钮显示条件
- 始终显示按钮（只要有配音功能）
- 未设置时点击显示提示

#### 3.3 更新按钮 tooltip
- 显示当前轨道状态：`"Toggle audio track - Currently: Original"` 或 `"Toggle audio track - Currently: Translated"`

### Phase 4: 数据流层

#### 4.1 修改 `frontend/components/video/VideoPlayerSection.tsx`
- 传递新的 props 到 VideoPlayer

#### 4.2 修改 `frontend/app/video/[id]/VideoPageClient.tsx`
- 从 store 获取 originalVoiceoverId 和 translatedVoiceoverId
- 传递给 VideoPlayerSection

### Phase 5: Auto-leave 集成

#### 5.1 创建 `frontend/lib/voiceoverAutoSwitch.ts`
- 类似 `subtitleAutoSwitch.ts` 的纯函数模块
- 函数：
  - `getAutoSwitchVoiceoverOnHide(ctx)`: 返回应切换到的配音ID或null
  - `getAutoSwitchVoiceoverOnShow(ctx)`: 返回应恢复的配音ID或null

#### 5.2 修改 `frontend/components/features/FocusModeHandler.tsx`
- 添加配音自动切换逻辑
- 新增 props：
  ```typescript
  // Voiceover auto-switch
  autoSwitchVoiceoverOnLeave?: boolean;
  selectedVoiceoverId: string | null;
  originalVoiceoverId: string | null;
  translatedVoiceoverId: string | null;
  onVoiceoverChange: (id: string | null) => void;
  ```

#### 5.3 添加设置项
- 在 GlobalSettingsStore 中添加 `autoSwitchVoiceoverOnLeave` 设置
- 在设置 UI 中添加开关

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `stores/types.ts` | 修改 | 添加新状态字段 |
| `stores/useVideoStateStore.ts` | 修改 | 添加 actions 和 selectors |
| `components/dialogs/ActionsDialog.tsx` | 修改 | 添加预设设置 UI |
| `components/video/VideoPlayer.tsx` | 修改 | 修改快速切换逻辑 |
| `components/video/VideoPlayerSection.tsx` | 修改 | 传递新 props |
| `app/video/[id]/VideoPageClient.tsx` | 修改 | 连接状态 |
| `lib/voiceoverAutoSwitch.ts` | 新建 | 配音自动切换纯函数 |
| `components/features/FocusModeHandler.tsx` | 修改 | 添加配音自动切换 |
| `stores/useGlobalSettingsStore.ts` | 修改 | 添加设置项（可选） |

## 测试要点

1. **快速切换**：
   - [ ] 设置好两个预设后，点击按钮能正确切换
   - [ ] 未设置 Translated 时点击显示提示
   - [ ] 切换后音频正确播放

2. **Auto-leave**：
   - [ ] 离开页面时切换到 Translated 配音
   - [ ] 返回页面时恢复到 Original 配音
   - [ ] 用户手动切换后不自动恢复

3. **持久化**：
   - [ ] 预设设置在刷新后保持
   - [ ] 每个视频独立存储

## 依赖关系

```
Phase 1 (状态层)
    ↓
Phase 2 (ActionsDialog) ←→ Phase 3 (VideoPlayer)
    ↓                           ↓
Phase 4 (数据流连接)
    ↓
Phase 5 (Auto-leave)
```

## 预估工作量

- Phase 1: ~30 LOC
- Phase 2: ~80 LOC
- Phase 3: ~40 LOC
- Phase 4: ~20 LOC
- Phase 5: ~100 LOC (新模块 + 集成)

**总计**: ~270 LOC
