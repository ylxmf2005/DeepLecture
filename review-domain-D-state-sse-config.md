# Domain D Review: Task/SSE/State Management & Settings/Config Features

**Reviewer**: Domain D Correctness Auditor
**Date**: 2026-02-06
**Scope**: Backend task system, SSE events, frontend Zustand stores, settings/config, DnD, Dictionary, Live2D, Smart Skip, Video Progress

---

## Executive Summary

Domain D covers the real-time task system, state management, and ancillary features. The architecture is **solid overall** — the task system has proper crash recovery via SQLite persistence, SSE reconnection leverages the browser's native `EventSource` retry mechanism, and Zustand stores use well-designed persistence with migration support. However, several issues were identified, including a potential race condition in the SSE subscriber queue, missing tab removal sanitization in the tab layout store, and a stale closure in FocusModeHandler.

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High     | 2 |
| Medium   | 5 |
| Low      | 7 |
| Info     | 4 |

---

## 1. Backend Task System

### 1.1 Task State Machine (task_queue.py)

**Status**: Generally correct

The state machine follows: `PENDING → PROCESSING → READY | ERROR`

- `submit()` creates a task in PENDING state
- `update_task_progress()` transitions PENDING → PROCESSING on first progress report
- `complete_task()` and `fail_task()` are terminal transitions
- `is_terminal()` correctly prevents double-transitions

**[LOW] D-001: Cleanup uses `time.monotonic()` for TTL comparison against ISO timestamps**

- **File**: `src/deeplecture/infrastructure/workers/task_queue.py:368-384`
- The `_last_cleanup` field uses `time.monotonic()` for the cleanup interval, which is correct. However, the TTL expiry check inside `_cleanup_expired_tasks` correctly uses `datetime.datetime.now(UTC)` minus `task.updated_at`, so this is fine. No actual bug.

**[INFO] D-002: Task ID generation includes content_id, which could leak internal identifiers**

- **File**: `src/deeplecture/infrastructure/workers/task_queue.py:334-337`
- Task IDs are of the form `{task_type}_{content_id}_{timestamp}_{unique}`. This is fine for internal use, but content IDs are visible in SSE events sent to the client. This is acceptable since content IDs are already known to the client.

### 1.2 Worker Pool (task_queue.py:397-553)

**Status**: Well-designed

- Uses `ThreadPoolExecutor` with a single timeout monitor thread (avoids per-task thread overhead)
- `_consume_loop` properly handles `queue.Empty` with 1-second timeout
- `_on_future_done` callback cleans up tracking entries
- Timeout cancellation correctly calls `future.cancel()` followed by `fail_task()`

**[LOW] D-003: `future.cancel()` may not actually stop a running thread**

- **File**: `src/deeplecture/infrastructure/workers/task_queue.py:498`
- `concurrent.futures.Future.cancel()` only prevents execution if the task hasn't started yet. For already-running tasks, it has no effect. The task callable will continue running even after the timeout, potentially causing resource waste. However, this is a Python `ThreadPoolExecutor` limitation and the error state is correctly set regardless.

### 1.3 Durable Task Storage (sqlite_task_storage.py)

**Status**: Correct

- `mark_inflight_as_error()` is called on startup for crash recovery — correct
- `save()` uses `ON CONFLICT(id) DO UPDATE` and correctly preserves `created_at`
- `delete_expired_terminal()` correctly uses ISO timestamp comparison
- WAL mode enabled for concurrent read/write from multiple threads

**[INFO] D-004: SQLite connection opened per operation without connection pooling**

- **File**: `src/deeplecture/infrastructure/repositories/sqlite_task_storage.py:60-66`
- Each operation opens/closes a new connection. WAL mode mitigates contention, but under high task throughput this could become a bottleneck. Acceptable for current use case.

### 1.4 DI Container Wiring (container.py)

**Status**: Correct

- `TaskManager` correctly receives both `event_publisher` and `task_storage`
- `WorkerPool` receives `task_manager`
- `EventPublisher` max queue size is configurable via `tasks.sse_subscriber_queue_size`

---

## 2. SSE Event System

### 2.1 EventPublisher (events.py)

**[HIGH] D-005: Full subscriber queue causes silent event loss**

- **File**: `src/deeplecture/presentation/sse/events.py:84-95`
- When a subscriber queue is full (`queue.Full`), the subscriber is removed from the list and logged as a "dead queue". This means a slow client permanently loses its subscription without any reconnection signal. The client's `EventSource` won't know it was disconnected — it will just stop receiving events.
- **Impact**: If a client is briefly slow (e.g., tab in background, GC pause), it permanently loses all future events for that content_id without any error on the client side. The browser's EventSource won't trigger `onerror` because the HTTP connection is still alive; the server just stops sending events to that particular queue.
- **Recommendation**: Instead of removing the queue immediately, consider: (a) skipping the event for that subscriber but keeping the subscription, or (b) sending a special "you-were-dropped" event before removing, so the client can trigger reconnection.

### 2.2 SSE Stream Generation (events.py:146-224)

**Status**: Generally well-designed

- `subscribe()` → `initial_events_factory()` → `stream loop` pattern correctly avoids race conditions (subscribes first, then gets initial state)
- `retry: {retry_ms}\n\n` frame is sent at stream start for browser auto-reconnect (set to 3000ms)
- Keepalive comments (`": keepalive\n\n"`) prevent proxy timeouts
- `max_idle_keepalives` (60) prevents zombie connections (60 × 30s = 30 min max idle)
- `GeneratorExit` is caught for cleanup
- Incremental `id:` fields use `itertools.count(1)` for sequential SSE event IDs

**[MEDIUM] D-006: SSE event IDs are not globally unique across reconnections**

- **File**: `src/deeplecture/presentation/sse/events.py:177, 198`
- Event IDs reset to 1 on each new connection. If a client reconnects, the browser sends `Last-Event-ID` header, but the server doesn't read or use it. This means the `retry:` frame enables auto-reconnect but **no event replay** happens — the client just gets a fresh `initial_events_factory()` snapshot.
- **Impact**: This is actually **acceptable** by design because the `initial_events_factory` sends a full snapshot of current task states. Events that occurred during the disconnection gap are effectively "replayed" via the snapshot. However, this means any transient events (like progress updates) during the gap are lost. For task systems this is fine since the terminal state is what matters.

### 2.3 SSE Stream Route (routes/task.py)

**Status**: Correct

- `_reconcile_stale_tasks_on_connect()` runs before the SSE snapshot to clean up stale "processing" states
- `stream_with_context()` is used correctly for Flask streaming responses
- Headers (`Cache-Control: no-cache`, `X-Accel-Buffering: no`) are correct for SSE

---

## 3. Frontend Task Status & SSE

### 3.1 useTaskStatus Hook

**Status**: Correct with minor concern

- Uses native `EventSource` for automatic reconnection
- Correctly maps `task.task_id || task.id` for ID normalization
- `onopen` sets `isConnected = true`, `onerror` sets `isConnected = false`
- Cleanup on unmount via `eventSource.close()`

**[LOW] D-007: No task state clearing on reconnection**

- **File**: `frontend/hooks/useTaskStatus.ts:46-84`
- When `EventSource` reconnects after a disconnect, the existing `tasks` state is preserved and new `initial` events are merged in via the `setTasks` spread operator. This means stale task entries from before the disconnect persist. This is actually fine since `initial` events will overwrite them with correct data, and any tasks that no longer exist simply remain as stale entries until the component unmounts.

### 3.2 useVideoPageState Hook

**Status**: Well-architected

- SSE task completion handling uses `handledTasksRef` to prevent duplicate processing — correct
- `_eventType: "initial"` distinction prevents toast notifications for historical tasks — correct
- Optimistic updates for subtitle tasks with race condition protection — sophisticated
- Fallback polling (5s interval) activates only when SSE is disconnected — correct
- `cancelled` flag pattern prevents state updates after unmount

**[MEDIUM] D-008: Stale `processingAction` in SSE effect closure**

- **File**: `frontend/hooks/useVideoPageState.ts:274, 352-361`
- The SSE effect depends on `processingAction` in its dependency array, which means it re-runs whenever `processingAction` changes. However, inside the async `handleTasks()` function, `processingAction` could be stale by the time the metadata fetch returns. The `cancelled` flag mitigates stale state updates, but the comparison `matchingAction === processingAction` at line 356 uses a potentially stale value.
- **Impact**: In practice this is low-risk because `processingAction` changes infrequently and the effect re-runs on change. But theoretically, if two tasks complete in rapid succession and `processingAction` changes between them, one could be missed.

### 3.3 useTaskNotification Hook

**Status**: Correct

- Three notification channels: toast, title flash, browser notification
- Title flashing auto-stops after 30 seconds
- Visibility change listener stops flashing when tab becomes visible
- Browser notification uses `tag: "task-complete"` to prevent duplicates
- All controlled by per-channel settings from store

---

## 4. Zustand Stores

### 4.1 useGlobalSettingsStore

**Status**: Correct

- Uses `persist` middleware with localStorage
- Version 3 with migration support (v1→v2 for language consolidation, v2→v3 for AI settings)
- Migration correctly merges defaults for newly added settings sections
- `partialize` correctly excludes internal state (`_hydrated`, `_languageLoading`)
- All setters use functional updates to avoid stale state
- `resetToDefaults` preserves `_hydrated: true` — correct

**[LOW] D-009: `loadAIConfigFromServer` fetches config but doesn't use the result**

- **File**: `frontend/stores/useGlobalSettingsStore.ts:197-205`
- The function calls `getAppConfig()` but ignores the response. The comment says "Config loaded - defaults are managed by backend / User preferences in store override backend defaults". This is intentional — the call warms a cache used by UI components. Functionally correct but the pattern is confusing.

### 4.2 useVideoStateStore

**Status**: Correct

- Per-video state keyed by `videoId`
- Version 2 with legacy subtitle mode migration (`en` → `source`, `zh` → `target`, etc.)
- `clearVideoState` correctly uses destructuring to remove a single video entry
- All update functions spread `DEFAULT_VIDEO_STATE` first for schema forward compatibility
- Stable selector `useVideoNotes` returns frozen `EMPTY_VIDEO_NOTES` to prevent re-renders

### 4.3 useTabLayoutStore

**[HIGH] D-010: Tab layout merge on rehydration does not remove unknown/removed tabs**

- **File**: `frontend/stores/tabLayoutStore.ts:200-237`
- The `merge` function adds missing tabs but never removes tabs that are no longer in `ALL_TABS`. If a tab ID is removed from the codebase in a future update, persisted layouts with that removed tab will cause errors when trying to render the tab content.
- **Impact**: Currently all tabs are still present so this is not an active bug, but it's a latent forward-compatibility issue. When a tab is removed, users with old persisted layouts will have a phantom tab that matches no component.
- **Recommendation**: Add a filter step: `const validSidebar = persistedSidebar.filter(tab => ALL_TABS.has(tab))` before the merge.

**[MEDIUM] D-011: DnD snapshot/rollback does not deep-clone `activeTabs`**

- **File**: `frontend/stores/tabLayoutStore.ts:81-103`
- `startDrag` creates a snapshot with `{ ...activeTabs }`, which is a shallow copy. Since `activeTabs` is `{ sidebar: TabId, bottom: TabId }` with primitive values (strings), a shallow copy is sufficient. This is actually correct — no issue.

### 4.4 uploadQueueStore

**Status**: Correct

- File categorization logic is clear (PDF, video, unsupported)
- Reorder functions have proper bounds checking
- Upload functions check for empty state and in-progress state before proceeding
- Error state is properly managed with `clearError` and auto-clear on submit

### 4.5 useVocabularyStore

**Status**: Correct

- Word normalization via `toLowerCase().trim()` prevents duplicates
- Dedup check before `add` prevents duplicate entries
- `remove` correctly normalizes before comparison
- `_hydrated` state properly tracked in `onRehydrateStorage`

---

## 5. Settings & Configuration

### 5.1 Backend Config (settings.py)

**Status**: Well-designed

- Pydantic Settings with YAML source and environment variable overrides
- `_migrate_legacy_subtitle_configs` model validator handles backward compatibility
- `lru_cache` for singleton pattern with `reload_settings()` for hot reload
- All config sections have sensible defaults

### 5.2 Config Routes (config.py)

**Status**: Correct

- `/config` returns unified LLM models, TTS models, and prompt implementations
- `/languages` returns static language list
- `/note-defaults` reads from settings
- All wrapped in `@handle_errors`

### 5.3 Frontend Config API (lib/api/config.ts)

**Status**: Correct

- Clean API client calls for language settings, Live2D models, note defaults, and app config

### 5.4 SettingsDialog

**Status**: Correct

- Tab-based navigation with 7 settings tabs
- Escape key handler for closing
- `useFocusTrap` for accessibility
- Body scroll lock when open
- `aria-labelledby` for screen readers

**[LOW] D-012: Escape key listener duplicated**

- **File**: `frontend/components/dialogs/SettingsDialog.tsx:46-57`
- The component registers its own `keydown` listener for Escape, but `useFocusTrap` likely already handles Escape via its `onClose` callback. This is harmless (two close calls is idempotent) but redundant.

### 5.5 GeneralTab

**Status**: Correct

- Draft pattern for learner profile prevents saving on every keystroke
- Language settings use proper `CustomSelect` component
- "Apply Preferences" button commits draft to store

---

## 6. DnD Tab Layout

### 6.1 useDndTabLayout Hook

**Status**: Correct with good design

- Uses `@dnd-kit` with `PointerSensor` (8px activation distance prevents click interference)
- Custom collision detection: `pointerWithin` with `closestCenter` fallback
- `startDrag/commitDrag/rollbackDrag` pattern provides proper undo on cancel
- Cross-panel moves handled in `handleDragOver`, same-panel reorder in `handleDragEnd`
- Capacity constraints enforced (`MAX_SIDEBAR_TABS: 4`, `MAX_BOTTOM_TABS: 7`)

### 6.2 DraggableTabBar Component

**Status**: Correct

- `SortableTab` uses `useSortable` with proper ref, transform, and listener forwarding
- Visual feedback for drag state (opacity, shadow, ring)
- Capacity indicator shows `{count}/{max}` during drag
- Empty state placeholder ("Drop tabs here")
- `useDroppable` on panel allows dropping tabs onto empty area

---

## 7. Dictionary Feature

### 7.1 useDictionaryLookup Hook

**Status**: Correct

- 300ms debounce by default
- `AbortController` for canceling in-flight requests
- Cleanup on unmount (clears timeout and aborts request)
- Locale support check before lookup
- State updates guarded by `!controller.signal.aborted`

### 7.2 HoverableSubtitleText

**Status**: Correct

- Tokenization memoized via `useMemo`
- Supports both "hover" and "click" interaction modes
- Click mode calls `event.stopPropagation()` to prevent subtitle row seek — correct
- `memo()` wrapper prevents unnecessary re-renders
- Non-interactive mode renders plain text (no event handlers)

### 7.3 DictionaryPopup

**Status**: Correct

- Position calculation keeps popup within viewport bounds
- Escape key closes popup
- Click-outside detection with 100ms delay to avoid immediate close
- Audio playback with proper state machine (`idle → loading → playing → idle/error`)
- Audio element cleanup on entry change and unmount
- Save-to-vocabulary button with visual state change (BookmarkPlus → BookmarkCheck)
- `memo()` wrapper for performance

---

## 8. Live2D Feature

### 8.1 Live2DViewer

**[MEDIUM] D-013: Module-level global state prevents multiple instances**

- **File**: `frontend/components/live2d/Live2DViewer.tsx:71-75`
- `subdelegateInstance`, `animationFrameId`, `isFrameworkInitialized`, etc. are module-level globals. This means only one Live2DViewer instance can exist at a time. If two instances are mounted, they will fight over the shared state.
- **Impact**: Currently only one instance is used (via Live2DOverlay), so this is not an active bug. The `Live2DCanvas` component correctly uses refs instead of globals (line 89), which is the proper pattern.

### 8.2 Live2DCanvas

**Status**: Good design with refs

- Instance state moved to refs (`subdelegateRef`, `animationFrameIdRef`) — correct
- `isInitializingRef` prevents double initialization
- Model hit detection for pointer passthrough (only responds when clicking on model)
- Proper cleanup on unmount (cancel animation frame, release subdelegate)
- Scale clamped to `[0.5, 3.0]`
- Window-level mousemove listener for hover detection

### 8.3 Live2DOverlay

**Status**: Correct

- Draggable with proper bounds checking (`Math.max(0, Math.min(viewport - size))`)
- Resizable with min/max constraints
- Minimize/maximize toggle
- Close button with red hover state
- Touch support for drag and resize

---

## 9. Smart Skip

### 9.1 useSmartSkip Hook

**Status**: Correct and well-reasoned

- 0.25s epsilon for keyframe-based seeking tolerance
- Skip target guard prevents immediate re-skip after a seek
- Guard cleared only when playback enters a kept entry (not just any position)
- Manual seek sets skip target to prevent double-jump
- `handleSeek` correctly only sets guard when smart skip is enabled

**[LOW] D-014: Linear scan of timeline entries on every time update**

- **File**: `frontend/hooks/useSmartSkip.ts:62-65, 77-80`
- `timelineEntries.some()` is called on every `timeupdate` event (~4x/sec). For large timelines (100+ entries), this could be noticeable. In practice, timelines are typically under 50 entries so this is negligible.

---

## 10. Video Progress

### 10.1 useVideoProgress Hook

**Status**: Correct

- Progress saved every 5 seconds (threshold-based, not interval-based)
- Resume target initialized from stored progress
- `beforeunload` handler persists current progress
- Cleanup function also persists progress (double-safety for SPA navigation)
- Resume attempts tracked for retry logic
- Progress rounded to ms precision (`Math.round(time * 1000) / 1000`)

### 10.2 VideoProgressBar

**Status**: Correct

- Time conversion seconds → ms for react-video-seek-slider
- `Number.isFinite` guards against NaN/Infinity
- currentTime clamped to `[0, duration]`
- Fallback static bar when duration is 0 or invalid

---

## 11. FocusModeHandler

**[MEDIUM] D-015: Stale `subtitleMode` in debounced visibility change handler**

- **File**: `frontend/components/features/FocusModeHandler.tsx:123, 138-143`
- `handleVisibilityChange` is memoized with `subtitleMode` in its dependency array. However, the debounced callback inside `setTimeout` captures the `subtitleMode` value at the time the timeout was set. If the user manually changes subtitle mode during the 1.5s debounce window, the stale value will be used for the auto-switch logic.
- **Impact**: Low — the 1.5s window is short and subtitle mode changes during tab leave are unlikely. The debounce correctly prevents false triggers from brief tab switches.

**[LOW] D-016: `voiceoverAutoSwitch` piggybacks on subtitle auto-switch debounce**

- **File**: `frontend/components/features/FocusModeHandler.tsx:149-160`
- The voiceover auto-switch is inside the same `setTimeout` as subtitle auto-switch, but it's controlled by a hardcoded `enabled: true` rather than a user setting. This means voiceover auto-switching cannot be independently disabled.
- **Impact**: Minor — the feature only activates if `quickToggleTranslatedVoiceoverId` is set, which is an explicit user configuration.

---

## 12. Error Handling Across Features

**[MEDIUM] D-017: Upload store errors not surfaced via toast**

- **File**: `frontend/stores/uploadQueueStore.ts:174-177, 198-200, 213-216`
- Upload errors are stored in `state.error` but rely on the consumer component to display them. If the component that reads `error` is not mounted or doesn't use toast, the user gets no notification. Other parts of the system use toast directly.
- **Impact**: Depends on the consumer component implementation. If the upload dialog properly displays `state.error`, this is fine. But it's inconsistent with the rest of the system which uses `toast.error()` directly.

---

## Summary of Findings

### High Severity
| ID | Location | Issue |
|----|----------|-------|
| D-005 | `events.py:84-95` | Full subscriber queue silently removes subscriber — client loses all future events |
| D-010 | `tabLayoutStore.ts:200-237` | Tab layout merge does not filter out removed/unknown tab IDs |

### Medium Severity
| ID | Location | Issue |
|----|----------|-------|
| D-006 | `events.py:177` | SSE event IDs reset per connection — no replay (acceptable by design) |
| D-008 | `useVideoPageState.ts:352` | Potentially stale `processingAction` in async SSE handler |
| D-013 | `Live2DViewer.tsx:71-75` | Module-level globals prevent multiple Live2DViewer instances |
| D-015 | `FocusModeHandler.tsx:138` | Stale `subtitleMode` captured in debounced callback |
| D-017 | `uploadQueueStore.ts:174` | Upload errors stored in state, not surfaced via toast |

### Low Severity
| ID | Location | Issue |
|----|----------|-------|
| D-001 | `task_queue.py:368` | Cleanup uses two different time sources (cosmetic, not a bug) |
| D-003 | `task_queue.py:498` | `future.cancel()` doesn't stop running tasks (Python limitation) |
| D-007 | `useTaskStatus.ts:63` | Stale task entries preserved across reconnection |
| D-009 | `useGlobalSettingsStore.ts:197` | `loadAIConfigFromServer` ignores response (intentional cache warm) |
| D-012 | `SettingsDialog.tsx:46` | Escape key handler duplicated with focus trap |
| D-014 | `useSmartSkip.ts:62` | Linear timeline scan on every time update |
| D-016 | `FocusModeHandler.tsx:149` | Voiceover auto-switch cannot be independently disabled |

### Info
| ID | Location | Note |
|----|----------|------|
| D-002 | `task_queue.py:334` | Task IDs contain content_id (acceptable) |
| D-004 | `sqlite_task_storage.py:60` | No connection pooling (acceptable for throughput) |

---

## Architecture Notes

The task system architecture is well-designed:

1. **Crash Recovery**: `mark_inflight_as_error()` on startup reconciles interrupted tasks
2. **SSE Reliability**: `initial_events_factory` called after `subscribe()` avoids race conditions
3. **Durable State**: SQLite persistence enables accurate snapshots after restart
4. **Optimistic Updates**: Frontend uses optimistic status updates with race condition guards
5. **Fallback Polling**: Activates only when SSE is disconnected (5s interval)
6. **Store Design**: Zustand stores use proper persistence, migration, and hydration patterns
7. **DnD**: Snapshot/rollback pattern provides clean undo semantics
