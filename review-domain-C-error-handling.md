# Domain C: Frontend Error Handling & UX Consistency Review

## 1. Error Handling Infrastructure Analysis

### 1.1 Dual Toast System (Critical Architectural Issue)

The project has **two independent toast/notification systems** that coexist:

| System | Files | Usage Count | Mounted In |
|--------|-------|-------------|------------|
| **Sonner** (`toast` from `sonner`) | `app/layout.tsx` `<Toaster>` | ~12 call sites | `layout.tsx` ✅ Active |
| **Custom ErrorContext/Toast** | `ErrorContext.tsx`, `useErrorHandler.ts`, `Toast.tsx` | **0 call sites** | **NOT mounted** ❌ |

**Finding:** The custom `ErrorProvider` from `ErrorContext.tsx` is **never mounted** in the component tree. The `<Toaster>` from `sonner` is the only active toast system. The custom `ErrorContext`, `useErrorHandler` hook, `Toast.tsx` component, and `useErrors()` hook are all **dead code** — defined but never imported or used by any consumer.

- `ErrorProvider` is exported from `contexts/index.ts` but not used in `layout.tsx` or anywhere else
- `useErrors()` is never called by any component or hook
- `handleApiError()` from `useErrorHandler` is never called
- The custom `Toast.tsx` and `ToastContainer` are never rendered

### 1.2 Active Error Infrastructure: Sonner

Sonner is properly mounted at `layout.tsx:46` with `richColors` and `position="bottom-right"`.

Components using `toast` from sonner:
- `useVoiceoverHandlers.ts` — `toast.warning`, `toast.success`, `toast.error`
- `useSubtitleManagement.ts` — `toast.error`
- `useContentHandlers.ts` — `toast.info`
- `useNoteGeneration.ts` — `toast.success`, `toast.error`
- `useTaskNotification.ts` — `toast.success`, `toast.error` (SSE task completion)
- `VideoPlayer.tsx` — `toast.info`
- `ExplanationList.tsx` — `toast.error`

### 1.3 API Client Error Handling

`lib/api/client.ts` — Axios response interceptor wraps all errors into `APIError` via `wrapAPIError()`. This is well-structured:
- Classifies errors by code: NETWORK_ERROR, TIMEOUT, CANCELLED, BAD_REQUEST, NOT_FOUND, SERVER_ERROR, etc.
- Provides user-friendly default messages
- Preserves original error for debugging
- Logs non-cancellation errors

`lib/api/errors.ts` — `APIError` class with typed error codes, status helpers (`isNetworkError()`, `isCancelled()`, etc.)

`lib/utils/errorUtils.ts` — Utility functions `toError()`, `getErrorMessage()`, `getErrorStatus()` for safe error coercion.

### 1.4 ErrorBoundary

`shared/infrastructure/ErrorBoundary.tsx` — Class component with:
- `getDerivedStateFromError` + `componentDidCatch` (proper React pattern)
- Configurable fallback (ReactNode or render prop with reset)
- Default fallback UI with error message display and retry button
- Scoped logging via `logger.scope()`

`components/providers/RootErrorBoundary.tsx` — Wraps entire app in `layout.tsx`. Provides full-page error recovery UI with "Try Again" and "Reload Page" buttons. ✅ Correct.

### 1.5 Logger Infrastructure

`shared/infrastructure/logger.ts` — Centralized logger with scoped contexts. All error handling uses `log.error()` / `log.warn()` instead of raw `console.error()`. The only `console.error` / `console.warn` in app code are in:
- `app/video/[id]/data.ts` — Server-side data fetching (acceptable: runs in Node.js SSR)
- `lib/live2d/` — Third-party Live2D SDK code (acceptable: vendor code)
- `hooks/useDictionaryLookup.ts` — Uses `console.warn` (minor inconsistency)
- `lib/dictionary/lookup.ts` — Uses `console.warn` (minor inconsistency)

---

## 2. Component/Hook Error Handling Review

### 2.1 Handlers (hooks/handlers/)

#### useVoiceoverHandlers.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `handleGenerateVoiceover` | ✅ | ❌ **No toast** | ✅ `setVoiceoverProcessing(null)` | ⚠️ **Warning** |
| `handleDeleteVoiceover` | ✅ | ❌ **No toast** | N/A | ⚠️ **Warning** |
| `handleUpdateVoiceover` | ✅ | ✅ `toast.error` | N/A (re-throws) | ✅ |

#### useTimelineHandlers.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `handleGenerateTimeline` | ✅ | ❌ **No toast** | ✅ all three resets | ⚠️ **Warning** |

#### useSubtitleHandlers.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `handleGenerateSubtitles` | ✅ | ❌ **No toast** | ✅ | ⚠️ **Warning** |
| `handleTranslateSubtitles` | ✅ | ❌ **No toast** | ✅ | ⚠️ **Warning** |

#### useSlideHandlers.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `handleCapture` (explainSlide) | ✅ | ❌ **No toast** | N/A | ⚠️ **Warning** |
| `handleGenerateSlideLecture` | ✅ | ❌ **No toast** | ✅ | ⚠️ **Warning** |
| `handleUploadSlide` | ✅ | ❌ **No toast** | N/A | ⚠️ **Warning** |

#### useContentHandlers.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `handleAddToNotes` (fallback) | ✅ | ✅ `toast.info` | N/A | ✅ |
| `handleAskAtTime` | ✅ | ❌ (degrades gracefully) | N/A | ✅ Acceptable |
| `handleAddNoteAtTime` | ✅ `.catch()` | ❌ (degrades gracefully) | N/A | ✅ Acceptable |

### 2.2 State Hooks

#### useVideoPageState.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| Initial content fetch | ✅ | ❌ **No toast** | ✅ `setLoading(false)` | ⚠️ Silent failure |
| SSE content refresh | ✅ | ❌ | N/A (background) | ✅ Acceptable |
| SSE timeline load | ✅ | ❌ | N/A | ✅ Acceptable |
| SSE voiceover refresh | ✅ | ❌ | ✅ `finally` | ✅ Acceptable |
| Fallback polling | ✅ `catch {}` | ❌ | N/A (retry loop) | ✅ Acceptable |
| Timeline load (ready status) | ✅ | ❌ (404 filtered) | ✅ `finally` | ✅ |

**Note:** SSE task completion notifications are handled by `useTaskNotification` which uses sonner toast. So users DO get notified when long-running tasks succeed or fail. The catch blocks in SSE handlers are for silent data refresh failures, which is acceptable since the main notification comes from `useTaskNotification`.

#### useVoiceoverManagement.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `refreshVoiceovers` | ✅ | ❌ **No toast** | ✅ `finally` | ⚠️ Warning |
| Load sync timeline | ✅ | ❌ **No toast** | Sets null | ⚠️ Warning |

#### useSubtitleManagement.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `loadSubtitles` | ✅ | ✅ `toast.error` with description | ✅ | ✅ |

#### useNoteGeneration.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| Load note after generation | ✅ | ✅ `toast.error` | N/A | ✅ |
| `handleGenerateNote` | ✅ | ✅ `toast.error` | ✅ `setGeneratingNote(false)` | ✅ |

### 2.3 Feature Components

#### AskTab.tsx
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `initConversations` | ✅ | ❌ **No toast** | ✅ `finally` | ⚠️ **Warning** |
| `handleSelectConversation` | ✅ | ❌ **No toast** | ✅ `finally` | ⚠️ Warning |
| `handleCreateConversation` | ✅ | ❌ **No toast** | ✅ `finally` | ⚠️ Warning |
| `handleDeleteConversation` | ✅ | ❌ **No toast** | N/A | ⚠️ Warning |
| `handleSend` | ✅ | ❌ (shows inline error msg) | ✅ | ✅ Acceptable (inline UX) |

#### VerifyTab.tsx
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| Load report | ✅ | ❌ (sets `loadError` state) | ✅ `finally` | ✅ (dedicated error UI) |
| `handleGenerate` | ✅ | ❌ (sets `loadError` state) | ✅ | ✅ (dedicated error UI) |

#### CheatsheetTab.tsx
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| Load cheatsheet | ✅ | ❌ (sets `loadError` state) | ✅ `finally` | ✅ (dedicated error UI) |
| `handleGenerate` | ✅ | ❌ (sets `loadError` state) | ✅ | ✅ (dedicated error UI) |
| `handleSave` | ✅ | ❌ (sets `loadError` state) | ✅ `finally` | ✅ (dedicated error UI) |

#### ExplanationList.tsx
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `fetchHistory` | ✅ | ❌ **No toast** | ✅ `finally` | ⚠️ **Warning** |
| `handleDelete` | ✅ | ✅ `toast.error` | ✅ `finally` | ✅ |

#### VideoList.tsx
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `fetchContent` | ✅ | ❌ (sets `error` state) | ✅ `finally` | ✅ (inline error UI) |
| `handleDelete` | ✅ | ❌ (sets `error` state) | ✅ `finally` | ⚠️ Minor (error state is generic) |
| `handleRename` | ✅ | ❌ **No toast** | N/A | ⚠️ **Warning** |

### 2.4 Stores

#### uploadQueueStore.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `submitPdfs` | ✅ | ❌ (sets `error` state) | ✅ | ✅ (inline error display) |
| `submitVideos` | ✅ | ❌ (sets `error` state) | ✅ | ✅ (inline error display) |
| `importUrl` | ✅ | ❌ (sets `error` state) | ✅ | ✅ (inline error display) |

#### useGlobalSettingsStore.ts
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `loadLanguageFromServer` | ✅ | ❌ **No toast** | ✅ `finally` | ✅ Acceptable (startup, non-blocking) |
| `loadNoteDefaultsFromServer` | ✅ | ❌ **No toast** | N/A | ✅ Acceptable (startup) |
| `loadAIConfigFromServer` | ✅ | ❌ **No toast** | N/A | ✅ Acceptable (startup) |

### 2.5 Editor Components

#### MarkdownNoteEditor.tsx
| Operation | Try/Catch | Toast | Loading Reset | Verdict |
|-----------|-----------|-------|---------------|---------|
| `scheduleServerSave` (auto-save) | ✅ `.catch()` | ❌ **No toast** | N/A | ⚠️ **Warning** (silent save failure) |
| `handleImageUpload` | ✅ | ❌ **No toast** (re-throws) | N/A | ⚠️ Warning (Milkdown handles) |
| Load server note | ✅ | ❌ **No toast** | N/A | ✅ Acceptable (fallback to local) |

### 2.6 Server-Side Data Fetching

#### app/video/[id]/data.ts
| Operation | Try/Catch | Notification | Verdict |
|-----------|-----------|--------------|---------|
| `getContentMetadataServer` | ✅ | `console.error` | ✅ Acceptable (SSR, no UI) |
| `listVoiceoversServer` | ✅ | `console.error` | ✅ Acceptable (SSR, no UI) |

---

## 3. Issue Summary

### Critical Issues

| # | Issue | Location | Description |
|---|-------|----------|-------------|
| C-1 | **Dead ErrorContext system** | `ErrorContext.tsx`, `useErrorHandler.ts`, `Toast.tsx` | The custom error handling infrastructure (ErrorProvider, useErrors, ToastContainer) is completely unused. `ErrorProvider` is never mounted in the component tree. All actual error toast notifications use `sonner`. This is ~200 lines of dead code that creates confusion about which error system to use. |

### Warning Issues

| # | Issue | Location | Description |
|---|-------|----------|-------------|
| W-1 | Silent failure on voiceover generation | `useVoiceoverHandlers.ts:56` | `handleGenerateVoiceover` catches error, logs, resets processing, but shows no toast. User sees processing stop with no explanation. **Mitigated by SSE**: if the task was submitted, `useTaskNotification` will show a toast on task error. But if the API call itself fails (network error before task creation), user gets no feedback. |
| W-2 | Silent failure on voiceover deletion | `useVoiceoverHandlers.ts:73` | `handleDeleteVoiceover` catches error but shows no toast. Voiceover remains in list. User may not realize deletion failed. |
| W-3 | Silent failure on timeline generation | `useTimelineHandlers.ts:75` | `handleGenerateTimeline` catches error but shows no toast. User sees processing stop with no explanation. Same SSE mitigation as W-1. |
| W-4 | Silent failure on subtitle generation | `useSubtitleHandlers.ts:48` | `handleGenerateSubtitles` catches error but shows no toast. Same SSE mitigation pattern. |
| W-5 | Silent failure on subtitle translation | `useSubtitleHandlers.ts:66` | `handleTranslateSubtitles` catches error but shows no toast. Same SSE mitigation pattern. |
| W-6 | Silent failure on slide explanation | `useSlideHandlers.ts:69` | `handleCapture` (explainSlide) catches error but shows no toast. User may not know explanation generation failed to start. |
| W-7 | Silent failure on slide lecture generation | `useSlideHandlers.ts:91` | `handleGenerateSlideLecture` catches error but shows no toast. Same SSE mitigation as W-1. |
| W-8 | Silent failure on slide deck upload | `useSlideHandlers.ts:108` | `handleUploadSlide` catches error but shows no toast. User may not know upload failed. |
| W-9 | Silent failure on Ask init | `AskTab.tsx:98` | `initConversations` catches error but shows no toast. User sees empty chat with no explanation. |
| W-10 | Silent failure on Ask operations | `AskTab.tsx:128,153,186` | `handleSelectConversation`, `handleCreateConversation`, `handleDeleteConversation` all catch errors but show no toast. |
| W-11 | Silent failure on explanation history load | `ExplanationList.tsx:47` | `fetchHistory` catches error but shows no toast. User sees empty explanations list with no explanation. |
| W-12 | Silent failure on content rename | `VideoList.tsx:93` | `handleRename` catches error but shows no toast. Comment says "Optional: show toast error". |
| W-13 | Silent auto-save failure | `MarkdownNoteEditor.tsx:45` | `saveVideoNote` promise rejection is caught but only logged. User's note may fail to persist to server without notification. |
| W-14 | Silent voiceover list load failure | `useVoiceoverManagement.ts:97` | `refreshVoiceovers` catches error but shows no toast. |
| W-15 | Silent voiceover sync timeline load failure | `useVoiceoverManagement.ts:138` | Catches error, sets timeline to null, but shows no toast. |

### Info Issues

| # | Issue | Location | Description |
|---|-------|----------|-------------|
| I-1 | `console.warn` instead of logger | `useDictionaryLookup.ts:131`, `lib/dictionary/lookup.ts:141` | Dictionary code uses `console.warn` instead of scoped logger. Minor inconsistency. |
| I-2 | Error type not narrowed in some catch blocks | `CheatsheetTab.tsx:86,121,147`, `VerifyTab.tsx:93,122` | Uses `err instanceof Error ? err : undefined` pattern instead of `toError(err)`. Inconsistent with rest of codebase. |
| I-3 | crepe.create() promise not caught | `MarkdownNoteEditor.tsx:91` | `crepe.create().then(...)` has no `.catch()`. If Milkdown editor fails to initialize, it would be an unhandled rejection. |
| I-4 | No max toast limit | Sonner config at `layout.tsx:46` | Sonner's `<Toaster>` doesn't set `toastOptions.limit`. Multiple rapid errors could stack toasts. Sonner has internal limits but explicit config is cleaner. |

---

## 4. Error Handling Consistency Matrix

### Legend
- ✅ Toast on error (user notified)
- 🔔 SSE notification covers task errors (via `useTaskNotification`)
- 📋 Inline error state (component shows error UI)
- ⚠️ Silent (log only, no user notification)
- 🔄 Graceful degradation (fallback behavior)

| Component/Hook | Operation | Error Notification | Severity |
|----------------|-----------|-------------------|----------|
| **useVoiceoverHandlers** | Generate voiceover | ⚠️ Silent (🔔 SSE covers task errors) | Medium |
| **useVoiceoverHandlers** | Delete voiceover | ⚠️ Silent | Medium |
| **useVoiceoverHandlers** | Update/rename voiceover | ✅ Toast | OK |
| **useTimelineHandlers** | Generate timeline | ⚠️ Silent (🔔 SSE covers task errors) | Medium |
| **useSubtitleHandlers** | Generate subtitles | ⚠️ Silent (🔔 SSE covers task errors) | Medium |
| **useSubtitleHandlers** | Translate subtitles | ⚠️ Silent (🔔 SSE covers task errors) | Medium |
| **useSlideHandlers** | Explain slide | ⚠️ Silent | Medium |
| **useSlideHandlers** | Generate slide lecture | ⚠️ Silent (🔔 SSE covers task errors) | Medium |
| **useSlideHandlers** | Upload slide deck | ⚠️ Silent | Medium |
| **useSubtitleManagement** | Load subtitles | ✅ Toast with description | OK |
| **useNoteGeneration** | Generate note | ✅ Toast | OK |
| **useNoteGeneration** | Load note after generation | ✅ Toast | OK |
| **useTaskNotification** | SSE task complete/error | ✅ Toast (configurable) | OK |
| **useVoiceoverManagement** | Refresh voiceovers | ⚠️ Silent | Low |
| **useVoiceoverManagement** | Load sync timeline | ⚠️ Silent | Low |
| **useVideoPageState** | Initial content load | ⚠️ Silent | Low |
| **useVideoPageState** | SSE content refresh | ⚠️ Silent (background) | OK |
| **useVideoPageState** | Fallback polling | ⚠️ Silent (retry loop) | OK |
| **AskTab** | Init conversations | ⚠️ Silent | Medium |
| **AskTab** | Select/create/delete conversation | ⚠️ Silent | Medium |
| **AskTab** | Send message | 🔄 Inline error message | OK |
| **VerifyTab** | Load/generate report | 📋 Inline error state | OK |
| **CheatsheetTab** | Load/generate/save | 📋 Inline error state | OK |
| **ExplanationList** | Load history | ⚠️ Silent | Medium |
| **ExplanationList** | Delete explanation | ✅ Toast | OK |
| **VideoList** | Load content | 📋 Inline error state | OK |
| **VideoList** | Delete content | 📋 Inline error state | OK |
| **VideoList** | Rename content | ⚠️ Silent | Medium |
| **uploadQueueStore** | Submit PDFs/videos/URL | 📋 Inline error state | OK |
| **useGlobalSettingsStore** | Load language/config | ⚠️ Silent (startup) | OK |
| **MarkdownNoteEditor** | Auto-save to server | ⚠️ Silent | Medium |
| **MarkdownNoteEditor** | Load server note | ⚠️ Silent (fallback to local) | OK |

---

## 5. Toast System Analysis

### Sonner Toast (Active System)
- **Mounted**: `layout.tsx` via `<Toaster richColors position="bottom-right" />`
- **Types used**: `toast.success()`, `toast.error()`, `toast.warning()`, `toast.info()`
- **Auto-dismiss**: Yes (sonner default ~4s for success/info, persistent for errors)
- **Manual dismiss**: Yes (sonner default)
- **Stacking**: Yes (sonner handles this)
- **Dark mode**: Yes (`richColors` adapts)

### Custom Toast System (Dead Code)
- **Mounted**: ❌ Never
- **Auto-dismiss**: Only non-error types (5s timeout)
- **Manual dismiss**: Yes (X button)
- **Stacking**: Yes (flex column, bottom-right)
- **Issues**: Complete dead code. `ErrorProvider`, `useErrors()`, `useErrorHandler`, `ToastContainer`, `Toast` are all unused.

---

## 6. Loading & Empty State Audit

| Component | Loading State | Empty State | Notes |
|-----------|--------------|-------------|-------|
| **VideoList** | ✅ Spinner | ✅ "No content uploaded yet." | Good |
| **ExplanationList** | ✅ Spinner | ✅ "No explanations yet." | Good |
| **AskTab** | ✅ "Loading…" text | ✅ Empty messages area | Good |
| **VerifyTab** | ✅ Spinner "Loading verification report..." | ✅ CTA "Verify Claims" | Good |
| **CheatsheetTab** | ✅ Spinner "Loading cheatsheet..." | ✅ CTA "Generate Cheatsheet" | Good |
| **FlashcardTab** | ✅ "Loading vocabulary..." | ✅ "No saved words yet" with hint | Good |
| **MarkdownNoteEditor** | ✅ "Loading editor..." | N/A (editor always present) | Good |
| **TimelineList** | N/A (loaded by parent) | N/A | Loading controlled by `timelineLoading` |
| **SubtitleList** | N/A (loaded by parent) | N/A | Loading controlled by `subtitlesLoading` |
| **DictionaryPopup** | ✅ Loading skeleton | ✅ "Word not found" | Good |

---

## 7. Recommendations

### Priority 1: Remove Dead Code
Delete or repurpose the unused custom error handling system:
- `contexts/ErrorContext.tsx` — Remove or mark as deprecated
- `hooks/useErrorHandler.ts` — Remove
- `components/ui/Toast.tsx` — Remove
- Remove related exports from `contexts/index.ts`

### Priority 2: Add Toast Notifications to Silent Failures
The following user-initiated actions should show `toast.error()` when they fail:
1. `useVoiceoverHandlers` — `handleGenerateVoiceover`, `handleDeleteVoiceover`
2. `useTimelineHandlers` — `handleGenerateTimeline`
3. `useSubtitleHandlers` — `handleGenerateSubtitles`, `handleTranslateSubtitles`
4. `useSlideHandlers` — `handleCapture`, `handleGenerateSlideLecture`, `handleUploadSlide`
5. `AskTab` — `initConversations`, `handleSelectConversation`, `handleCreateConversation`, `handleDeleteConversation`
6. `ExplanationList` — `fetchHistory`
7. `VideoList` — `handleRename`

**Note:** For task-based operations (W-1, W-3, W-4, W-5, W-7), the SSE `useTaskNotification` provides toast on task completion/error. However, if the initial API call to **submit** the task fails (e.g., network error), the user gets no feedback. Adding a toast for the initial submission failure is important.

### Priority 3: Minor Consistency Fixes
1. Replace `console.warn` with scoped logger in `useDictionaryLookup.ts` and `lib/dictionary/lookup.ts`
2. Use `toError(err)` consistently in `CheatsheetTab.tsx` and `VerifyTab.tsx` catch blocks
3. Add `.catch()` to `crepe.create().then(...)` in `MarkdownNoteEditor.tsx`
4. Consider adding a toast or subtle indicator for note auto-save failures

---

## 8. Summary

**Overall Assessment: Good foundation with gaps in user-facing error feedback**

The error handling architecture is well-designed at the infrastructure level:
- ✅ Centralized API error classification (`APIError` with typed codes)
- ✅ Consistent error coercion utilities (`toError`, `getErrorMessage`)
- ✅ Scoped logging throughout the codebase
- ✅ Root error boundary with recovery UI
- ✅ Sonner toast system properly configured
- ✅ SSE task notification system for long-running operations
- ✅ Good loading and empty states across components
- ✅ Race condition protection in async effects

Key gaps:
- ❌ ~200 lines of dead error handling code (custom ErrorContext/Toast system)
- ⚠️ ~15 user-initiated API operations silently fail (log only, no toast)
- ⚠️ Task submission failures (before SSE takes over) have no user feedback
- Minor: 2 files use `console.warn` instead of scoped logger
