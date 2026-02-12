---
title: "feat: Add Video Bookmarks Module"
type: feat
date: 2026-02-12
brainstorm: docs/brainstorms/2026-02-12-video-bookmarks-brainstorm.md
---

# feat: Add Video Bookmarks Module

## Overview

Add a **Bookmarks** draggable tab module that lets users mark timestamps in a video, attach notes to each bookmark, click to jump, and see bookmark positions as dots on the video progress bar. The feature follows the existing 6-layer vertical slice architecture (Protocol → Storage → DTO → UseCase → Route → Frontend Component).

## Problem Statement / Motivation

Users studying long video lectures need a way to mark key moments for later review. Current options (Timeline, Subtitles) are auto-generated and not user-editable. There is no user-driven annotation system tied to specific timestamps. Bookmarks fill this gap with a lightweight, CRUD-only module.

## Proposed Solution

A full vertical slice following the existing Note/Quiz/Cheatsheet pattern:

- **Backend**: JSON-file storage at `content/{id}/bookmarks/bookmarks.json`, CRUD REST API, Clean Architecture layering
- **Frontend**: New `BookmarkTab` component in the bottom panel, progress bar overlay markers, `B` keyboard shortcut
- **No AI generation** — pure user-driven CRUD

## Technical Approach

### Data Model

```python
# Backend DTO — src/deeplecture/use_cases/dto/bookmark.py
@dataclass
class BookmarkItem:
    id: str               # UUID v4
    timestamp: float      # seconds (float from HTMLVideoElement.currentTime)
    title: str            # auto-filled from subtitle, max 500 chars
    note: str             # plain text, max 50_000 chars
    created_at: datetime
    updated_at: datetime
```

```typescript
// Frontend — frontend/lib/api/bookmarks.ts
export interface BookmarkItem {
    id: string;
    timestamp: number;
    title: string;
    note: string;
    createdAt: string;   // ISO datetime
    updatedAt: string;
}

export interface BookmarkListResponse {
    contentId: string;
    bookmarks: BookmarkItem[];
}
```

### API Design

| Method | Endpoint | Body | Description |
|---|---|---|---|
| GET | `/api/bookmarks?content_id=...` | — | List all bookmarks (sorted by timestamp) |
| POST | `/api/bookmarks` | `{ content_id, timestamp, title, note }` | Create bookmark, returns 201 |
| PUT | `/api/bookmarks/<id>` | `{ content_id, title?, note?, timestamp? }` | Update bookmark fields |
| DELETE | `/api/bookmarks/<id>?content_id=...` | — | Delete bookmark |

> **Note**: Uses `content_id` (snake_case) to match all existing routes.

### Validation Rules

| Field | Type | Constraints |
|---|---|---|
| `id` | string | UUID v4 format (via `validate_uuid`) |
| `content_id` | string | Existing pattern (via `validate_content_id`) |
| `timestamp` | float | `>= 0` (no upper bound — video may be trimmed later) |
| `title` | string | Max 500 chars (via `validate_title`) |
| `note` | string | Max 50,000 chars (via `validate_message` with custom `max_length`) |

---

## Implementation Phases

### Phase 1: Backend — Storage & Domain

#### 1.1 Create `BookmarkStorageProtocol`

**New file:** `src/deeplecture/use_cases/interfaces/bookmark.py`

```python
class BookmarkStorageProtocol(Protocol):
    def load_all(self, content_id: str) -> list[dict[str, Any]]: ...
    def save_all(self, content_id: str, items: list[dict[str, Any]]) -> datetime: ...
    def exists(self, content_id: str) -> bool: ...
```

Uses `list[dict]` (not domain objects) — the use case layer handles DTO conversion.

#### 1.2 Create `BookmarkItem` and DTOs

**New file:** `src/deeplecture/use_cases/dto/bookmark.py`

Three DTOs following the Quiz pattern:
- `BookmarkItem` — internal representation with `to_dict()` / `from_dict()`
- `CreateBookmarkRequest` — `content_id`, `timestamp`, `title`, `note`
- `UpdateBookmarkRequest` — `content_id`, `bookmark_id`, optional `title`, `note`, `timestamp`
- `BookmarkListResult` — `content_id`, `items: list[BookmarkItem]`

#### 1.3 Create `FsBookmarkStorage`

**New file:** `src/deeplecture/infrastructure/repositories/fs_bookmark_storage.py`

Follow the `FsQuizStorage` pattern:
- `NAMESPACE = "bookmarks"`, `FILENAME = "bookmarks.json"`
- Storage path: `content/{content_id}/bookmarks/bookmarks.json`
- Atomic writes: `tempfile.NamedTemporaryFile` + `os.fsync` + `os.replace`
- `threading.Lock` for the read-modify-write cycle (prevents concurrent write race)
- `load_all()` returns `list[dict]` sorted by `timestamp`
- `save_all()` writes entire list atomically

#### 1.4 Create `BookmarkUseCase`

**New file:** `src/deeplecture/use_cases/bookmark.py`

```python
class BookmarkUseCase:
    def __init__(self, *, bookmark_storage: BookmarkStorageProtocol,
                 metadata_storage: MetadataStorageProtocol) -> None: ...

    def list_bookmarks(self, content_id: str) -> BookmarkListResult: ...
    def create_bookmark(self, request: CreateBookmarkRequest) -> BookmarkItem: ...
    def update_bookmark(self, request: UpdateBookmarkRequest) -> BookmarkItem: ...
    def delete_bookmark(self, content_id: str, bookmark_id: str) -> None: ...
```

- `create_bookmark`: generates UUID, sets `created_at` / `updated_at`, appends to list, saves
- `update_bookmark`: finds item by ID, patches fields, updates `updated_at`, saves
- `delete_bookmark`: filters out item by ID, saves; raises domain error if not found
- All methods call `metadata_storage.validate_exists(content_id)` to ensure content exists

#### 1.5 Wire into `__init__` exports

**Modify:**
- `src/deeplecture/use_cases/interfaces/__init__.py` — add `BookmarkStorageProtocol` to imports and `__all__`
- `src/deeplecture/infrastructure/repositories/__init__.py` — add `FsBookmarkStorage`
- `src/deeplecture/infrastructure/__init__.py` — add `FsBookmarkStorage`

---

### Phase 2: Backend — API Route & DI

#### 2.1 Create bookmark route blueprint

**New file:** `src/deeplecture/presentation/api/routes/bookmark.py`

```python
bp = Blueprint("bookmarks", __name__)

@bp.route("", methods=["GET"])
@handle_errors
def list_bookmarks() -> Response:
    content_id = validate_content_id(request.args.get("content_id"))
    result = get_container().bookmark_usecase.list_bookmarks(content_id)
    return success(result.to_dict())

@bp.route("", methods=["POST"])
@handle_errors
def create_bookmark() -> Response:
    data = request.get_json(silent=True) or {}
    # validate content_id, timestamp, title, note
    result = get_container().bookmark_usecase.create_bookmark(req)
    return created(result.to_dict())

@bp.route("/<bookmark_id>", methods=["PUT"])
@handle_errors
def update_bookmark(bookmark_id: str) -> Response:
    bookmark_id = validate_uuid(bookmark_id, field_name="bookmark_id")
    data = request.get_json(silent=True) or {}
    # validate fields, call use case
    return success(result.to_dict())

@bp.route("/<bookmark_id>", methods=["DELETE"])
@handle_errors
def delete_bookmark(bookmark_id: str) -> Response:
    bookmark_id = validate_uuid(bookmark_id, field_name="bookmark_id")
    content_id = validate_content_id(request.args.get("content_id"))
    get_container().bookmark_usecase.delete_bookmark(content_id, bookmark_id)
    return success({"deleted": True})
```

#### 2.2 Wire DI container

**Modify:** `src/deeplecture/di/container.py`

Add two cached properties:
```python
@property
def bookmark_storage(self) -> FsBookmarkStorage:
    if "bookmark_storage" not in self._cache:
        self._cache["bookmark_storage"] = FsBookmarkStorage(self.path_resolver)
    return self._cache["bookmark_storage"]

@property
def bookmark_usecase(self) -> BookmarkUseCase:
    if "bookmark_uc" not in self._cache:
        self._cache["bookmark_uc"] = BookmarkUseCase(
            bookmark_storage=self.bookmark_storage,
            metadata_storage=self.metadata_storage,
        )
    return self._cache["bookmark_uc"]
```

#### 2.3 Register blueprint

**Modify:**
- `src/deeplecture/presentation/api/routes/__init__.py` — add `bookmark_bp`
- `src/deeplecture/presentation/api/app.py` — `app.register_blueprint(bookmark_bp, url_prefix="/api/bookmarks")`

---

### Phase 3: Frontend — Tab Registration & API Client

#### 3.1 Add `"bookmarks"` to tab system

**Modify:** `frontend/stores/tabLayoutStore.ts`
- Add `"bookmarks"` to `TabId` union type
- Add `"bookmarks"` to `DEFAULT_BOTTOM_TABS` array
- Bump `MAX_BOTTOM_TABS` from `8` to `10`

**Modify:** `frontend/components/dnd/DraggableTabBar.tsx`
- Import `Bookmark` from `lucide-react`
- Add `bookmarks: { label: "Bookmarks", icon: <Bookmark className="w-4 h-4" /> }` to `TAB_CONFIG`

#### 3.2 Create API client

**New file:** `frontend/lib/api/bookmarks.ts`

```typescript
import { api } from "./client";

export interface BookmarkItem { ... }
export interface BookmarkListResponse { ... }

export const listBookmarks = async (contentId: string): Promise<BookmarkListResponse> => {
    const response = await api.get<BookmarkListResponse>("/bookmarks", {
        params: { contentId },
    });
    return response.data;
};

export const createBookmark = async (
    contentId: string, timestamp: number, title: string, note: string
): Promise<BookmarkItem> => {
    const response = await api.post<BookmarkItem>("/bookmarks", {
        content_id: contentId, timestamp, title, note,
    });
    return response.data;
};

export const updateBookmark = async (
    id: string, contentId: string, updates: Partial<Pick<BookmarkItem, "title" | "note" | "timestamp">>
): Promise<BookmarkItem> => {
    const response = await api.put<BookmarkItem>(`/bookmarks/${id}`, {
        content_id: contentId, ...updates,
    });
    return response.data;
};

export const deleteBookmark = async (id: string, contentId: string): Promise<void> => {
    await api.delete(`/bookmarks/${id}`, { params: { contentId } });
};
```

**Modify:** `frontend/lib/api/index.ts` — add re-exports for bookmark API functions and types.

---

### Phase 4: Frontend — BookmarkTab Component

#### 4.1 Create `BookmarkTab`

**New file:** `frontend/components/features/BookmarkTab.tsx`

**Structure:**

```
BookmarkTab
├── Header: "Bookmarks" title + [+ Add Bookmark] button
├── Empty state (when 0 bookmarks)
├── Bookmark list (sorted by timestamp)
│   └── BookmarkRow (for each item)
│       ├── Timestamp badge (clickable → onSeek)
│       ├── Title (inline-editable)
│       ├── Note preview (truncated, click to expand)
│       ├── Expanded note editor (textarea, shown on expand)
│       └── Delete button (with confirmation)
└── Delete confirmation dialog
```

**Props:**
```typescript
interface BookmarkTabProps {
    videoId: string;
    currentTime: number;
    onSeek: (time: number) => void;
    subtitles?: Subtitle[];        // for auto-fill title
}
```

**Key behaviors:**
- `useState` + `useEffect` for initial fetch via `listBookmarks(videoId)`
- "Add Bookmark" captures `currentTime`, auto-fills title from `getActiveSubtitles(subtitles, currentTime)`
- Fallback title: `"Bookmark at {formatTime(timestamp)}"` when no subtitles
- Note editing uses a plain `<textarea>` (lightweight), with debounced `updateBookmark` on change
- Active bookmark: highlight row where `timestamp` is the largest value `<= currentTime` (most recently passed)
- Auto-scroll active row into view during playback
- Delete shows confirmation dialog before calling `deleteBookmark`

#### 4.2 Register in TabContentRenderer

**Modify:** `frontend/components/video/TabContentRenderer.tsx`

```typescript
// Add dynamic import
const BookmarkTab = dynamic(
    () => import("@/components/features/BookmarkTab").then((mod) => mod.BookmarkTab),
    { loading: LoadingSpinner }
);

// Add case in switch
case "bookmarks":
    return (
        <BookmarkTab
            videoId={videoId}
            currentTime={currentTime}
            onSeek={onSeek}
            subtitles={subtitlesSource}
        />
    );
```

**Note:** `BookmarkTab` needs `currentTime` (for active highlighting and bookmark creation) and `subtitles` (for auto-fill). These are already available in `TabContentProps`.

---

### Phase 5: Frontend — Progress Bar Markers

#### 5.1 Add bookmark markers overlay to VideoProgressBar

**Modify:** `frontend/components/video/VideoProgressBar.tsx`

Add an optional `bookmarks` prop:

```typescript
interface VideoProgressBarProps {
    currentTime: number;
    duration: number;
    onSeek: (time: number) => void;
    bufferTime?: number;
    className?: string;
    bookmarkTimestamps?: number[];  // NEW — list of bookmark timestamps
}
```

Render an overlay `<div>` inside the `video-progress-bar-wrapper`:

```tsx
<div className="video-progress-bar-wrapper w-full overflow-visible relative">
    <VideoSeekSlider ... />
    {bookmarkTimestamps && bookmarkTimestamps.length > 0 && duration > 0 && (
        <div className="absolute inset-0 pointer-events-none">
            {bookmarkTimestamps.map((ts, i) => (
                <div
                    key={i}
                    className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-yellow-400 border border-yellow-600"
                    style={{ left: `${(ts / duration) * 100}%` }}
                />
            ))}
        </div>
    )}
</div>
```

Key design choices:
- `pointer-events: none` — dots don't interfere with seek drag
- `bg-yellow-400` — distinct color that stands out against the progress bar
- `w-2 h-2` (8px) — visible but not obtrusive
- Dots are positioned as percentage of duration

#### 5.2 Thread bookmarks data through to VideoPlayer

**Modify:** `frontend/components/video/VideoPlayer.tsx`
- Add `bookmarkTimestamps?: number[]` to `VideoPlayerProps`
- Pass it through to `<VideoControls>` → `<VideoProgressBar>`

**Modify:** `frontend/components/video/VideoControls.tsx`
- Add `bookmarkTimestamps?: number[]` to props
- Pass to `<VideoProgressBar bookmarkTimestamps={bookmarkTimestamps} />`

**Modify:** `frontend/app/video/[id]/VideoPageClient.tsx`
- Fetch bookmarks at page level (or lift from BookmarkTab state via a small Zustand store or shared state)
- Pass `bookmarkTimestamps` to `<VideoPlayer>`

---

### Phase 6: Frontend — Keyboard Shortcut

#### 6.1 Add `B` key shortcut

**Modify:** `frontend/components/video/VideoPlayer.tsx`

In the existing `handleKeyDown` handler (around line 178-223):

```typescript
case "b":
case "B":
    if (onAddBookmark) {
        onAddBookmark(currentTimeRef.current);
    }
    break;
```

**Add to `VideoPlayerProps`:**
```typescript
onAddBookmark?: (time: number) => void;
```

Wire `onAddBookmark` from the video page level to create a bookmark at the current time.

---

## Acceptance Criteria

### Functional Requirements

- [x] User can add a bookmark at the current video playback time
- [x] Bookmark title is auto-filled from the nearest subtitle (or fallback to "Bookmark at X:XX")
- [x] Bookmark title is editable inline
- [x] User can attach/edit a plain-text note on each bookmark (textarea)
- [x] Clicking a bookmark's timestamp seeks the video to that position
- [x] Bookmarks are listed sorted by timestamp ascending
- [x] The nearest past bookmark is highlighted during playback
- [x] User can delete a bookmark with confirmation dialog
- [x] Bookmarks appear as yellow dots on the video progress bar
- [x] `B` key adds a bookmark at the current time
- [x] Bookmarks tab appears in the bottom panel and is draggable
- [x] Bookmarks persist across page reloads (server-side JSON storage)

### Non-Functional Requirements

- [x] `MAX_BOTTOM_TABS` bumped to 10 to accommodate new tab
- [x] Backend uses atomic writes with threading lock
- [x] Backend validates all inputs (UUID, content_id, timestamp >= 0, title <= 500, note <= 50000)
- [x] Frontend uses `next/dynamic` for lazy-loading BookmarkTab
- [x] Progress bar markers use `pointer-events: none` to not interfere with seeking

### Quality Gates

- [x] Backend unit tests for `BookmarkUseCase` (CRUD operations, validation)
- [x] Backend unit tests for `FsBookmarkStorage` (load, save, atomic write)
- [x] Frontend: BookmarkTab renders empty state, list, active highlight
- [x] No TypeScript errors, no Python type check errors

---

## Files Summary

### New Files (7)

| # | File | Purpose |
|---|---|---|
| 1 | `src/deeplecture/use_cases/interfaces/bookmark.py` | `BookmarkStorageProtocol` |
| 2 | `src/deeplecture/use_cases/dto/bookmark.py` | DTOs: BookmarkItem, Create/Update requests, ListResult |
| 3 | `src/deeplecture/use_cases/bookmark.py` | `BookmarkUseCase` (CRUD) |
| 4 | `src/deeplecture/infrastructure/repositories/fs_bookmark_storage.py` | JSON filesystem storage with lock |
| 5 | `src/deeplecture/presentation/api/routes/bookmark.py` | Flask blueprint (GET/POST/PUT/DELETE) |
| 6 | `frontend/lib/api/bookmarks.ts` | API client functions + types |
| 7 | `frontend/components/features/BookmarkTab.tsx` | Tab component (list + CRUD + active highlight) |

### Modified Files (10)

| # | File | Change |
|---|---|---|
| 8 | `src/deeplecture/use_cases/interfaces/__init__.py` | Export `BookmarkStorageProtocol` |
| 9 | `src/deeplecture/infrastructure/repositories/__init__.py` | Export `FsBookmarkStorage` |
| 10 | `src/deeplecture/infrastructure/__init__.py` | Export `FsBookmarkStorage` |
| 11 | `src/deeplecture/presentation/api/routes/__init__.py` | Export `bookmark_bp` |
| 12 | `src/deeplecture/di/container.py` | Add `bookmark_storage` + `bookmark_usecase` properties |
| 13 | `src/deeplecture/presentation/api/app.py` | Register blueprint at `/api/bookmarks` |
| 14 | `frontend/stores/tabLayoutStore.ts` | Add `"bookmarks"` to `TabId`, `DEFAULT_BOTTOM_TABS`, bump max to 10 |
| 15 | `frontend/components/dnd/DraggableTabBar.tsx` | Add `bookmarks` to `TAB_CONFIG` |
| 16 | `frontend/components/video/TabContentRenderer.tsx` | Add dynamic import + switch case |
| 17 | `frontend/lib/api/index.ts` | Re-export bookmark API |

### Modified Files — Progress Bar Integration (3)

| # | File | Change |
|---|---|---|
| 18 | `frontend/components/video/VideoProgressBar.tsx` | Add `bookmarkTimestamps` prop + overlay dots |
| 19 | `frontend/components/video/VideoControls.tsx` | Thread `bookmarkTimestamps` to progress bar |
| 20 | `frontend/components/video/VideoPlayer.tsx` | Add `bookmarkTimestamps` + `onAddBookmark` props, `B` key handler |

### Test Files (2)

| # | File | Purpose |
|---|---|---|
| 21 | `tests/unit/use_cases/test_bookmark.py` | BookmarkUseCase unit tests |
| 22 | `tests/unit/infrastructure/repositories/test_fs_bookmark_storage.py` | Storage unit tests |

**Total: 7 new + 13 modified + 2 test = 22 files**

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Note editor | Plain textarea (not Milkdown) | Performance — Milkdown is too heavy for N instances in a list |
| Tab capacity | Bump `MAX_BOTTOM_TABS` to 10 | Simplest fix, horizontal scroll already supported |
| Delete UX | Confirmation dialog | Prevents accidental loss of notes |
| Keyboard shortcut | `B` key | Consistent with existing single-key shortcuts (Space, T) |
| Active highlight | Largest `timestamp <= currentTime` | "Most recently passed" is most intuitive during playback |
| API params | `content_id` (snake_case) | Matches all existing routes |
| Timestamp type | float | Matches `HTMLVideoElement.currentTime` precision |
| Concurrency | `threading.Lock` on storage | Prevents read-modify-write race on single JSON file |
| Progress bar markers | Overlay div with `pointer-events: none` | Does not interfere with `react-video-seek-slider` seek drag |

---

## Dependencies & Risks

| Risk | Mitigation |
|---|---|
| Progress bar overlay may visually clash with seek slider styling | Use small (8px) yellow dots, test across themes |
| `B` key may conflict with future shortcuts | Check for conflicts; key handler already skips when typing in inputs |
| Large bookmark count (100+) could slow list rendering | Unlikely for typical use; add virtual scrolling later if needed |
| Corrupted `bookmarks.json` | Wrap `json.loads` in try/except, return empty list on parse error |

---

## References

### Internal References
- Brainstorm: `docs/brainstorms/2026-02-12-video-bookmarks-brainstorm.md`
- Note route pattern: `src/deeplecture/presentation/api/routes/note.py`
- Quiz storage pattern: `src/deeplecture/infrastructure/repositories/fs_quiz_storage.py`
- Tab system: `frontend/stores/tabLayoutStore.ts`
- Progress bar: `frontend/components/video/VideoProgressBar.tsx`
- Subtitle search: `frontend/lib/subtitleSearch.ts` (`getActiveSubtitles`)
- Validation helpers: `src/deeplecture/presentation/api/shared/validation.py`
