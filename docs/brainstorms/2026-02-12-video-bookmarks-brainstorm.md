# Brainstorm: Video Bookmarks Module

**Date:** 2026-02-12
**Status:** Approved
**Author:** Jason

---

## What We're Building

A **Bookmarks** tab module that allows users to mark specific timestamps in a video, attach Markdown notes to each bookmark, and jump to bookmarked positions with one click. Bookmarks are also visually displayed as markers on the video player's progress bar for at-a-glance navigation.

### Core Capabilities

1. **Add bookmark** at the current video playback time
2. **Auto-fill title** from the nearest subtitle at that timestamp (user can edit)
3. **Attach Markdown notes** to each bookmark (using Milkdown editor, reusing `MarkdownNoteEditor`)
4. **Click to seek** — clicking a bookmark row jumps the video to that timestamp
5. **Progress bar markers** — bookmarks are displayed as small indicator dots on the video player's seek bar
6. **Highlight active bookmark** — the nearest bookmark to the current playback time is highlighted in the list
7. **CRUD operations** — create, read, update, delete bookmarks
8. **Sorted by timestamp** — list is always ordered by video time position

---

## Why This Approach

**Chosen approach: Minimal CRUD + Timeline Integration (Progress Bar Markers)**

- **CRUD foundation** follows the exact same 6-layer vertical slice pattern as every other module (Note, Quiz, Cheatsheet, etc.), ensuring consistency and minimal learning curve
- **Progress bar markers** provide the most direct visual value — users can see all bookmarked positions without switching tabs
- **Markdown notes** (instead of plain text) leverage the existing Milkdown editor component and give users rich formatting for their annotations
- **Auto-fill from subtitles** reduces friction: most users just want to mark "this moment" without typing a title

### What We're NOT Building (YAGNI)

- No tag/label/color categorization system (can be added later)
- No AI-generated bookmark suggestions
- No bookmark sharing or export
- No bookmark search/filter (list is small enough to scan)

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Title source | Auto-fill from subtitle + editable | Best UX: low friction but flexible |
| Note editor | Markdown (Milkdown) | Reuses `MarkdownNoteEditor`, richer than plain text |
| Default panel | Bottom bar | Consistent with other content tabs (Notes, Quiz, etc.) |
| List sorting | By timestamp ascending | Natural video timeline order |
| Active highlight | Highlight nearest bookmark to `currentTime` | Mirrors Subtitle/Timeline behavior |
| Storage format | JSON file | Structured data (id, timestamp, title, note, dates) |
| Progress bar | Marker dots on seek bar | Core differentiator — visual at-a-glance navigation |

---

## Data Model

```typescript
// Frontend
interface BookmarkItem {
    id: string;            // UUID
    timestamp: number;     // seconds into the video
    title: string;         // auto-filled from subtitle, editable
    note: string;          // Markdown content
    createdAt: string;     // ISO datetime
    updatedAt: string;     // ISO datetime
}
```

```python
# Backend DTO
@dataclass
class BookmarkItem:
    id: str              # UUID
    timestamp: float     # seconds
    title: str
    note: str
    created_at: datetime
    updated_at: datetime
```

**Storage path:** `content/{content_id}/bookmarks/bookmarks.json`

---

## API Design

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/bookmarks?contentId=...` | List all bookmarks for a video |
| POST | `/api/bookmarks` | Create a new bookmark |
| PUT | `/api/bookmarks/<id>` | Update bookmark title/note/timestamp |
| DELETE | `/api/bookmarks/<id>` | Delete a bookmark |

---

## Architecture — Files to Create/Modify

### Backend — New Files

1. `src/deeplecture/use_cases/interfaces/bookmark.py` — `BookmarkStorageProtocol`
2. `src/deeplecture/infrastructure/repositories/fs_bookmark_storage.py` — JSON filesystem storage
3. `src/deeplecture/use_cases/dto/bookmark.py` — Request/Response DTOs
4. `src/deeplecture/use_cases/bookmark.py` — `BookmarkUseCase` (CRUD)
5. `src/deeplecture/presentation/api/routes/bookmark.py` — Flask blueprint

### Backend — Modified Files

6. `src/deeplecture/use_cases/interfaces/__init__.py` — export protocol
7. `src/deeplecture/infrastructure/repositories/__init__.py` — export storage
8. `src/deeplecture/presentation/api/routes/__init__.py` — export blueprint
9. `src/deeplecture/di/container.py` — wire up storage + use case
10. `src/deeplecture/presentation/api/app.py` — register blueprint

### Frontend — New Files

11. `frontend/components/features/BookmarkTab.tsx` — Tab component (list + add/edit/delete)
12. `frontend/lib/api/bookmark.ts` — API client functions

### Frontend — Modified Files

13. `frontend/stores/tabLayoutStore.ts` — Add `"bookmarks"` to `TabId`
14. `frontend/components/dnd/DraggableTabBar.tsx` — Add to `TAB_CONFIG`
15. `frontend/components/video/TabContentRenderer.tsx` — Add `case "bookmarks"`
16. `frontend/lib/api/index.ts` — Re-export bookmark API
17. `frontend/components/video/VideoPlayer.tsx` — Add bookmark marker dots on progress bar

---

## UX Sketch

### Bookmark Tab (Bottom Panel)

```
┌─────────────────────────────────────────────┐
│ [+ Add Bookmark]                            │
├─────────────────────────────────────────────┤
│ ▶ 02:15  Introduction to Neural Networks    │  ← highlighted (nearest)
│          "Key concept: backpropagation..."   │
├─────────────────────────────────────────────┤
│   05:42  Loss Function Explained            │
│          "Remember: MSE vs Cross-entropy..." │
├─────────────────────────────────────────────┤
│   12:30  Gradient Descent Visualization     │
│          (no note)                           │
└─────────────────────────────────────────────┘
```

### Video Player Progress Bar

```
[====●========●===========●=======]
     ↑        ↑           ↑
   02:15    05:42       12:30  ← bookmark markers
```

---

## Open Questions

- None at this time. All key decisions have been made.
