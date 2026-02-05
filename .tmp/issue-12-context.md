# Context Summary: Multi-track subtitle switching with auto-toggle

## Feature Understanding
**Intent**: Implement a system to manage multiple subtitle tracks (original and translated) with named copies, allowing users to specify which track is "original" and which is "translated". Add a video player toggle button for quick switching between tracks and auto-switch behavior that changes to translated when leaving the video and back to original when watching.

**Scope signals**: multi-track, subtitle switching, auto-toggle, original/translated tracks, video player controls, auto-pause integration, track selection, track management

## Relevant Files

### Source Files (Backend)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/subtitle.py` — Core subtitle generation and enhancement/translation logic. Currently saves subtitles with language suffix (e.g., `en`, `zh`, `en_enhanced`)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/dto/subtitle.py` — Subtitle DTOs including `SubtitleResult`, `GenerateSubtitleRequest`, `EnhanceTranslateRequest`
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/subtitle.py` — Protocol defining `SubtitleStorageProtocol` with `save()`, `load()`, `exists()`, `delete()`, `list_languages()` methods
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_subtitle_storage.py` — File system implementation storing subtitles as SRT files with pattern `subtitle_{language}.srt`
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/subtitle.py` — REST API routes for subtitle generation, enhancement, and retrieval (`GET /<content_id>`, `POST /<content_id>/generate`, `POST /<content_id>/enhance-translate`)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/config/settings.py` — Configuration system using Pydantic with YAML support; already has subtitle enhancement config

### Source Files (Frontend)
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx` — Main video player component with subtitle overlay, language menu (Lines 487-546), and subtitle mode switching. Uses `SubtitlePlayerMode = SubtitleDisplayMode | "off"`
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayerSection.tsx` — Wrapper managing video player state including subtitle mode
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useSubtitleManagement.ts` — Hook managing subtitle loading, caching, and mode selection. Loads source/target/dual/dual_reversed subtitle arrays based on mode
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useVideoPageSettings.ts` — Settings coordination hook (referenced by types)
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/FocusModeHandler.tsx` — Implements auto-pause when user leaves (Line 83-136 using `visibilitychange` event), handles auto-resume behavior
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/api/subtitle.ts` — API client for subtitle operations (`generateSubtitles`, `enhanceAndTranslate`, `getSubtitles`, `getSubtitlesVtt`)

### Documentation
- `/Users/EthanLee/Desktop/CourseSubtitle/docs/demo/dual-subtitle.md` — Current dual subtitle feature documentation
- `/Users/EthanLee/Desktop/CourseSubtitle/.serena/memories/subtitle_regeneration_data_flow.md` — Detailed data flow for subtitle regeneration including SSE events and state management
- `/Users/EthanLee/Desktop/CourseSubtitle/docs/README.md` — Feature overview and navigation

### Tests
- `/Users/EthanLee/Desktop/CourseSubtitle/tests/unit/use_cases/test_subtitle.py` — Unit tests for SubtitleUseCase with mocked dependencies

### Configuration
- `/Users/EthanLee/Desktop/CourseSubtitle/CLAUDE.md` — Project instructions: no Co-author, no Claude Code attribution, Delegate Mode instructions
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts` — Type definitions for `SubtitleDisplayMode` (source/target/dual/dual_reversed), `ViewMode`, `GlobalSettings`, `VideoState`, `PlaybackSettings`

## Architecture Context

### Existing Patterns

**Clean Architecture (Backend)**
- Domain layer: Pure entities (`Segment`) and errors
- Use Cases layer: Business logic (`SubtitleUseCase`), DTOs, interfaces (protocols)
- Infrastructure layer: Concrete implementations (`FsSubtitleStorage`, gateways)
- Presentation layer: API routes, SSE events
- DI Container: Composition root at `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/di/container.py`

**Multi-track voiceover pattern** (reference at `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/voiceover.py`):
- Stores multiple voiceover files with metadata in JSON (`voiceovers/voiceovers.json`)
- Uses `selectedVoiceoverId` in frontend state to track active voiceover
- Sync timeline JSON for playback coordination

**Subtitle storage pattern**:
- Files named `subtitle_{language}.srt` (e.g., `subtitle_en.srt`, `subtitle_zh.srt`, `subtitle_en_enhanced.srt`)
- `list_languages()` method scans directory for available subtitle files
- Uses `SubtitleStorageProtocol` for abstraction

**Frontend state management**:
- Zustand stores: `GlobalSettingsStore` (user preferences) and `VideoStateStore` (per-video state)
- Semantic subtitle modes: `source`, `target`, `dual`, `dual_reversed` (language-agnostic)
- `subtitleRefreshVersion` for cache invalidation on SSE events
- Request ID protection against race conditions in `useSubtitleManagement`

**Auto-pause detection** (at `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/FocusModeHandler.tsx`):
- Uses `document.visibilitychange` event (Line 83)
- Tracks `wasPlayingRef` and `leaveTimeRef` to detect if user was watching
- Already has `autoPauseOnLeave` and `autoResumeOnReturn` settings in `PlaybackSettings`

### Integration Points

**Backend storage**: `SubtitleStorageProtocol` needs extension to:
- Support named subtitle tracks beyond language codes
- Store track metadata (e.g., which track is "original" vs "translated")
- Possibly introduce a manifest/metadata file similar to voiceover pattern

**Frontend state**: `VideoState` and subtitle mode system needs:
- Track designation system (mark tracks as "original" or "translated")
- Track selection UI separate from display mode
- Auto-switch logic integrated with FocusModeHandler

**API layer**: New or extended endpoints for:
- Listing available subtitle tracks with metadata
- Setting track designation (original/translated)
- Renaming/copying tracks

**Settings integration**: Extend `PlaybackSettings` or create new settings group for:
- Auto-switch behavior preferences
- Default track selections

## Constraints Discovered

- **Language-agnostic design**: Frontend uses semantic modes (`source`, `target`, `dual`) not hardcoded language codes (`en`, `zh`). New system must maintain this abstraction (from `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts`)
- **SSE event system**: All background operations must integrate with task queue and SSE broadcasting for real-time updates (pattern documented in `.serena/memories/subtitle_regeneration_data_flow.md`)
- **Cache invalidation**: Must use `subtitleRefreshVersion` pattern to force subtitle reload when tracks change
- **Clean Architecture boundaries**: No business logic in presentation layer; use protocols for abstraction
- **No emojis in responses**: Per project instructions in `CLAUDE.md`
- **File naming convention**: Current pattern is `subtitle_{language}.srt` - need to maintain or extend systematically
- **Race condition protection**: Must implement request ID tracking pattern for async operations
- **Voiceover integration**: Subtitle system is separate from voiceover sync timeline but both affect video playback state

## Recommended Focus Areas for Bold-Proposer

**Backend metadata architecture**: Explore SOTA approaches for multi-track subtitle management. Should we use a manifest file (like voiceover's JSON) or extend the current file-naming convention? Consider version control and rollback patterns.

**Track designation UX**: Research best practices for track management in video players (YouTube, VLC, browser `<video>` element). How do users understand "original" vs "translated" vs "custom" tracks?

**Auto-switch behavior patterns**: Investigate auto-language switching in existing video platforms. Should it be bidirectional (original <-> translated) or customizable? Consider edge cases like multiple translated tracks or no original track.

**State synchronization**: How should track selection state synchronize between player overlay, sidebar, and backend persistence? Consider offline/online scenarios and conflict resolution.

## Complexity Estimation

**Estimated LOC**: ~450 (Large)

**Lite path checklist**:
- [ ] All knowledge within repo (no internet research needed): **no** - Need SOTA research on multi-track subtitle UX patterns and state management approaches
- [ ] Files affected < 5: **no** - Affects 10+ files: backend (use cases, storage, routes, DI), frontend (hooks, components, stores, types)
- [ ] LOC < 150: **no** - Estimated ~450 LOC

**Breakdown**:
- Backend storage + metadata system: ~100 LOC (new manifest file, extend protocol, update storage impl)
- Backend API routes: ~50 LOC (list tracks, set designation, rename/copy endpoints)
- Backend use case logic: ~60 LOC (track management operations, validation)
- Frontend track selection UI: ~80 LOC (new component or extend existing)
- Frontend auto-switch logic: ~60 LOC (integrate with FocusModeHandler)
- Frontend state management: ~40 LOC (extend stores, add track selection state)
- Frontend hooks: ~40 LOC (new `useTrackManagement` or extend existing)
- Tests: ~20 LOC (basic coverage)

**Recommended path**: `full`

**Rationale**: This feature requires research into SOTA multi-track subtitle management patterns, UX design for track designation, and architectural decisions about metadata storage. The implementation spans 10+ files across backend and frontend with complex state synchronization requirements. The auto-switch behavior needs careful integration with existing FocusModeHandler and consideration of edge cases. A full debate with web research will help identify best practices and prevent design mistakes.
