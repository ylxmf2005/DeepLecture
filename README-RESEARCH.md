# Cascading Configuration System - Complete Research Index

**Research Date:** 2026-02-10
**Status:** Complete and Ready for Implementation
**Total Materials:** 57 KB across 4 comprehensive guides

---

## Start Here

### For Quick Understanding (5-10 minutes)
📖 **[QUICK-START-GUIDE.md](./QUICK-START-GUIDE.md)**
- 30-second overview of the 3-level cascade
- Why this system matters
- Architecture overview
- Data flow examples
- FAQ

### For Complete Design Details (20-30 minutes)
📖 **[docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md](./docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md)**
- Full design rationale
- Task parameter matrix (13 tasks × 6 configurable dimensions)
- Configuration scoping decisions
- 3-level hierarchy specification
- Open questions and answers
- Industry reference (VS Code, Premiere Pro, Descript)

---

## Implementation Resources

### For Implementation Planning (15 minutes)
📋 **[IMPLEMENTATION-CHECKLIST.md](./IMPLEMENTATION-CHECKLIST.md)**
- Detailed backend checklist (domain, persistence, API)
- Detailed frontend checklist (state, components, integration)
- Testing checklist (unit, integration, E2E)
- Data flow diagrams
- Implementation timeline (4 weeks)

### For Coding Reference (As Needed)
💻 **[CODE-STRUCTURE-REFERENCE.md](./CODE-STRUCTURE-REFERENCE.md)**
- Exact file locations (12 files to create, 15 files to update)
- SQLite schema changes
- Type definitions (Python and TypeScript)
- Code examples and integration patterns
- Deployment considerations

---

## Research & Architecture

### For Comprehensive Research Summary (15-20 minutes)
📚 **[RESEARCH-CASCADING-CONFIG.md](./RESEARCH-CASCADING-CONFIG.md)**
- Findings from codebase exploration
- Global settings store structure
- ContentMetadata entity details
- Task system architecture overview
- Recommended implementation path
- File locations reference

### For Understanding Task Architecture (Optional, 30 minutes)
📚 **[docs/architecture/task-system-overview.md](./docs/architecture/task-system-overview.md)** (850 lines)
- 13 task types
- State machine (PENDING → PROCESSING → READY/ERROR)
- Complete data flow with code paths
- Persistence layer (SQLite WAL mode, snapshots)
- SSE implementation (Subscribe-Then-Snapshot pattern)
- Frontend hooks and state management
- Exception scenarios and recovery

### For Task System Architectural Decisions (Optional, 10 minutes)
📚 **[docs/architecture/task-state-and-sse.md](./docs/architecture/task-state-and-sse.md)**
- Why SQLite (not event sourcing)
- Why ThreadPoolExecutor (not Celery)
- Why native EventSource (not manual retry)
- Why snapshot-based persistence

---

## The Three-Level Cascade

```
Per-Task Invocation Overrides (highest priority)
    ↓ falls through if not set
Per-Video Configuration (backend-persisted)
    ↓ falls through if not set
Global User Defaults (localStorage)
```

**Each level is optional** — if not set, cascade falls through to next level.

---

## What Gets Cascaded

| Setting | Type | Storage | Level |
|---------|------|---------|-------|
| Source language | string | Backend | Per-video |
| Target language | string | Backend | Per-video |
| LLM model | string | Backend | Per-video |
| TTS model | string | Backend | Per-video |
| Prompts | dict | Backend | Per-video |
| Note context mode | enum | Backend | Per-video |

**NOT cascaded** (stays global):
- Playback behavior (autopause, autoresume, summary threshold)
- Subtitle display (font size, bottom offset, repeat count)
- Notifications (toast, browser, title flash)
- Layout (sidebar visibility, view mode)
- Dictionary settings (enabled, interaction mode)
- Live2D appearance (model path, position, scale)
- Learner profile (global for now, can be per-video in Phase 2)

---

## Implementation Phases

### Phase 1: Backend Infrastructure (2-3 days)
```python
# Extend ContentMetadata
config_overrides: dict[str, Any]

# Create ConfigResolution service
class ConfigResolution:
    def resolve(global_config, video_config, task_overrides):
        # Cascade with nullish coalescing

# Add API endpoints
GET    /api/content/{id}/config       # Fetch overrides
PUT    /api/content/{id}/config       # Update overrides
DELETE /api/content/{id}/config       # Reset to global
```

### Phase 2: Frontend Integration (1-2 days)
```typescript
// Resolution hook
const config = useConfigResolution(contentId, taskOverrides);

// State management
const videoConfig = useVideoConfig(contentId);

// Task handlers
generateSubtitles(contentId, { config_overrides: {...} });
```

### Phase 3: UI Components (2-3 days)
```typescript
// Per-video settings
<VideoSettingsPanel />

// Pre-task overrides
<PreTaskConfigPopover />

// Updated global settings
<SettingsDialog /> // Add clarifying text
```

### Phase 4: Testing & Polish (1-2 days)
- Unit tests (config cascade logic)
- Integration tests (API endpoints)
- E2E tests (user flows)

---

## Key Design Decisions

| Decision | Why |
|----------|-----|
| **3-level cascade** | Only store what's different. Auto-propagation. Easy reset. Familiar pattern. |
| **Backend-persisted** | Survives browser clears. Multi-device access. Config lives with content. |
| **Partial overrides** | Minimal storage. Clear inheritance. No duplication. |
| **Separate UI** | Keeps settings uncluttered. Makes it clear what you're configuring. |
| **Optional popover** | Doesn't slow casual users. Lets power users tweak. |

---

## Getting Started

### 1. Read the Design
Start with **QUICK-START-GUIDE.md** (5 min) to understand the concept.

Then read **docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md** for full design.

### 2. Plan Your Work
Use **IMPLEMENTATION-CHECKLIST.md** to plan tasks and track progress.

### 3. Implement Phase 1
Use **CODE-STRUCTURE-REFERENCE.md** for exact file locations and code examples.

Focus on:
- Extending ContentMetadata
- Creating ConfigResolution service
- Adding API endpoints
- Thorough testing of cascade logic

### 4. Implement Phase 2 & 3
Wire frontend to backend.
Add UI components.
Test end-to-end.

---

## Files to Create

**Backend (Python):**
1. `/src/deeplecture/use_cases/config_resolution.py` — Cascade logic
2. `/src/deeplecture/presentation/api/routes/config.py` — API endpoints

**Frontend (TypeScript):**
3. `/frontend/hooks/useConfigResolution.ts` — Resolution hook
4. `/frontend/hooks/useVideoConfig.ts` — Fetch/cache config
5. `/frontend/components/video/VideoSettingsPanel.tsx` — Per-video UI
6. `/frontend/components/video/PreTaskConfigPopover.tsx` — Task overrides UI
7. `/frontend/lib/api/config.ts` — API client

**Tests:**
8. `/tests/unit/use_cases/test_config_resolution.py` — Cascade logic tests
9. `/tests/integration/test_config_api.py` — API endpoint tests

---

## Files to Update

**Backend:**
- `/src/deeplecture/domain/entities/content.py` — Add config_overrides field
- `/src/deeplecture/infrastructure/repositories/sqlite_metadata.py` — Persist config
- `/src/deeplecture/di/container.py` — Wire ConfigResolution service

**Frontend:**
- `/frontend/stores/types.ts` — Add cascading config types
- `/frontend/hooks/useVideoPageState.ts` — Fetch video config
- `/frontend/hooks/handlers/use*Handlers.ts` — Include config in task calls
- `/frontend/lib/api/*.ts` — Accept config_overrides param
- `/frontend/components/dialogs/SettingsDialog.tsx` — Clarify these are defaults
- `/frontend/components/video/TabContentRenderer.tsx` — Add settings tab

---

## Testing Strategy

### Unit Tests (Fast)
- Config resolution cascade logic
- Each parameter type
- Null/undefined handling

### Integration Tests
- Config API endpoints (GET/PUT/DELETE)
- Task submission with config
- Database persistence

### E2E Tests
- User can view per-video config
- User can set overrides
- User can reset to defaults
- Task uses correct resolved config

---

## Success Criteria

- User can view current config for a video (showing inherited vs overridden)
- User can set per-video overrides (language, model, etc.)
- User can reset per-video override to use global default
- Task uses correct resolved config (cascade works correctly)
- Per-video config persists across browser refresh
- Multiple videos can have different configs simultaneously
- System is backward compatible (old clients still work)

---

## No Surprises

✅ Clear data flow
✅ Well-tested patterns (Zustand, FastAPI, SSE)
✅ Non-breaking schema change (add column, default NULL)
✅ Backward compatible
✅ No external dependencies
✅ Existing tests remain valid

---

## Timeline

**Week 1:** Backend infrastructure
**Week 2:** Frontend integration
**Week 3:** UI components
**Week 4:** Testing & polish

**Total: 3-4 weeks** (depending on team size and parallel work)

---

## Questions?

| Question | Answer |
|----------|--------|
| Where do I start? | QUICK-START-GUIDE.md |
| What's the full design? | docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md |
| How do I implement this? | CODE-STRUCTURE-REFERENCE.md |
| What should I code next? | IMPLEMENTATION-CHECKLIST.md |
| How does config cascade work? | See `ConfigResolution.resolve()` in CODE-STRUCTURE-REFERENCE.md |
| Can learner profile be per-video? | Yes, Phase 2. Currently global only. |
| What about backward compatibility? | Fully compatible. Old clients use global settings. |

---

## Document Locations

All documents are in repository root or `/docs/`:

```
/QUICK-START-GUIDE.md                                    ← START HERE
/RESEARCH-CASCADING-CONFIG.md                            ← Full findings
/IMPLEMENTATION-CHECKLIST.md                             ← What to build
/CODE-STRUCTURE-REFERENCE.md                             ← Where & how
/docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md  ← Design
/docs/architecture/task-system-overview.md               ← Task system (850 lines)
/docs/architecture/task-state-and-sse.md                 ← Architectural decisions
```

---

## Research Methodology

This research followed institutional knowledge best practices:

1. **Extracted keywords** from feature description (cascading, config, per-video, global)
2. **Narrowed to relevant directories** (docs/brainstorms/, docs/architecture/)
3. **Pre-filtered with Grep** to find candidate files
4. **Read frontmatter and relevant sections** (design docs already existed)
5. **Traced code structure** (ContentMetadata, GlobalSettings store, Task system)
6. **Synthesized findings** into actionable implementation guides
7. **Created comprehensive reference materials** for the team

**Result:** Complete roadmap with no surprises, clear file locations, working code examples, and test strategies.

---

**Status:** Ready to implement. All research complete. No blockers identified.
