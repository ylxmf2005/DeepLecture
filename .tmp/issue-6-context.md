# Context Summary: Quiz Feature Implementation

## Feature Understanding
**Intent**: Implement a Quiz feature that generates quiz questions from video content, following DRY principles by reusing existing AI functionality (especially learning from the cheatsheet implementation), and using a well-researched quiz generation algorithm.

**Scope signals**: "Quiz", "AI functionality", "DRY", "algorithm", "feature", mentions in README.md roadmap showing Quiz as a planned feature alongside Flashcard and Cheatsheet.

## Relevant Files

### Source Files
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/cheatsheet.py` — Two-stage LLM pipeline (extraction + rendering) pattern that can be adapted for quiz generation. Shows context loading from subtitles, structured data extraction, and storage patterns.
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/note.py` — Multi-part content generation with parallel execution, shows outline-then-details pattern and context loading from both subtitles and slides.
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/explanation.py` — Shows simpler single-stage generation pattern with subtitle context extraction.
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/timeline.py` — Two-stage pipeline (segmentation + explanation) with parallel processing, similar architecture to what quiz might need.
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/ask.py` — Shows conversation history management and context building patterns.

### Documentation
- `/Users/EthanLee/Desktop/CourseSubtitle/README.md` — Shows Quiz listed in roadmap (line 106) as high-priority planned feature: "AI 根据视频内容生成测验题".
- `/Users/EthanLee/Desktop/CourseSubtitle/CLAUDE.md` — Clean Architecture structure with 4 layers: entities, use_cases, infrastructure, presentation. Quiz would follow same pattern.
- `/Users/EthanLee/Desktop/CourseSubtitle/plan.json` — Shows previous Report feature planning mentioned Quiz as one of report types, indicating quiz generation was already conceptually designed.
- `/Users/EthanLee/Desktop/CourseSubtitle/docs/README.md` — Feature organization patterns.

### Tests
- No existing quiz-specific tests found (feature not yet implemented).

### Configuration
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/di/container.py` — Shows DI pattern for registering new use cases (lines 490-499 show cheatsheet_usecase registration as reference).
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/prompts/cheatsheet.py` — Shows two-stage prompt structure that quiz can learn from.
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/cheatsheet.py` — Shows API route pattern with GET/POST/generate endpoints and async task submission.

## Architecture Context

### Existing Patterns
- **Two-stage LLM pipeline**: Cheatsheet uses extraction (structured items) then rendering (formatted output). Timeline uses segmentation then explanation. Quiz should follow similar pattern: question generation then answer/distractor generation or question extraction then validation/refinement.
- **Context loading from subtitles**: All features use `SubtitleStorageProtocol` and helper functions in `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/shared/subtitle.py` to load subtitle context.
- **Storage Protocol pattern**: Each feature defines a Protocol interface (e.g., `CheatsheetStorageProtocol` in `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/cheatsheet.py`) and filesystem implementation (e.g., `FsCheatsheetStorage`).
- **DTO pattern**: Request/Response DTOs in `use_cases/dto/` directory for type safety (e.g., `GenerateCheatsheetRequest`, `CheatsheetResult`).
- **Async task execution**: Long-running generation tasks use `TaskManager.submit()` with SSE notifications (line 108-118 in cheatsheet route).
- **Parallel execution**: Features use `ParallelRunnerProtocol` for fan-out LLM calls (note generation does this for parts, timeline for explanations).
- **Frontend tab pattern**: CheatsheetTab.tsx shows the complete frontend pattern: loading state, generation trigger, edit mode, SSE refresh handling.

### Integration Points
- **Use Case Layer**: Create `QuizUseCase` in `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/quiz.py`.
- **DTO Layer**: Create `quiz.py` in `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/dto/`.
- **Storage Interface**: Create `quiz.py` in `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/`.
- **Storage Implementation**: Create `fs_quiz_storage.py` in `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/`.
- **Prompts**: Create `quiz.py` in `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/prompts/`.
- **API Routes**: Create `quiz.py` in `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/`.
- **DI Container**: Register quiz_usecase and quiz_storage in container.py.
- **Frontend**: Create `QuizTab.tsx` in `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/`.

## Constraints Discovered
- Must follow Clean Architecture: domain entities separate from use cases, use cases depend on protocols not implementations (CLAUDE.md).
- Must use existing `SubtitleStorageProtocol` for context loading, not create custom subtitle access (DRY principle).
- Prompts should use `PromptRegistryProtocol` for flexibility (seen in ExplanationUseCase line 53, NoteUseCase line 59).
- Must use `LLMProviderProtocol` for runtime model selection, not hardcode LLM client (container.py lines 294-308).
- Storage must use atomic writes with tempfile (seen in FsCheatsheetStorage lines 84-100).
- Frontend must handle SSE events for async task completion (CheatsheetTab.tsx lines 38-104).
- API routes must use `@handle_errors` decorator and validation helpers (cheatsheet.py lines 25, 11-15).
- No emojis in code or user-facing messages (CLAUDE.md).
- Git commits should not include Co-author or "Generated with Claude Code" (CLAUDE.md).

## Recommended Focus Areas for Bold-Proposer
- **Quiz algorithm research**: Investigate SOTA quiz generation algorithms (e.g., Bloom's taxonomy-based question generation, distractor generation techniques, difficulty calibration, spaced repetition integration). This requires external research beyond the codebase.
- **Question type taxonomy**: Design a structured taxonomy (multiple choice, true/false, fill-in-blank, short answer) with quality metrics.
- **DRY opportunities**: Identify how to reuse cheatsheet's two-stage pattern but adapt for quiz-specific needs (e.g., question validation stage, distractor quality checks).
- **Interactive quiz format**: Consider if quiz should be static Markdown or interactive JSON format with scoring/feedback (architectural decision).
- **Quality assurance**: Research how to validate generated quiz questions for clarity, difficulty balance, and educational value.
- **Integration with learning science**: Consider spaced repetition scheduling, difficulty adaptation, and learning analytics.

## Complexity Estimation

**Estimated LOC**: ~650-800 (Large)

**Breakdown**:
- Use case (`quiz.py`): ~200-250 LOC (two-stage pipeline + validation + parallel execution)
- DTOs (`dto/quiz.py`): ~100-120 LOC (QuizRequest, QuizResult, QuestionItem, etc.)
- Storage interface + impl: ~80-100 LOC (protocol + filesystem storage)
- Prompts (`prompts/quiz.py`): ~100-150 LOC (question generation prompts + answer/distractor generation)
- API routes (`routes/quiz.py`): ~80-100 LOC (GET/POST/generate endpoints)
- DI container registration: ~20-30 LOC
- Frontend QuizTab: ~250-300 LOC (interactive quiz UI more complex than cheatsheet viewer)
- Documentation updates: ~20-30 LOC

**Lite path checklist**:
- [ ] All knowledge within repo (no internet research needed): **No** - Quiz generation algorithms, question taxonomy design, distractor generation techniques, and educational assessment best practices require SOTA research.
- [ ] Files affected < 5: **No** - Estimated 8-10 files (use case, dto, interface, storage, prompts, route, container, frontend component, docs).
- [ ] LOC < 150: **No** - Estimated 650-800 LOC total.

**Recommended path**: `full`

**Rationale**:
1. **Requires external research**: Quiz generation is a well-studied field in educational technology and NLP. Implementing a "well-researched algorithm" (per user request) requires investigating SOTA approaches like:
   - Automatic question generation papers (e.g., "Neural Question Generation" models, transformers for QG)
   - Distractor generation techniques (semantic similarity, common misconceptions)
   - Bloom's taxonomy alignment for question difficulty
   - Question quality metrics and validation approaches

2. **High file count**: 8-10 files across all architecture layers (domain, use_case, infrastructure, presentation).

3. **Architectural complexity**: Two-stage LLM pipeline + parallel execution + validation + interactive frontend exceeds 150 LOC threshold.

4. **Design decisions needed**: Interactive format vs static, question taxonomy, scoring system, difficulty calibration - these require multi-agent debate to evaluate trade-offs.

The `full` path will enable Bold-proposer to research quiz generation algorithms, propose SOTA-informed design, have Critique evaluate educational validity, and Reducer optimize the implementation.
