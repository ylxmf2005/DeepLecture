# DeepLecture

> **用 AI 解锁视频学习的全部潜力**

**DeepLecture** 是一个开源的、AI 原生的视频学习平台，旨在弥合内容与理解之间的鸿沟。



## 功能

| 痛点 | 解决方案 | Demo |
|------|----------|------|
| 语速太快、口音劝退、想要双语对照但没有 | **双语字幕**：自动转录并翻译，同时显示原文和译文，点击字幕跳转 | [🎬 查看演示](docs/demo/dual-subtitle.md) |
| 图表/公式看不懂，暂停去问 ChatGPT 打断心流 | **截图解释**：截图后 AI 结合前后字幕帮你解释，自动保存方便复习 | [🎬 查看演示](docs/demo/screenshot-explanation.md) |
| 视频太长找不到重点，快进又怕错过内容 | **时间线节点**：AI 自动拆成知识点片段，生成可点击的时间线 | [🎬 查看演示](docs/demo/timeline.md) |
| 老师废话太多，听了半天都是自己会的 | **智能跳过**：自动快进闲聊、重复内容，只在重点正常播放 | [🎬 查看演示](docs/demo/smart-skip.md) |
| 摸鱼过头不知道讲了啥，回退又开始摸鱼 | **专注模式**：可选自动暂停，或者回来后 AI 帮你总结错过的内容 | [🎬 查看演示](docs/demo/focus-mode.md) |
| 没听懂想问，切到 ChatGPT 又要复述上下文 | **AI 问答**：任何地方一键「问 AI」，AI 结合上下文回答 | [🎬 查看演示](docs/demo/ai-qa.md) |
| 笔记散落在 Notion/Obsidian，复习时找不到对应视频位置 | **笔记**：任何内容一键「添加到笔记」，WYSIWYG + KaTeX，边看边记 | [🎬 查看演示](docs/demo/notes.md) |
| 外语听着累、老师声音难听、语速忽快忽慢 | **AI 配音** ⭐：用你喜欢的声音配音，只需等 TTS 完成，播放时自动对齐（老师啰嗦会加速视频哦） | [🎬 查看演示](docs/demo/ai-voiceover.md) |
| 只有课件没有讲解，自己又看不下去 | **课件生成视频** ⭐：上传 PDF，AI 自动生成讲解脚本和配音 | [🎬 查看演示](docs/demo/slide-lecture.md) |
| 学习太枯燥 | **Live2D 陪伴**：屏幕上显示 Live2D 模型，嘴型与音频同步 | [🎬 查看演示](docs/demo/live2d.md) |

## 跨平台支持

DeepLecture 支持所有主流操作系统：

| 平台 | 推荐引擎 | 特点 |
|------|---------|------|
| **macOS** | Whisper.cpp | Metal GPU 加速，自动编译和下载模型 |
| **Windows** | Faster-whisper | 无需编译，支持 CUDA 加速 |
| **Linux** | 两者皆可 | *未测试 |

> 选定引擎后，系统会自动检测硬件（Metal/CUDA/CPU）并优化运行参数。

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- FFmpeg（用于音视频处理）
- Git

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/DeepLecture.git
cd DeepLecture
```

### 2. 安装依赖

**后端**：
```bash
uv sync

# Windows 用户需要额外安装 faster-whisper
uv sync --extra faster-whisper
```

**前端**：
```bash
cd frontend && npm install && cd ..
```

### 3. 配置

复制默认配置文件：

```bash
cp config/conf.default.yaml config/conf.yaml
```

编辑 `config/conf.yaml`，参考注释配置（LLM 为必须配置项）。

### 4. 启动服务

**启动后端**（端口 11393）：
```bash
uv run deeplecture
```

**启动前端**（新终端，端口 3000）：

```bash
cd frontend && npm run dev
```

访问 http://localhost:3000 开始使用。

> **注意**：首次使用字幕功能时，系统会自动下载 Whisper 模型（large-v3-turbo 约 1.5GB），请耐心等待。

## Roadmap

我们正在积极开发以下功能，欢迎贡献代码或提出建议！

### 🔴 高优先级

- [ ] `Feature:` **内容导出** - 字幕导出 (SRT/VTT)、嵌入字幕的视频导出
- [ ] `DevOps:` **Docker 部署** - 一键部署、GPU passthrough 支持
- [ ] `Enhancement:` **笔记生成优化** - 更智能的 AI 笔记生成。笔记中嵌入课程截图。
- [ ] `Feature:` **课程组织** - 课程 > 章节 > 视频的层级管理
- [ ] `Feature:` **Flashcard 闪卡** - 基于时间线节点生成记忆卡片
- [ ] `Feature:` **Quiz 小测验** - AI 根据视频内容生成测验题
- [ ] `Feature:` **Cheatsheet 速查表** - 自动提取关键概念生成速查表


### 🟡 中优先级
- [ ] `Enhancement:` **Slide Lecture** - AI 可用工具标注 Slide 图片，并可插入 AI 生成的 Illustraion 图片 / HTML
- [ ] `Feature:` **学习统计仪表盘** - 观看时长、学习天数、完成进度等数据可视化
- [ ] `Feature:` **任务统计** - 转录/翻译/配音任务耗时、LLM Token 消耗量追踪
- [ ] `Feature:` **字幕全局搜索** - 跨视频搜索字幕内容，快速定位知识点
- [ ] `Feature:` **视频拖拽排序** - 自定义视频列表顺序
- [ ] `Feature:` **Podcast 模式** - 将视频转为纯音频播客格式
- [ ] `Feature:` **学习报告 Report** - 生成学习总结报告
- [ ] `UI:` **移动端适配** - 响应式布局、触摸友好

### 🟢 待定 / 探索中

- [ ] `Integration:` **Obsidian 集成**
- [ ] `Performance:` **性能优化**
- [ ] `UI:` **其他 UI/UX 增强**
- [ ] `Enhancement:` **Prompt & Workflow 优化**


---

> 💡 有想法或建议？欢迎 [提交 Issue](https://github.com/your-username/DeepLecture/issues) 或 [参与讨论](https://github.com/your-username/DeepLecture/discussions)！

## License

MIT License
